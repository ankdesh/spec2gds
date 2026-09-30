import assert from "node:assert/strict";
import { once } from "node:events";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import test from "node:test";
import { apply } from "../src/index.js";

async function hostFixture(interactiveForms = true) {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-creation-host-"));
  const contract = JSON.parse(await readFile(new URL("./fixtures/spec-document-operation-contract.json", import.meta.url), "utf8"));
  let active: string | null = null;
  let creates = 0;
  let contextReads = 0;
  const owner = createServer(async (request, response) => {
    const path = new URL(request.url!, "http://local").pathname;
    const send = (value: unknown, status = 200) => { response.writeHead(status, { "Content-Type": "application/json" }); response.end(JSON.stringify(value)); };
    if (path === "/health") return send({ status: "ok" });
    if (path === "/assistant/capabilities") return send({ approval_policy: "review" });
    if (path === "/documents/create") {
      let text = ""; for await (const chunk of request) text += chunk;
      const body = JSON.parse(text);
      try { await writeFile(body.path, body.document_id, { flag: "wx" }); }
      catch { return send({ detail: "Refusing to replace existing package" }, 422); }
      active = body.document_id; creates++;
      return send({ document_id: active, source_revision_hash: "sha256:created" });
    }
    if (!active) return send({ detail: "No V1 .spec package is open." }, 400);
    if (path === "/assistant/operation-schema") return send(contract);
    if (path === "/assistant/context/document") {
      contextReads++;
      return send({ document_id: active, source_revision_hash: "sha256:created", scope: "document", target: null,
        rendered_context: { document_id: active, source_revision_hash: "sha256:created", target: null, text: "Empty specification" },
        available_references: {}, diagnostics: [] });
    }
    return send({ detail: "Unexpected route" }, 404);
  });
  owner.listen(0, "127.0.0.1"); await once(owner, "listening");
  const address = owner.address(); assert.ok(address && typeof address === "object");
  const url = `http://127.0.0.1:${address.port}`;
  const listeners = new Map<string, Array<(...args: any[]) => any>>();
  const routes: any[] = [];
  const agents = new Map<string, any>();
  const workflows = new Map<string, any>();
  const starts: any[] = [];
  const answered: string[] = [];
  const ctx: any = {
    agents: { get: (id: string) => agents.get(id) },
    sessionPersistence: { list: async () => [] },
    promptCatalog: { get: () => ({}), seal: () => {}, bind: () => ({ sections: ["domain-persona", "binding-context", "operation-constraints", "output-contract"].map((id, index) => ({ id, order: 100 + index * 50, text: id })) }) },
    sWorkflow: { catalog: (domain: string) => ({ definitions: [{ value: { metadata: { id: "prepare-reviewed-change", version: "1.0.0" } } }], adapters: [{ value: { metadata: { id: `${domain}-editor`, version: "1.0.0" } } }] }),
      seal: () => {}, get: (agent: any) => workflows.get(agent.id) ?? null,
      start: (agent: any, request: any) => { starts.push(request); workflows.set(agent.id, { status: "active", preset: request.preset, runId: "run", revision: 0, budget: { maxDelegationDepth: 1, maxConcurrency: 2 } }); },
      answerInput: (_agent: any, _ref: any, text: string) => { answered.push(text); }, checkpoint: () => {},
    },
    on: (event: string, listener: (...args: any[]) => any) => { listeners.set(event, [...(listeners.get(event) ?? []), listener]); return () => {}; },
    effect: (effect: () => any) => effect(),
    inject: (_deps: string[], callback: (context: any) => any) => callback({ ...ctx,
      webServer: { register: (route: any) => { routes.push(route); return () => {}; } }, connection: { authenticatedUrl: (value: string) => `${value}/?token=fixture` },
    }),
  };
  apply(ctx, { provider: "openai", model: "fixture", stateRoot: root, scratchRoot: join(root, "workspaces"), specDocumentRoot: root,
    specAllowlist: url, circuitAllowlist: "http://127.0.0.1:9/api/circuit-designer/v1", requestTimeoutMs: 1_000,
    maxStepsPerTurn: 3, maxOutputTokens: 1_200, interactiveForms });
  const emit = async (event: string, ...args: any[]) => { for (const listener of listeners.get(event) ?? []) await listener(...args); };
  const makeAgent = async (id: string, preset = "focused", parentSession?: string) => {
    const tools = new Map<string, any>(); const sections = new Map<string, any>();
    const agent = { id, session: { header: { agentPreset: preset, parentSession, delegationDepth: parentSession ? 1 : 0 } },
      ctx: { tools: { register: (tool: any) => { tools.set(tool.name, tool); return () => tools.delete(tool.name); }, get: (name: string) => tools.get(name) },
        systemPrompt: { section: (section: any) => { sections.set(section.name, section); return () => sections.delete(section.name); } } }, tools, sections };
    agents.set(id, agent); await emit("agent/created", { agent }); return agent;
  };
  const message = (sessionId: string, text: string) => emit("session/event", { id: sessionId }, { type: "user/message", data: { source: { kind: "user" }, content: [{ type: "text", text }] } });
  const api = async (path: string, body?: unknown, origin?: string) => {
    const route = routes.find(route => route.kind === "prefix");
    const request: any = Readable.from(body === undefined ? [] : [Buffer.from(JSON.stringify(body))]);
    request.url = `/spec2gds-api${path}`; request.method = body === undefined ? "GET" : "POST";
    request.headers = { host: "local", "content-type": "application/json", ...(origin ? { origin } : {}) };
    let status = 0; let value: any;
    await route.handler(request, { writeHead: (code: number) => { status = code; }, end: (text: string) => { value = JSON.parse(text); } });
    return { status, value };
  };
  return { root, url, makeAgent, emit, message, api, starts, answered, workflows,
    get creates() { return creates; }, get contextReads() { return contextReads; },
    async close() { await emit("dispose"); await new Promise<void>(resolve => owner.close(() => resolve())); await rm(root, { recursive: true, force: true }); },
  };
}

