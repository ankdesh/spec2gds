import { serveIntegrationMetadata } from "./support/integration-metadata.mjs";
import { approvedArchitecture } from "./support/architecture.js";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { ServiceClients } from "../src/service-clients.js";
import { ProductState } from "../src/state.js";
import { creationContinuation, registerSourceCreationTool, SourceCreations, specDestination } from "../src/source-creation.js";
import type { BindingInput, SourceCreationRequest } from "../src/types.js";

const comparatorRequest = `Create a new spec document for comparator_3bit. Compare unsigned A[2:0] and B[2:0] using combinational logic. A_greater, A_equal, and A_less are one-bit, mutually exclusive outputs for A > B, A == B, and A < B.`;

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-source-creation-"));
  const database = join(root, "state.sqlite3");
  let state = new ProductState(database);
  const paths: string[] = [];
  let creates = 0;
  let creationReceipts = false;
  const receipts = new Map<string, { body: string; snapshot: Record<string, unknown> }>();
  let approvalPolicy: "automatic" | "review" = "review";
  let reservationFailure = false;
  let mode: "normal" | "reject" | "drop" | "invalid" | "offline" = "normal";
  let creationGate: Promise<void> | undefined;
  const server = createServer(async (request, response) => {
    if (serveIntegrationMetadata(request, response)) return;
    paths.push(`${request.method} ${request.url}`);
    if (request.url === "/assistant/capabilities") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ approval_policy: approvalPolicy, submission_endpoint: "/assistant/proposals/submit", creation_receipts: creationReceipts }));
      return;
    }
    if (request.url === "/health") {
      response.writeHead(mode === "offline" ? 503 : 200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ status: "ok" }));
      return;
    }
    if (request.url !== "/documents/create") { response.writeHead(400); response.end('{"detail":"No V1 .spec package is open."}'); return; }
    let raw = ""; for await (const chunk of request) raw += chunk;
    const body = JSON.parse(raw);
    creates += 1;
    await creationGate;
    const receipt = creationReceipts ? receipts.get(body.request_id) : undefined;
    if (receipt) {
      response.writeHead(receipt.body === raw ? 200 : 409, { "Content-Type": "application/json" });
      response.end(JSON.stringify(receipt.body === raw ? receipt.snapshot : { detail: "Changed creation input" }));
      return;
    }
    if (mode === "reject") { response.writeHead(422, { "Content-Type": "application/json" }); response.end('{"detail":"Existing package"}'); return; }
    try { await writeFile(body.path, body.document_id, { flag: "wx" }); }
    catch { response.writeHead(422, { "Content-Type": "application/json" }); response.end('{"detail":"Refusing to replace existing package"}'); return; }
    const snapshot = { document_id: body.document_id, source_revision_hash: "sha256:created", owner_document_key: "created-package" };
    if (creationReceipts) receipts.set(body.request_id, { body: raw, snapshot });
    if (mode === "drop") { request.socket.destroy(); return; }
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(mode === "invalid" ? "not JSON" : JSON.stringify(snapshot));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); assert.ok(address && typeof address === "object");
  const url = `http://127.0.0.1:${address.port}`;
  const owners = new ServiceClients([url], [], 1_000);
  const reserve = async (input: BindingInput, sessionId = "unused") => {
    if (reservationFailure) throw new Error("Simulated chat setup failure");
    const workspace = { key: input.documentId, title: input.title!, path: join(root, "workspace", input.documentId), domain: "spec" as const, serviceUrl: url, documentId: input.documentId };
    const binding = state.createBinding(sessionId, { ...input, serviceUrl: url,
      workspaceKey: workspace.key, workspaceTitle: workspace.title, workspacePath: workspace.path,
      workspaceDomain: workspace.domain, workspaceServiceUrl: url, workspaceDocumentId: input.documentId });
    return { binding, workspace };
  };
  approvedArchitecture(state, "unbound-chat", comparatorRequest);
  approvedArchitecture(state, "chat", comparatorRequest);
  approvedArchitecture(state, "bound-chat", comparatorRequest);
  let creations = new SourceCreations(state, owners, root, reserve);
  const prepare = async (callId = "create-call", originalRequest = comparatorRequest) =>
    await creations.prepare({ sourceSessionId: "unbound-chat", callId, originalRequest, preset: "focused", title: "3-bit comparator", documentId: "comparator_3bit", architectureReviewId: "architecture-unbound-chat" }) as unknown as SourceCreationRequest;
  const values = { documentId: "comparator_3bit", title: "3-bit comparator", serviceBaseUrl: url };
  return { root, url, owners, paths, values, prepare,
    get state() { return state; }, get creations() { return creations; }, get creates() { return creates; },
    set mode(value: typeof mode) { mode = value; }, set reservationFailure(value: boolean) { reservationFailure = value; },
    set gate(value: Promise<void> | undefined) { creationGate = value; },
    set approvalPolicy(value: "automatic" | "review") { approvalPolicy = value; },
    set creationReceipts(value: boolean) { creationReceipts = value; },
    reopen() { state.close(); state = new ProductState(database); creations = new SourceCreations(state, owners, root, reserve); },
    async close() { state.close(); await new Promise<void>(resolve => server.close(() => resolve())); await rm(root, { recursive: true, force: true }); },
  };
}

