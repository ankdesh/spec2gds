/** Real Harness boot, owner-context tool dispatch, streaming, and restart recovery. */
import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { once } from "node:events";

const root = fileURLToPath(new URL("..", import.meta.url));
const delay = ms => new Promise(resolvePromise => setTimeout(resolvePromise, ms));
async function until(fn, message, timeout = 30_000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn(); if (value) return value; await delay(100); }
  throw new Error(message);
}
async function listen(server) { server.listen(0, "127.0.0.1"); await once(server, "listening"); return server.address().port; }

test("boots the product profile, calls owner context, streams, and resumes", { timeout: 90_000 }, async () => {
  let ownerReads = 0;
  let revision = "sha256:test";
  const applied = new Map();
  const owner = createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/health") return send(response, { status: "ok" });
    if (url.pathname === "/assistant/context/document") {
      ownerReads += 1;
      return send(response, {
        schema_version: "spec2gds.assistant-context.v1", scope: "document", document_id: "doc-test",
        source_revision_hash: revision, target: null,
        writable: { document_operations: ["create_entity"] }, read_only: { existing_entities: true },
        rendered_context: { document_id: "doc-test", source_revision_hash: revision, target: null, text: "Test specification with one ALU." },
        available_references: { components: [], designs: [] }, diagnostics: [],
      });
    }
    if (request.method === "POST" && url.pathname === "/assistant/proposals/preview") {
      return readJson(request).then(proposal => send(response, {
        status: proposal.base_source_revision_hash === revision ? "valid" : "stale",
        proposal_id: proposal.proposal_id,
        diagnostics: [],
        operation_count: proposal.operations.length,
      }));
    }
    if (request.method === "POST" && url.pathname === "/assistant/proposals/apply") {
      return readJson(request).then(proposal => {
        const existing = applied.get(proposal.proposal_id);
        if (!existing) {
          revision = "sha256:applied";
          applied.set(proposal.proposal_id, { proposal_id: proposal.proposal_id, result_source_revision_hash: revision });
        }
        send(response, { status: "applied", proposal_id: proposal.proposal_id, source_revision_hash: revision, idempotent_replay: Boolean(existing) });
      });
    }
    if (request.method === "GET" && url.pathname === "/assistant/changes") {
      return send(response, { assistant_changes: [...applied.values()] });
    }
    response.writeHead(404); response.end();
  });
  const ownerPort = await listen(owner);

  const modelRequests = [];
  const provider = createServer(async (request, response) => {
    let raw = ""; for await (const chunk of request) raw += chunk;
    const body = JSON.parse(raw); modelRequests.push(body);
    const toolResults = body.messages.filter(message => message.role === "tool").length;
    const delta = toolResults === 0
      ? { tool_calls: [{ index: 0, id: "call_context", type: "function", function: { name: "get_bound_context", arguments: "{}" } }] }
      : toolResults === 1
        ? { tool_calls: [{ index: 0, id: "call_proposal", type: "function", function: { name: "prepare_spec_proposal", arguments: JSON.stringify({
          supported: true, unsupported_reason: null,
          title: "Add timer", summary: "Adds a timer component.", rationale: "The design needs timing control.", assumptions: [],
          operations: [{ operation_id: "create_timer", type: "create_entity", kind: "component", name: "timer", instances: [] }],
        }) } }] }
        : { content: "The bound specification contains one ALU. The timer proposal is ready for your review." };
    response.writeHead(200, { "Content-Type": "text/event-stream" });
    for (const [index, part] of [{ role: "assistant" }, delta, {}].entries()) {
      response.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", created: 1, model: "gpt-4o-mini", choices: [{ index: 0, delta: part, finish_reason: index === 2 ? toolResults >= 2 ? "stop" : "tool_calls" : null }] })}\n\n`);
    }
    response.end("data: [DONE]\n\n");
  });
  const providerPort = await listen(provider);
  const reserve = createServer(); const assistantPort = await listen(reserve); await new Promise(done => reserve.close(done));
  const state = await mkdtemp(join(tmpdir(), "spec2gds-harness-integration-"));
  const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"));
  let child; let output = "";
  const env = {
    ...process.env, HARNESS_SOURCE: harness, ASSISTANT_STATE: state, ASSISTANT_HOST: "127.0.0.1",
    ASSISTANT_PORT: String(assistantPort), SPEC_SERVICE_ALLOWLIST: `http://127.0.0.1:${ownerPort}`,
    CIRCUIT_SERVICE_ALLOWLIST: "http://127.0.0.1:9/api/circuit-designer/v1",
    OPENAI_API_KEY: "fixture-key", OPENAI_BASE_URL: `http://127.0.0.1:${providerPort}/v1`,
  };
  function start() {
    child = spawn(process.execPath, [resolve(root, "scripts/dev.mjs")], { cwd: root, env, stdio: ["ignore", "pipe", "pipe"] });
    child.stdout.on("data", value => { output += value; }); child.stderr.on("data", value => { output += value; });
  }
  async function stop() { if (child && child.exitCode === null) { const done = once(child, "exit"); child.kill("SIGTERM"); await done; } }
  const base = `http://127.0.0.1:${assistantPort}`;
  async function ready() { await until(async () => { if (child.exitCode !== null) throw new Error(output); try { return (await fetch(`${base}/readyz`)).ok; } catch { return false; } }, "Assistant did not become ready."); }
  async function api(path, value) {
    const response = await fetch(`${base}/api${path}`, { method: value === undefined ? "GET" : "POST", headers: value === undefined ? {} : { "Content-Type": "application/json" }, body: value === undefined ? undefined : JSON.stringify(value) });
    const body = await response.json(); assert.ok(response.ok, JSON.stringify(body)); return body;
  }
  try {
    start(); await ready();
    const created = await api("/sessions", { domain: "spec", scope: "document", serviceBaseUrl: `http://127.0.0.1:${ownerPort}`, documentId: "doc-test" });
    const id = created.session.sessionId;
    await api(`/sessions/${id}/messages`, { text: "What is in this specification?" });
    const completed = await until(async () => { const value = await api(`/sessions/${id}`); return !value.running && value.events.some(event => event.type === "turn/end") ? value : false; }, "Turn did not complete.");
    assert.ok(completed.events.some(event => event.type === "assistant/message" && event.text.includes("one ALU")));
    assert.ok(ownerReads >= 2, `Expected validation and tool context reads, got ${ownerReads}`);
    assert.ok(modelRequests[0].tools.some(tool => tool.function.name === "get_bound_context"));
    assert.ok(modelRequests[0].tools.every(tool => !["apply", "send", "create"].includes(tool.function.name)));
    const review = completed.reviews.find(item => item.state === "ready");
    assert.ok(review, "Expected an owner-previewed review.");
    const accepted = await api(`/sessions/${id}/reviews/${review.proposalId}/actions`, { action: "apply" });
    assert.equal(accepted.review.state, "applied");
    assert.equal(applied.size, 1);
    await stop(); start(); await ready();
    const resumed = await api(`/sessions/${id}`);
    assert.ok(resumed.events.some(event => event.type === "assistant/message" && event.text.includes("one ALU")));
    assert.equal((await api(`/sessions/${id}/manage`, { action: "rename", title: "Timer work" })).session.title, "Timer work");
    assert.equal((await api(`/sessions/${id}/manage`, { action: "archive" })).session.archived, true);
    const archivedWrite = await fetch(`${base}/api/sessions/${id}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: "should fail" }) });
    assert.equal(archivedWrite.status, 409);
    assert.equal((await api(`/sessions/${id}/manage`, { action: "unarchive" })).session.archived, false);
  } finally {
    await stop(); await Promise.all([new Promise(done => owner.close(done)), new Promise(done => provider.close(done))]);
    await rm(state, { recursive: true, force: true });
  }
});

function send(response, value) { response.writeHead(200, { "Content-Type": "application/json" }); response.end(JSON.stringify(value)); }
async function readJson(request) { let raw = ""; for await (const chunk of request) raw += chunk; return JSON.parse(raw); }
