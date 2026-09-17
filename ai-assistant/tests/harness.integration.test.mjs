/** Real headless profile, owner tools, proposal preview, and durable binding state. */
import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { DatabaseSync } from "node:sqlite";

const root = fileURLToPath(new URL("..", import.meta.url));

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  return server.address().port;
}

test("one-off profile reads bound context and persists a previewed proposal", { timeout: 90_000 }, async () => {
  let ownerReads = 0;
  let previews = 0;
  const owner = createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/health") return send(response, { status: "ok" });
    if (url.pathname === "/assistant/context/document") {
      ownerReads += 1;
      return send(response, {
        schema_version: "spec2gds.assistant-context.v1",
        scope: "document",
        document_id: "doc-test",
        source_revision_hash: "sha256:test",
        target: null,
        writable: { document_operations: ["create_entity"] },
        read_only: { existing_entities: true },
        rendered_context: {
          document_id: "doc-test",
          source_revision_hash: "sha256:test",
          target: null,
          text: "Test specification with one ALU.",
        },
        available_references: { components: [], designs: [] },
        diagnostics: [],
      });
    }
    if (request.method === "POST" && url.pathname === "/assistant/proposals/preview") {
      previews += 1;
      return readJson(request).then(proposal => send(response, {
        status: "valid",
        proposal_id: proposal.proposal_id,
        diagnostics: [],
        operation_count: proposal.operations.length,
        diff: [{ path: "components.timer", change: "added", before: null, after: { name: "timer" } }],
      }));
    }
    response.writeHead(404);
    response.end();
  });
  const ownerPort = await listen(owner);

  const modelRequests = [];
  const provider = createServer(async (request, response) => {
    const body = await readJson(request);
    modelRequests.push(body);
    const toolResults = body.messages.filter(message => message.role === "tool").length;
    const delta = toolResults === 0
      ? { tool_calls: [{ index: 0, id: "call_context", type: "function", function: { name: "get_bound_context", arguments: "{}" } }] }
      : toolResults === 1
        ? { tool_calls: [{ index: 0, id: "call_proposal", type: "function", function: { name: "prepare_spec_proposal", arguments: JSON.stringify({
          supported: true,
          unsupported_reason: null,
          title: "Add timer",
          summary: "Adds a timer component.",
          rationale: "The design needs timing control.",
          assumptions: [],
          operations: [{ operation_id: "create_timer", type: "create_entity", kind: "component", name: "timer", instances: [] }],
        }) } }] }
        : { content: "The bound specification contains one ALU. The timer proposal is ready for review." };
    response.writeHead(200, { "Content-Type": "text/event-stream" });
    const chunks = [{ role: "assistant" }, delta, {}];
    for (let index = 0; index < chunks.length; index += 1) {
      response.write(`data: ${JSON.stringify({
        id: "fixture",
        object: "chat.completion.chunk",
        created: 1,
        model: "gpt-4o-mini",
        choices: [{ index: 0, delta: chunks[index], finish_reason: index === 2 ? toolResults >= 2 ? "stop" : "tool_calls" : null }],
      })}\n\n`);
    }
    response.end("data: [DONE]\n\n");
  });
  const providerPort = await listen(provider);
  const state = await mkdtemp(join(tmpdir(), "spec2gds-harness-integration-"));
  const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"));
  let child;
  try {
    child = spawn(process.execPath, [
      resolve(root, "scripts/request.mjs"),
      "--json",
      "--domain", "spec",
      "--service-url", `http://127.0.0.1:${ownerPort}`,
      "--document-id", "doc-test",
      "--",
      "Inspect the specification and propose a timer component.",
    ], {
      cwd: root,
      env: {
        ...process.env,
        HARNESS_SOURCE: harness,
        ASSISTANT_STATE: state,
        SPEC_SERVICE_ALLOWLIST: `http://127.0.0.1:${ownerPort}`,
        CIRCUIT_SERVICE_ALLOWLIST: "http://127.0.0.1:9/api/circuit-designer/v1",
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: `http://127.0.0.1:${providerPort}/v1`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    child.stdout.on("data", value => { output += value; });
    child.stderr.on("data", value => { output += value; });
    const [code, signal] = await once(child, "exit");
    assert.equal(signal, null, output);
    assert.equal(code, 0, output);
    assert.match(output, /one ALU/);
    assert.ok(ownerReads >= 3, `Expected validation, context, and proposal reads; got ${ownerReads}.\n${output}`);
    assert.equal(previews, 1);
    assert.ok(modelRequests.length >= 3);
    const toolNames = modelRequests[0].tools.map(tool => tool.function.name);
    assert.ok(toolNames.includes("get_bound_context"));
    assert.ok(toolNames.includes("prepare_spec_proposal"));
    const forbiddenGeneralTools = new Set([
      "bash", "pwsh", "jobs", "fs", "fs_search", "skill", "subagent",
      "workflow", "ralph", "todo", "web", "apply", "send", "create",
    ]);
    assert.ok(
      toolNames.every(name => !forbiddenGeneralTools.has(name)),
      `Focused profile exposed general tools: ${toolNames.filter(name => forbiddenGeneralTools.has(name)).join(", ")}`,
    );

    const database = new DatabaseSync(resolve(state, "assistant.sqlite3"), { readOnly: true });
    try {
      const binding = database.prepare("SELECT status, domain, document_id, scope FROM bindings").get();
      assert.deepEqual({ ...binding }, { status: "active", domain: "spec", document_id: "doc-test", scope: "document" });
      const review = database.prepare("SELECT state, domain, artifact_json, preview_json FROM reviews").get();
      assert.equal(review.state, "ready");
      assert.equal(review.domain, "spec");
      assert.equal(JSON.parse(review.artifact_json).operations[0].type, "create_entity");
      assert.equal(JSON.parse(review.preview_json).status, "valid");
    } finally {
      database.close();
    }
  } finally {
    if (child && child.exitCode === null) child.kill("SIGTERM");
    await Promise.all([new Promise(done => owner.close(done)), new Promise(done => provider.close(done))]);
    await rm(state, { recursive: true, force: true });
  }
});

function send(response, value) {
  response.writeHead(200, { "Content-Type": "application/json" });
  response.end(JSON.stringify(value));
}

async function readJson(request) {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  return JSON.parse(raw);
}