test("unbound creation stages a durable card without accessing bound context or creating a package", async () => {
  const f = await fixture();
  try {
    const request = await f.prepare();
    assert.equal(f.creates, 0);
    assert.ok(f.paths.every(path => ["GET /health", "GET /assistant/capabilities"].includes(path)));
    assert.equal(f.state.getBinding("unbound-chat"), null);
    assert.equal((await f.prepare()).requestId, request.requestId, "Repeated tool execution reuses its receipt");
    f.reopen();
    assert.equal(f.creations.get(request.requestId).originalRequest, comparatorRequest);
    const result = await f.creations.create(request.requestId, f.values) as any;
    assert.equal(f.creates, 1);
    assert.equal(await readFile(join(f.root, "3-bit-comparator.spec"), "utf8"), "comparator_3bit");
    assert.equal(result.session.scope, "document");
    assert.notEqual(result.session.sessionId, "unbound-chat");
    assert.ok(result.continuation.message.includes(comparatorRequest));
    assert.match(result.continuation.message, /Do not create another Spec/);
    assert.equal(f.state.getBinding("unbound-chat"), null);
    f.state.activateBinding(result.session.sessionId);
    f.creations.continued(request.requestId);
    f.reopen();
    const replay = await f.creations.create(request.requestId, f.values) as any;
    assert.equal(f.creates, 1);
    assert.equal(replay.session.sessionId, result.session.sessionId);
    assert.equal(replay.continuation.requestId, result.continuation.requestId);
    assert.equal(replay.continuation.sent, true);
  } finally { await f.close(); }
});

test("known creation success survives a failed reservation and retries only chat setup", async () => {
  const f = await fixture();
  try {
    const request = await f.prepare(); f.reservationFailure = true;
    await assert.rejects(f.creations.create(request.requestId, f.values), /chat setup failure/);
    assert.equal(f.creations.get(request.requestId).status, "created");
    assert.match(f.creations.get(request.requestId).error!, /package was saved/);
    f.reopen(); f.reservationFailure = false;
    const result = await f.creations.create(request.requestId, f.values) as any;
    assert.equal(result.session.sessionId, request.destinationSessionId);
    assert.equal(f.creates, 1);
    await assert.rejects(f.creations.create(request.requestId, { ...f.values, title: "Different" }), /already saved/);
  } finally { await f.close(); }
});

test("simultaneous card submissions create one package and preserve one chat identity", async () => {
  const f = await fixture();
  let release!: () => void;
  try {
    f.gate = new Promise<void>(resolve => { release = resolve; });
    const request = await f.prepare();
    const first = f.creations.create(request.requestId, f.values);
    while (f.creates === 0) await new Promise(resolve => setImmediate(resolve));
    await assert.rejects(f.creations.create(request.requestId, f.values), /creating/);
    release(); await first;
    assert.equal(f.creates, 1);
  } finally { release?.(); await f.close(); }
});

test("new tool-call IDs sharing an approved architecture retain one creation receipt", async () => {
  const f = await fixture();
  try {
    const [first, retry] = await Promise.all([f.prepare("first-call"), f.prepare("retry-call")]);
    assert.equal(first.requestId, retry.requestId);
    await f.creations.create(first.requestId, f.values);
    const destination = f.creations.get(first.requestId).destinationSessionId;
    f.reopen();
    const replay = await f.prepare("another-call");
    assert.equal(replay.requestId, first.requestId);
    assert.equal(replay.destinationSessionId, destination);
    assert.equal(f.creates, 1);
  } finally { await f.close(); }
});

