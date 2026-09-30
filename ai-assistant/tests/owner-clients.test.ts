import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { once } from "node:events";
import { OwnerClients, normalizeCircuitUrl, normalizeSpecUrl } from "../src/owner-clients.js";
import type { SessionBinding } from "../src/types.js";

test("owner URLs require exact configured origins", () => {
  assert.equal(normalizeSpecUrl("http://127.0.0.1:6010/", ["http://127.0.0.1:6010"]), "http://127.0.0.1:6010");
  assert.throws(() => normalizeSpecUrl("http://127.0.0.1:6010/other", ["http://127.0.0.1:6010"]), /only scheme/);
  assert.equal(
    normalizeCircuitUrl("http://localhost:6011/api/circuit-designer/v1/", ["http://localhost:6011/api/circuit-designer/v1"]),
    "http://localhost:6011/api/circuit-designer/v1",
  );
  assert.throws(() => normalizeCircuitUrl("http://localhost:6011/api/circuit-designer/v2", ["http://localhost:6011/api/circuit-designer/v1"]), /must end/);
});

test("Spec policy discovery is explicit and bound requests carry the package key", async () => {
  const urls: URL[] = [];
  let policy: unknown = "automatic";
  let status = 200;
  const server = createServer((request, response) => {
    const url = new URL(request.url!, "http://localhost"); urls.push(url);
    response.writeHead(status, { "Content-Type": "application/json" });
    response.end(JSON.stringify(url.pathname === "/assistant/capabilities"
      ? { approval_policy: policy, submission_endpoint: "/assistant/proposals/submit" }
      : { document_id: "same-id", status: "applied", source_revision_hash: "sha256:saved" }));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); assert.ok(address && typeof address === "object");
  const ownerUrl = `http://127.0.0.1:${address.port}`;
  const clients = new OwnerClients([ownerUrl], [], 5_000);
  const binding = { domain: "spec", ownerUrl, documentId: "same-id", ownerDocumentKey: "package-A", scope: "document", sessionId: "chat" } as SessionBinding;
  try {
    assert.deepEqual(await clients.specPolicy(ownerUrl), { approval_policy: "automatic", submissions: true });
    await clients.context(binding);
    await clients.submitSpec(binding, {});
    assert.ok(urls.filter(url => url.pathname !== "/assistant/capabilities").every(url => url.searchParams.get("owner_document_key") === "package-A"));
    assert.equal(urls.at(-1)!.searchParams.get("session_id"), "chat");
    policy = undefined;
    await assert.rejects(clients.specPolicy(ownerUrl), /valid approval policy/);
    status = 404;
    assert.deepEqual(await clients.specPolicy(ownerUrl), { approval_policy: "review", submissions: false });
    status = 503;
    await assert.rejects(clients.specPolicy(ownerUrl));
  } finally { await new Promise<void>(resolve => server.close(() => resolve())); }
});

test("Spec target discovery uses canonical entity references", async () => {
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({
      document_id: "doc-1",
      narrative: { title: "Demo specification" },
      components: [{ ref: { entity_id: "component-1" }, vlnv: "acme:demo:component:1.0" }],
      designs: [{ ref: { entity_id: "design-1" }, vlnv: "acme:demo:design:1.0" }],
      bus_definitions: [], abstraction_definitions: [],
    }));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const ownerUrl = `http://127.0.0.1:${address.port}`;
  try {
    const targets = await new OwnerClients([ownerUrl], [], 5_000).targets("spec", ownerUrl);
    assert.deepEqual(targets.document, { document_id: "doc-1", title: "Demo specification" });
    assert.deepEqual(targets.entities, [
      { document_id: "doc-1", entity_id: "component-1", entity_kind: "component", title: "acme:demo:component:1.0" },
      { document_id: "doc-1", entity_id: "design-1", entity_kind: "design", title: "acme:demo:design:1.0" },
    ]);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});

test("Circuit client uses the public snapshot, preview, and proposal routes", async () => {
  const requests: Array<{ method: string; path: string; body?: Record<string, unknown> }> = [];
  const server = createServer(async (request, response) => {
    const path = new URL(request.url ?? "/", "http://localhost").pathname;
    let body: Record<string, unknown> | undefined;
    if (request.method === "POST") {
      let raw = ""; for await (const chunk of request) raw += chunk;
      body = JSON.parse(raw) as Record<string, unknown>;
    }
    requests.push({ method: request.method ?? "", path, ...(body ? { body } : {}) });
    if (request.method === "POST" && path.endsWith("/exports")) {
      response.writeHead(200, { "Content-Type": "image/svg+xml" });
      response.end('<svg viewBox="0 0 10 10"></svg>');
      return;
    }
    const value = request.method === "GET" && path.endsWith("/documents/doc-1")
      ? { revision: "rev-1", document: { document_id: "doc-1" } }
      : request.method === "POST" && path.endsWith("/operations/preview")
        ? { status: "accepted", diagnostics: [], diff: {}, alias_map: {} }
        : request.method === "POST" && path.endsWith("/proposals")
          ? { proposal_id: "proposal-1", status: "pending" }
          : request.method === "GET" && path.endsWith("/proposals")
            ? { proposals: [{ proposal_id: "proposal-1", status: "pending" }] }
            : null;
    response.writeHead(value ? 200 : 404, { "Content-Type": "application/json" });
    response.end(JSON.stringify(value ?? { detail: "not found" }));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const ownerUrl = `http://127.0.0.1:${address.port}/api/circuit-designer/v1`;
  const clients = new OwnerClients([], [ownerUrl], 5_000);
  const binding: SessionBinding = {
    sessionId: "session-1", status: "active", preset: "focused", domain: "circuit", ownerUrl,
    documentId: "doc-1", scope: "document", entityKind: null, entityId: null,
    title: "Circuit: doc-1", archived: false, createdAt: "", updatedAt: "",
    workspaceKey: "test", workspaceTitle: "Test", workspacePath: "/tmp/test",
    workspaceDomain: "circuit", workspaceOwnerUrl: ownerUrl, workspaceDocumentId: "doc-1",
  };
  try {
    assert.equal((await clients.context(binding)).revision, "rev-1");
    assert.match(await clients.circuitSvg(binding), /viewBox/);
    const batch = { request_id: "request-1", expected_revision: "rev-1", operations: [{ operation_id: "op-1", type: "delete_net", net_id: "net-1" }] };
    assert.equal((await clients.previewCircuit(binding, batch)).status, "accepted");
    assert.equal((await clients.sendCircuit(binding, {
      proposal_id: "proposal-1", document_id: "doc-1", base_revision: "rev-1",
      title: "Delete net", summary: "Deletes a net.", rationale: "Unused.", assumptions: [], batch,
    })).status, "pending");
    assert.equal((await clients.circuitProposals(binding)).proposals instanceof Array, true);
    assert.deepEqual(requests.map(item => `${item.method} ${item.path}`), [
      "GET /api/circuit-designer/v1/documents/doc-1",
      "POST /api/circuit-designer/v1/documents/doc-1/exports",
      "POST /api/circuit-designer/v1/documents/doc-1/operations/preview",
      "POST /api/circuit-designer/v1/documents/doc-1/proposals",
      "GET /api/circuit-designer/v1/documents/doc-1/proposals",
    ]);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});

test("fetches binding-specific owner operation contracts and reports retrieval failures", async () => {
  const paths: string[] = [];
  let available = true;
  const server = createServer((request, response) => {
    paths.push(request.url ?? "");
    response.writeHead(available ? 200 : 503, { "Content-Type": "application/json" });
    response.end(JSON.stringify(available
      ? { schema_version: 1, digest: `sha256:${"a".repeat(64)}`, operation_schema: {
        $schema: "https://json-schema.org/draft/2020-12/schema", oneOf: [],
      } }
      : { detail: "schema unavailable" }));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const ownerUrl = `http://127.0.0.1:${address.port}`;
  const clients = new OwnerClients([ownerUrl], [], 5_000);
  const binding: SessionBinding = {
    sessionId: "session-1", status: "active", preset: "focused", domain: "spec", ownerUrl,
    documentId: "doc-1", scope: "entity", entityKind: "component", entityId: "component-1",
    title: "Spec", archived: false, createdAt: "", updatedAt: "",
    workspaceKey: "test", workspaceTitle: "Test", workspacePath: "/tmp/test",
    workspaceDomain: "spec", workspaceOwnerUrl: ownerUrl, workspaceDocumentId: "doc-1",
  };
  try {
    assert.equal((await clients.operationContract(binding)).schema_version, 1);
    assert.match(paths[0] ?? "", /document_id=doc-1&scope=entity&entity_kind=component&entity_id=component-1/);
    available = false;
    await assert.rejects(() => clients.operationContract(binding), /schema unavailable/);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});