test("browser root presets create from an unbound chat and start workflows only in the destination", async () => {
  const f = await hostFixture();
  try {
    for (const preset of ["focused", "goal", "orchestrated"]) {
      const original = `Create a new spec document for a 3-bit comparator (${preset}) with A[2:0], B[2:0], and one-bit A_greater, A_equal, A_less.`;
      const origin = await f.makeAgent(`origin-${preset}`, preset);
      assert.match(origin.sections.get("spec2gds:unbound-session").text, /Do not read get_bound_context first/,
        "The complete unbound prompt must retain the creation instructions");
      await f.message(origin.id, original);
      assert.equal(f.workflows.has(origin.id), false);
      const prepared = await origin.tools.get("prepare_spec_document_creation").execute({ title: "Comparator", document_id: `comparator_${preset}` }, { callId: `call-${preset}` });
      const request = prepared.source_creation;
      assert.equal(request.originalRequest, original);
      assert.equal(f.workflows.has(origin.id), false);
      const created = await f.api("/sources/create", { domain: "spec", creationRequestId: request.requestId,
        documentId: request.documentId, title: request.title, serviceBaseUrl: request.serviceBaseUrl });
      assert.equal(created.status, 201, JSON.stringify(created.value));
      assert.equal(created.value.session.preset, preset);
      const destination = await f.makeAgent(created.value.session.sessionId, preset);
      await f.api(`/bindings/${destination.id}/activate`, {});
      await f.message(destination.id, created.value.continuation.message);
      assert.equal(f.workflows.has(destination.id), false);
      await destination.tools.get("get_bound_context").execute({}, { signal: new AbortController().signal });
      assert.equal(f.workflows.has(destination.id), preset !== "focused");
      assert.equal(f.workflows.has(origin.id), false);
      assert.equal((await f.api(`/source-requests/${request.requestId}/continued`, {})).status, 200);
      const replay = await f.api("/sources/create", { domain: "spec", creationRequestId: request.requestId,
        documentId: request.documentId, title: request.title, serviceBaseUrl: request.serviceBaseUrl });
      assert.equal(replay.value.session.sessionId, destination.id);
      assert.equal(replay.value.continuation.sent, true);
      assert.equal((await f.api(`/bindings/${origin.id}`)).status, 404);
    }
    assert.equal(f.creates, 3);
  } finally { await f.close(); }
});

test("existing chooser creation works and a bound chat can create another package without reading or rebinding its owner", async () => {
  const f = await hostFixture();
  try {
    const existing = await f.api("/sources/create", { domain: "spec", serviceBaseUrl: f.url, documentId: "original", title: "Original", preset: "goal" });
    assert.equal(existing.status, 201);
    const origin = await f.makeAgent(existing.value.session.sessionId, "goal");
    await f.api(`/bindings/${origin.id}/activate`, {});
    f.workflows.set(origin.id, { status: "awaiting-user-input", preset: "goal", budget: {} });
    const reads = f.contextReads;
    await f.message(origin.id, "Create a new spec document for a comparator");
    const request = (await origin.tools.get("prepare_spec_document_creation").execute({ document_id: "comparator", title: "Comparator" }, { callId: "bound-create" })).source_creation;
    assert.equal(f.contextReads, reads);
    assert.equal(f.answered.length, 0, "Creation must not consume pending workflow input");
    assert.equal((await f.api("/sources/create", { domain: "spec", creationRequestId: request.requestId,
      documentId: request.documentId, title: request.title, serviceBaseUrl: f.url })).status, 201);
    const unchanged = await f.api(`/bindings/${origin.id}`);
    assert.equal(unchanged.value.session.documentId, "original");
    assert.equal(unchanged.value.session.workspaceKey, existing.value.session.workspaceKey);
    assert.equal(f.workflows.get(origin.id).status, "awaiting-user-input");
    assert.equal((await f.api(`/source-requests/${request.requestId}`, undefined, "http://evil")).status, 403);
  } finally { await f.close(); }
});

test("headless and delegated agents do not acquire the creation tool", async () => {
  const headless = await hostFixture(false); const web = await hostFixture();
  try {
    const unbound = await headless.makeAgent("headless");
    assert.equal(unbound.tools.has("prepare_spec_document_creation"), false);
    const source = await web.api("/sources/create", { domain: "spec", serviceBaseUrl: web.url, documentId: "parent", title: "Parent", preset: "orchestrated" });
    const parent = await web.makeAgent(source.value.session.sessionId, "orchestrated");
    await web.api(`/bindings/${parent.id}/activate`, {});
    await web.message(parent.id, "Inspect the bound specification");
    await parent.tools.get("get_bound_context").execute({}, { signal: new AbortController().signal });
    const child = await web.makeAgent("child", "focused", parent.id);
    assert.equal(child.tools.has("prepare_spec_document_creation"), false);
    assert.equal(child.tools.has("get_bound_context"), true);
  } finally { await headless.close(); await web.close(); }
});