test("a source revision change while a creation card is pending requires renewed architecture approval", async () => {
  const f = await fixture();
  try {
    f.state.createBinding("source", { domain: "spec", serviceBaseUrl: f.url, serviceUrl: f.url, documentId: "source-doc", scope: "document",
      serviceDocumentKey: "source-package", workspaceKey: "source", workspaceTitle: "Source", workspacePath: f.root,
      workspaceDomain: "spec", workspaceServiceUrl: f.url, workspaceDocumentId: "source-doc" });
    const reviewId = approvedArchitecture(f.state, "source", comparatorRequest, "sha256:old");
    let revision = "sha256:old";
    f.owners.context = async () => ({ document_id: "source-doc", source_revision_hash: revision });
    const request = await f.creations.prepare({ sourceSessionId: "source", callId: "new-package", originalRequest: comparatorRequest,
      preset: "focused", title: "Comparator", documentId: "comparator_3bit", architectureReviewId: reviewId });
    revision = "sha256:new";
    await assert.rejects(f.creations.create(String(request.requestId), f.values), /stale/);
    assert.equal(f.creates, 0);
  } finally { await f.close(); }
});

test("cancelled and invalid requests never write packages", async () => {
  const f = await fixture();
  try {
    const request = await f.prepare();
    for (const documentId of ["../escape", "bad/name", "", "x".repeat(129)]) {
      await assert.rejects(f.creations.create(request.requestId, { ...f.values, documentId }), /Document ID/);
    }
    await assert.rejects(f.creations.create(request.requestId, { ...f.values, title: " " }), /title/);
    await assert.rejects(f.creations.create(request.requestId, { ...f.values, serviceBaseUrl: "http://127.0.0.1:9" }), /allowlist/i);
    f.creations.cancel(request.requestId); f.reopen();
    await assert.rejects(f.creations.create(request.requestId, f.values), /cancelled/);
    assert.equal(f.creates, 0);
  } finally { await f.close(); }
});

test("owner rejection and offline services leave an editable request; existing files remain intact", async () => {
  const f = await fixture();
  try {
    const request = await f.prepare();
    f.mode = "offline";
    await assert.rejects(f.creations.create(request.requestId, f.values), /offline/);
    assert.equal(f.creates, 0); assert.equal(f.creations.get(request.requestId).status, "pending");
    f.mode = "normal";
    await writeFile(join(f.root, "3-bit-comparator.spec"), "original");
    await assert.rejects(f.creations.create(request.requestId, f.values), /Refusing to replace/);
    assert.equal(await readFile(join(f.root, "3-bit-comparator.spec"), "utf8"), "original");
    assert.equal(f.creations.get(request.requestId).status, "pending");
    await f.creations.create(request.requestId, { ...f.values, title: "3-bit comparator new" });
    assert.equal(f.creations.get(request.requestId).status, "reserved");
  } finally { await f.close(); }
});

for (const mode of ["drop", "invalid"] as const) {
  test(`an ambiguous ${mode} owner response is never automatically repeated`, async () => {
    const f = await fixture();
    try {
      const request = await f.prepare(); f.mode = mode;
      await assert.rejects(f.creations.create(request.requestId, f.values));
      assert.equal(f.creations.get(request.requestId).status, "uncertain");
      assert.equal(await readFile(request.destination, "utf8"), request.documentId);
      f.reopen(); f.mode = "normal";
      await assert.rejects(f.creations.create(request.requestId, f.values), /will not be repeated automatically/);
      assert.equal(f.creates, 1);
    } finally { await f.close(); }
  });
}

test("restart converts an interrupted owner mutation into uncertain creation", async () => {
  const f = await fixture();
  try {
    const request = await f.prepare(); assert.equal(f.state.claimSourceCreation(request), true);
    f.reopen(); f.state.recoverInterruptedSourceCreations();
    assert.equal(f.creations.get(request.requestId).status, "uncertain");
    await assert.rejects(f.creations.create(request.requestId, f.values), /interrupted/);
    assert.equal(f.creates, 0);
  } finally { await f.close(); }
});

