import { serveIntegrationMetadata } from "./support/integration-metadata.mjs";
import { architecturePlan } from "./support/architecture.js";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import test from "node:test";
import { apply } from "../src/index.js";

async function hostFixture(interactiveForms = true, storedIds: string[] = []) {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-creation-host-"));
  const contract = JSON.parse(await readFile(new URL("./fixtures/spec-document-operation-contract.json", import.meta.url), "utf8"));
  let active: string | null = null;
  let durability = true;
  let creates = 0;
  let contextReads = 0;
  const owner = createServer(async (request, response) => {
    if (serveIntegrationMetadata(request, response)) return;
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
  const executions = new Map<string, any>();
  const starts: any[] = [];
  const members = new Map<string, any>();
  const ctx: any = {
    eventHttpSources: { list: () => [] },
    agents: { get: (id: string) => agents.get(id) },
    sessions: { flush: async () => durability },
    sessionPersistence: { open: async (id: string) => ({ read: async () => ({ events: agents.get(id)?.events || [] }), close: async () => {} }), list: async () => storedIds.map(id => ({ header: { id } })) },
    promptCatalog: { get: () => ({}), seal: () => {}, bind: () => ({ sections: ["domain-persona", "binding-context", "operation-constraints", "output-contract"].map((id, index) => ({ id, order: 100 + index * 50, text: id })) }) },
    eventSystems: {
      ready: Promise.resolve(), definition: (id: string) => {
        const [_, domain, preset] = id.split(".");
        const template = JSON.parse(readFileSync(new URL(`../profile/catalog/event-systems/${domain}-${preset}.yaml`, import.meta.url), "utf8"));
        return { ...template, agents: template.agents.map((agent: any) => ({ ...agent, prompt: readFileSync(new URL(`../profile/catalog/event-systems/${agent.prompt}`, import.meta.url), "utf8") })) };
      }, seal: () => {},
      get: (id: string) => executions.get(id), membership: (id: string) => members.get(id),
      attach: async (agent: any, mode: string, definition: any, limits: any) => {
        starts.push({ mode, definition, limits });
        executions.set(agent.id, { status: "active", mode, revision: 1, definition: { primary: "primary" }, events: [], deliveries: [], limits });
        members.set(agent.id, { conversationId: agent.id, member: "primary", primary: true });
      },
      publishHost: async () => {}, hold: async () => {},
    },
    goals: { get: () => undefined },
    on: (event: string, listener: (...args: any[]) => any) => { listeners.set(event, [...(listeners.get(event) ?? []), listener]); return () => {}; },
    effect: (effect: () => any) => effect(),
    inject: (_deps: string[], callback: (context: any) => any) => callback({ ...ctx,
      webServer: { register: (route: any) => { routes.push(route); return () => {}; } }, connection: { authenticatedUrl: (value: string) => `${value}/?token=fixture` },
    }),
  };
  apply(ctx, { provider: "openai", model: "fixture", stateRoot: root, scratchRoot: join(root, "workspaces"), specDocumentRoot: root,
    specAllowlist: url, circuitAllowlist: "http://127.0.0.1:9/api/circuit-designer/v1", requestTimeoutMs: 1_000,
    maxStepsPerTurn: 3, maxOutputTokens: 1_200, interactiveForms,
    execution: {
      goal: { maxRounds: 8, maxRequests: 32, maxTokens: 300_000, maxActiveMillis: 1_800_000, maxMembers: 1, maxConcurrency: 1, maxPending: 100, maxEvents: 256, maxPayloadBytes: 131072, maxDepth: 16 },
      orchestrated: { maxRounds: 8, maxRequests: 48, maxTokens: 500_000, maxActiveMillis: 2_700_000, maxMembers: 7, maxConcurrency: 3, maxPending: 100, maxEvents: 256, maxPayloadBytes: 131072, maxDepth: 16 },
    } });
  const emit = async (event: string, ...args: any[]) => { for (const listener of listeners.get(event) ?? []) await listener(...args); };
  const makeAgent = async (id: string, preset = "focused", parentSession?: string) => {
    const tools = new Map<string, any>(); const sections = new Map<string, any>();
    const events: any[] = [];
    const agent = { id, events, followup: (input: any) => { events.push({ type: "agent/inbox/spliced", data: { inserted: [input] } }); }, session: { header: { agentPreset: preset, parentSession, delegationDepth: parentSession ? 1 : 0 } },
      ctx: { tools: { register: (tool: any) => { tools.set(tool.name, tool); return () => tools.delete(tool.name); }, get: (name: string) => tools.get(name), guard: () => () => {} },
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
  return { root, url, makeAgent, emit, message, api, starts, executions, members,
    set durability(value: boolean) { durability = value; },
    get creates() { return creates; }, get contextReads() { return contextReads; },
    async close() { await emit("dispose"); await new Promise<void>(resolve => owner.close(() => resolve())); await rm(root, { recursive: true, force: true }); },
  };
}

test("browser root presets create from an unbound chat and attach execution systems only to the bound destination", async () => {
  const f = await hostFixture();
  try {
    for (const preset of ["focused", "goal", "orchestrated"]) {
      const original = `Create a new spec document for a 3-bit comparator (${preset}) with A[2:0], B[2:0], and one-bit A_greater, A_equal, A_less.`;
      const origin = await f.makeAgent(`origin-${preset}`, preset);
      assert.match(origin.sections.get("spec2gds:unbound-session").text, /Do not read get_bound_context first/,
        "The complete unbound prompt must retain the creation instructions");
      assert.match(origin.sections.get("spec2gds:unbound-session").text, /ARCHITECTURE AND IMPLEMENTATION AUTHORITY/);
      assert.match(origin.sections.get("spec2gds:unbound-session").text, /components=\[\{name,purpose\}\]/);
      await f.message(origin.id, original);
      assert.equal(f.executions.has(origin.id), false);
      const review = (await origin.tools.get("prepare_architecture_review").execute(architecturePlan, { callId: `arch-${preset}` })).architecture_review;
      assert.equal((await f.api(`/architecture-reviews/${review.reviewId}/approve`, {})).status, 200);
      const prepared = await origin.tools.get("prepare_spec_document_creation").execute({ architecture_review_id: review.reviewId, title: `Comparator ${preset}` }, { callId: `call-${preset}` });
      const request = prepared.source_creation;
      assert.equal(request.originalRequest, original);
      assert.equal(f.executions.has(origin.id), false);
      const created = await f.api("/sources/create", { domain: "spec", creationRequestId: request.requestId,
        documentId: request.documentId, title: request.title, serviceBaseUrl: request.serviceBaseUrl });
      assert.equal(created.status, 201, JSON.stringify(created.value));
      assert.equal(created.value.session.preset, preset);
      const destination = await f.makeAgent(created.value.session.sessionId, preset);
      await f.api(`/bindings/${destination.id}/activate`, {});
      await f.message(destination.id, created.value.continuation.message);
      assert.equal(f.executions.has(destination.id), preset !== "focused");
      await destination.tools.get("get_bound_context").execute({}, { signal: new AbortController().signal });
      assert.equal(f.executions.has(destination.id), preset !== "focused");
      assert.equal(f.executions.has(origin.id), false);
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

test("bound creation checks architecture freshness while preserving the original binding and execution", async () => {
  const f = await hostFixture();
  try {
    const existing = await f.api("/sources/create", { domain: "spec", serviceBaseUrl: f.url, documentId: "original", title: "Original", preset: "goal" });
    assert.equal(existing.status, 201);
    const origin = await f.makeAgent(existing.value.session.sessionId, "goal");
    await f.api(`/bindings/${origin.id}/activate`, {});
    f.executions.get(origin.id).status = "paused";
    const reviewResult = await origin.tools.get("prepare_architecture_review").execute(architecturePlan, { callId: "arch-bound" });
    assert.ok(reviewResult.architecture_review, JSON.stringify(reviewResult));
    const review = reviewResult.architecture_review;
    assert.equal((await f.api(`/architecture-reviews/${review.reviewId}/approve`, {})).status, 200);
    const reads = f.contextReads;
    await f.message(origin.id, "Create a new spec document for a comparator");
    const request = (await origin.tools.get("prepare_spec_document_creation").execute({ document_id: "comparator", title: "Comparator", architecture_review_id: review.reviewId }, { callId: "bound-create" })).source_creation;
    assert.equal(f.contextReads, reads + 1, "Verify the approved architecture's source revision before package creation");
    assert.equal(f.executions.get(origin.id).status, "paused", "Creation must not rearm the source conversation");
    assert.equal((await f.api("/sources/create", { domain: "spec", creationRequestId: request.requestId,
      documentId: request.documentId, title: request.title, serviceBaseUrl: f.url })).status, 201);
    const unchanged = await f.api(`/bindings/${origin.id}`);
    assert.equal(unchanged.value.session.documentId, "original");
    assert.equal(unchanged.value.session.workspaceKey, existing.value.session.workspaceKey);
    assert.equal(f.executions.get(origin.id).status, "paused");
    assert.equal((await f.api(`/source-requests/${request.requestId}`, undefined, "http://evil")).status, 403);
  } finally { await f.close(); }
});

test("headless and specialist agents do not acquire the creation tool", async () => {
  const headless = await hostFixture(false); const web = await hostFixture();
  try {
    const unbound = await headless.makeAgent("headless");
    assert.equal(unbound.tools.has("prepare_spec_document_creation"), false);
    const source = await web.api("/sources/create", { domain: "spec", serviceBaseUrl: web.url, documentId: "parent", title: "Parent", preset: "orchestrated" });
    const parent = await web.makeAgent(source.value.session.sessionId, "orchestrated");
    await web.api(`/bindings/${parent.id}/activate`, {});
    await web.message(parent.id, "Inspect the bound specification");
    await parent.tools.get("get_bound_context").execute({}, { signal: new AbortController().signal });
    web.members.set("child", { conversationId: parent.id, member: "analyst", primary: false });
    const child = await web.makeAgent("child", "focused");
    assert.equal(child.tools.has("prepare_spec_document_creation"), false);
    assert.equal(child.tools.has("get_bound_context"), true);
  } finally { await headless.close(); await web.close(); }
});


test("legacy conversations retain history and cannot run the model or domain tools", async () => {
  const f = await hostFixture(true, ["legacy"]);
  try {
    const agent = await f.makeAgent("legacy");
    assert.equal(agent.tools.size, 0);
    let entered = false;
    await assert.rejects(f.emit("agent/pre-step", { agent, turn: 1, step: 1 }, async () => { entered = true; }), /Start a new bound conversation/);
    assert.equal(entered, false);
    await assert.rejects(f.emit("agent/request", { agent, turn: 1, step: 1 }, async () => ({})), /Start a new conversation/);
    const fresh = await f.makeAgent("fresh");
    assert.ok(fresh.tools.has("prepare_architecture_review"));
  } finally { await f.close(); }
});


test("unbound optional lookups and scoped review lookups preserve error detection", async () => {
  const f = await hostFixture();
  try {
    await f.makeAgent("unbound");
    assert.equal((await f.api("/bindings/unbound?optional=true")).status, 200);
    assert.equal((await f.api("/bindings/unbound?optional=true")).value.session, null);
    assert.equal((await f.api("/bindings/unbound")).status, 404);
    assert.equal((await f.api("/bindings/missing?optional=true")).status, 404);
    assert.equal((await f.api("/bindings/unbound/reviews/missing")).status, 404);
  } finally { await f.close(); }
});

test("architecture continuation retries queue one structured readable native message", async () => {
  const f = await hostFixture();
  try {
    const agent = await f.makeAgent("decision");
    await f.message("decision", "Original designer request");
    const prepared = await agent.tools.get("prepare_architecture_review").execute(architecturePlan, { callId: "review" });
    const id = prepared.architecture_review.reviewId;
    const decided = await f.api(`/architecture-reviews/${id}/revise`, { feedback: "Use active-low reset" });
    assert.equal(decided.status, 200);
    assert.equal(decided.value.continuation.architecture_review_id, id);
    assert.equal((await f.api(`/architecture-reviews/${id}/continue`, { sessionId: "foreign" })).status, 409);
    f.durability = false;
    assert.equal((await f.api(`/architecture-reviews/${id}/continue`, { sessionId: "decision" })).status, 409);
    assert.equal(agent.events.length, 0);
    assert.equal((await f.api(`/architecture-reviews/${id}`)).value.architecture_review.continuationSent, false);
    f.durability = true;
    const followup = agent.followup;
    agent.followup = () => { throw new Error("Temporary native delivery failure"); };
    assert.equal((await f.api(`/architecture-reviews/${id}/continue`, { sessionId: "decision" })).status, 409);
    agent.followup = followup;
    assert.equal((await f.api(`/architecture-reviews/${id}/continue`, { sessionId: "decision" })).status, 200);
    assert.equal((await f.api(`/architecture-reviews/${id}/continue`, { sessionId: "decision" })).status, 200);
    assert.equal(agent.events.length, 1);
    const message = agent.events[0].data.inserted[0];
    assert.equal(message.source.form, "notice");
    assert.match(message.source.summary, /revised/);
    assert.deepEqual(JSON.parse(message.content[0].text), { kind: "architecture_decision", architecture_review_id: id, decision: "revised", feedback: "Use active-low reset" });
  } finally { await f.close(); }
});
