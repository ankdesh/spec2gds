/** Real headless profile, owner tools, proposal preview, and durable binding state. */
import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { DatabaseSync } from "node:sqlite";
import { calculateMetrics, parseJsonLines } from "../lib/eval-metrics.js";

import { approveTimer } from "./support/approved-timer.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  return server.address().port;
}

async function sessionLogs(root) {
  const entries = await readdir(root, { recursive: true, withFileTypes: true });
  return entries.filter(entry => entry.isFile() && (entry.name.endsWith(".jsonl") || entry.name.endsWith(".jsonl.zstd")))
    .map(entry => resolve(entry.parentPath, entry.name));
}

test("one-off profile reads bound context and persists a previewed proposal", { timeout: 90_000 }, async () => {
  let ownerReads = 0;
  let previews = 0;
  const operationContract = JSON.parse(await readFile(new URL("./fixtures/spec-document-operation-contract.json", import.meta.url), "utf8"));
  const owner = createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/health") return send(response, { status: "ok" });
    if (url.pathname === "/assistant/operation-schema") return send(response, operationContract);
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
    const looping = Array.isArray(body.tools) && JSON.stringify(body.messages).includes("Repeat context forever");
    const delta = looping
      ? { tool_calls: [{ index: 0, id: `call_context_${toolResults}`, type: "function", function: { name: "get_bound_context", arguments: "{}" } }] }
      : toolResults === 0
      ? { tool_calls: [{ index: 0, id: "call_context", type: "function", function: { name: "get_bound_context", arguments: "{}" } }] }
      : toolResults === 1
        ? { tool_calls: [{ index: 0, id: "call_proposal", type: "function", function: { name: "prepare_spec_proposal", arguments: JSON.stringify({
          architecture_review_id: "approved-timer",
          supported: true,
          base_source_revision_hash: "sha256:test",
          unsupported_reason: null,
          title: "Add timer",
          summary: "Adds a timer component.",
          rationale: "The design needs timing control.",
          assumptions: [],
          operations: [{ operation_id: "create_timer", type: "create_entity", kind: "component", name: "timer", entity_id: "local-timer", instances: [] }, { operation_id: "explanation", type: "set_entity_metadata", entity: { document_id: "doc-test", entity_kind: "component", entity_id: "local-timer" }, description: "Timing control. Interface and functional RTL are not implemented yet." }],
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
        choices: [{ index: 0, delta: chunks[index], finish_reason: index === 2 ? looping || toolResults < 2 ? "tool_calls" : "stop" : null }],
        ...(index === 2 ? { usage: { prompt_tokens: 20, completion_tokens: 5, total_tokens: 25, prompt_tokens_details: { cached_tokens: 4 } } } : {}),
      })}\n\n`);
    }
    response.end("data: [DONE]\n\n");
  });
  const providerPort = await listen(provider);
  const state = await mkdtemp(join(tmpdir(), "spec2gds-harness-integration-"));
  const loopState = await mkdtemp(join(tmpdir(), "spec2gds-harness-loop-limit-"));
  const replayState = await mkdtemp(join(tmpdir(), "spec2gds-harness-replay-"));
  const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"));
  let child;
  let loopChild;
  let replayChild;
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
        SPEC2GDS_SESSION_COMPRESSION: "none",
        SPEC_SERVICE_ALLOWLIST: `http://127.0.0.1:${ownerPort}`,
        CIRCUIT_SERVICE_ALLOWLIST: "http://127.0.0.1:9/api/circuit-designer/v1",
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: `http://127.0.0.1:${providerPort}/v1`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    child.stdout.on("data", value => { output += value; for (const line of String(value).split("\n")) { try { const event=JSON.parse(line); if(event.type==="session") approveTimer(state,event.sessionId); } catch { /* Other stream lines are not session headers. */ } } });
    child.stderr.on("data", value => { output += value; });
    const [code, signal] = await once(child, "exit");
    assert.equal(signal, null, output);
    assert.equal(code, 0, output);
    assert.match(output, /one ALU/);
    assert.ok(ownerReads >= 3, `Expected validation, context, and proposal reads; got ${ownerReads}.\n${output}`);
    assert.equal(previews, 1);
    const agentRequests = modelRequests.filter(request => Array.isArray(request.tools));
    assert.equal(agentRequests.length, 3);
    assert.ok(agentRequests.every(request => (request.max_tokens ?? request.max_completion_tokens) === 1200),
      `Expected every agent request to use the product output cap: ${agentRequests.map(request => request.max_tokens ?? request.max_completion_tokens).join(", ")}`);
    const systemMessage = agentRequests[0].messages.find(message => message.role === "system");
    const system = String(systemMessage?.content);
    assert.match(system, /You are the focused spec2gds hardware-design assistant\./);
    assert.match(system, /Document ID: doc-test/);
    assert.match(system, /MUST call get_bound_context before answering/);
    assert.match(system, /Never ask the user which document or design they mean/);
    const promptMarkers = ["DOMAIN PERSONA", "BOUND CONVERSATION", "OPERATION CONSTRAINTS", "OUTPUT CONTRACT"];
    for (const marker of promptMarkers) assert.equal(system.split(marker).length - 1, 1, `Expected one ${marker} section.\n${system}`);
    for (let index = 1; index < promptMarkers.length; index += 1) {
      assert.ok(system.indexOf(promptMarkers[index - 1]) < system.indexOf(promptMarkers[index]),
        `Expected ${promptMarkers[index - 1]} before ${promptMarkers[index]}.\n${system}`);
    }
    const toolNames = agentRequests[0].tools.map(tool => tool.function.name);
    assert.ok(toolNames.includes("get_bound_context"));
    assert.ok(toolNames.includes("prepare_spec_proposal"));
    const forbiddenGeneralTools = new Set([
      "bash", "pwsh", "jobs", "fs", "fs_search", "skill", "subagent",
      "workflow", "ralph", "todo", "web", "apply", "send", "create",
      "create_goal", "get_goal", "update_goal",
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

    const requestsBeforeLoop = modelRequests.length;
    loopChild = spawn(process.execPath, [
      resolve(root, "scripts/request.mjs"),
      "--json",
      "--domain", "spec",
      "--service-url", `http://127.0.0.1:${ownerPort}`,
      "--document-id", "doc-test",
      "--",
      "Repeat context forever.",
    ], {
      cwd: root,
      env: {
        ...process.env,
        HARNESS_SOURCE: harness,
        ASSISTANT_STATE: loopState,
        SPEC_SERVICE_ALLOWLIST: `http://127.0.0.1:${ownerPort}`,
        CIRCUIT_SERVICE_ALLOWLIST: "http://127.0.0.1:9/api/circuit-designer/v1",
        OPENAI_API_KEY: "fixture-key",
        OPENAI_BASE_URL: `http://127.0.0.1:${providerPort}/v1`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let loopOutput = "";
    loopChild.stdout.on("data", value => { loopOutput += value; });
    loopChild.stderr.on("data", value => { loopOutput += value; });
    const [loopCode, loopSignal] = await once(loopChild, "exit");
    assert.equal(loopSignal, null, loopOutput);
    assert.equal(loopCode, 1, loopOutput);
    assert.match(loopOutput, /"reason":\{"kind":"blocked"\}/);
    const loopAgentRequests = modelRequests.slice(requestsBeforeLoop).filter(request => Array.isArray(request.tools));
    assert.equal(loopAgentRequests.length, 3,
      `The product must stop a repeated tool trajectory after three model steps.\n${loopOutput}`);

    const logs = await sessionLogs(state);
    assert.equal(logs.length, 1, `Expected one recorded Session log under ${state}, got ${logs.join(", ")}`);
    const recordedMetrics = calculateMetrics(parseJsonLines(await readFile(logs[0], "utf8")), 1);
    assert.equal(recordedMetrics.proposalCalls, 1);
    assert.equal(recordedMetrics.schemaValidProposalCalls, 1);
    assert.equal(recordedMetrics.firstPreviewReadyCases, 1);
    assert.equal(recordedMetrics.proposedOperations, 2);
    assert.ok(recordedMetrics.tokens.input > 0);
    assert.ok(recordedMetrics.tokens.output > 0);
    const providerRequestsBeforeReplay = modelRequests.length;
    replayChild = spawn(process.execPath, [
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
        ASSISTANT_PROFILE: "spec2gds-replay",
        ASSISTANT_STATE: replayState,
        SPEC2GDS_SESSION_COMPRESSION: "none",
        DSH_SNAPSHOT_FILE: logs[0],
        SPEC_SERVICE_ALLOWLIST: `http://127.0.0.1:${ownerPort}`,
        CIRCUIT_SERVICE_ALLOWLIST: "http://127.0.0.1:9/api/circuit-designer/v1",
        OPENAI_API_KEY: "must-not-be-used",
        OPENAI_BASE_URL: "http://127.0.0.1:9/v1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let replayOutput = "";
    replayChild.stdout.on("data", value => { replayOutput += value; for (const line of String(value).split("\n")) { try { const event=JSON.parse(line); if(event.type==="session") approveTimer(replayState,event.sessionId); } catch { /* Other stream lines are not session headers. */ } } });
    replayChild.stderr.on("data", value => { replayOutput += value; });
    const [replayCode, replaySignal] = await once(replayChild, "exit");
    assert.equal(replaySignal, null, replayOutput);
    assert.equal(replayCode, 0, replayOutput);
    assert.match(replayOutput, /timer proposal is ready for review/i);
    assert.equal(modelRequests.length, providerRequestsBeforeReplay, "DSH replay must not call the provider fixture.");
  } finally {
    if (child && child.exitCode === null) child.kill("SIGTERM");
    if (loopChild && loopChild.exitCode === null) loopChild.kill("SIGTERM");
    if (replayChild && replayChild.exitCode === null) replayChild.kill("SIGTERM");
    await Promise.all([new Promise(done => owner.close(done)), new Promise(done => provider.close(done))]);
    await Promise.all([
      rm(state, { recursive: true, force: true }),
      rm(loopState, { recursive: true, force: true }),
      rm(replayState, { recursive: true, force: true }),
    ]);
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