test("receipt-capable owners recover a lost creation response after restart", async () => {
  const f = await fixture();
  try {
    f.creationReceipts = true;
    const request = await f.prepare();
    f.mode = "drop";
    await assert.rejects(f.creations.create(request.requestId, f.values));
    assert.equal(f.creations.get(request.requestId).status, "uncertain");
    const saved = await readFile(request.destination);
    f.reopen(); f.mode = "normal";
    await assert.rejects(f.creations.create(request.requestId, { ...f.values, title: "Changed" }), /exactly/);
    const result = await f.creations.create(request.requestId, f.values) as any;
    assert.equal(result.session.serviceDocumentKey, "created-package");
    assert.equal(result.session.sessionId, request.destinationSessionId);
    assert.deepEqual(await readFile(request.destination), saved);
    assert.equal(f.creates, 2, "One original request and one receipt replay");
    await f.creations.create(request.requestId, f.values);
    assert.equal(f.creates, 2);
  } finally { await f.close(); }
});

test("available owner selection supports a preferred Spec service and multiple configured services", async () => {
  const f = await fixture(); const second = await fixture();
  try {
    f.owners.specAllowlist.unshift("http://127.0.0.1:9"); f.owners.specAllowlist.push(second.url);
    const defaulted = await f.prepare() as any;
    assert.equal(defaulted.serviceBaseUrl, f.url); assert.equal(defaulted.services.length, 3);
    const preferred = await f.creations.prepare({ sourceSessionId: "bound-chat", callId: "second", originalRequest: comparatorRequest,
      preset: "orchestrated", preferredOwner: second.url, architectureReviewId: "architecture-bound-chat" });
    assert.equal(preferred.serviceBaseUrl, second.url); assert.equal(preferred.preset, "orchestrated");
  } finally { await f.close(); await second.close(); }
});

test("model tool captures the host request and supplies safe empty-spec defaults", async () => {
  const f = await fixture();
  try {
    let tool: any;
    const sections: any[] = [];
    registerSourceCreationTool({ ctx: { tools: { register: value => { tool = value; return () => {}; } }, systemPrompt: { section: value => { sections.push(value); return () => {}; } } } }, f.creations,
      () => ({ sourceSessionId: "chat", originalRequest: "Create an empty specification", preset: "focused" }));
    const result = await tool.execute({ empty: true }, { callId: "empty-call" });
    assert.equal(tool.name, "prepare_spec_document_creation");
    assert.match(result.source_creation.documentId, /^spec_[a-f0-9]{32}$/);
    assert.equal(f.creates, 0);
    assert.match(sections[0].text, /Do not read get_bound_context first/);
    assert.match(creationContinuation(result.source_creation), /only asked for an empty Spec/);
    assert.throws(() => specDestination(f.root, "../escape"), /Document ID/);
  } finally { await f.close(); }
});

test("automatic creation returns a saved receipt and continuation with no confirmation", async () => {
  const f = await fixture();
  try {
    f.approvalPolicy = "automatic";
    let tool: any;
    registerSourceCreationTool({ ctx: { tools: { register: value => { tool = value; return () => {}; } } } }, f.creations,
      () => ({ sourceSessionId: "chat", originalRequest: comparatorRequest, preset: "focused" }));
    const invalid = await tool.execute({ document_id: "not a valid ID", title: "3-bit comparator", architecture_review_id: "architecture-chat" }, { callId: "invalid-id" });
    assert.match(invalid.creation_error, /Document ID/);
    assert.equal(f.creates, 0);
    const result = await tool.execute({ document_id: "comparator_3bit", title: "3-bit comparator", architecture_review_id: "architecture-chat" }, { callId: "automatic-call" });
    assert.ok(result.source_creation, JSON.stringify(result));
    assert.equal(result.source_creation.status, "reserved");
    assert.equal(result.source_creation.automatic, true);
    assert.equal(result.source_creation.documentId, "comparator_3bit");
    assert.equal(result.source_creation.title, "3-bit comparator");
    assert.equal(result.source_creation.destination, join(f.root, "3-bit-comparator.spec"));
    assert.equal(f.creates, 1);
    assert.ok(result.source_creation.continuation.message.includes(comparatorRequest));
    const retry = await tool.execute({}, { callId: "automatic-call" });
    assert.equal(retry.source_creation.requestId, result.source_creation.requestId);
    assert.equal(f.creates, 1);
  } finally { await f.close(); }
});
