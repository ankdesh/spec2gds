import { EventEmitter } from "node:events";
import { Readable } from "node:stream";
import { afterEach, expect, it, vi } from "vitest";
import { createEmptyCircuitDocument, type CircuitSourceBindingV1 } from "@spec2gds/circuit-core";
import { CircuitDesignerService } from "../src/server";
import { EphemeralCircuitSessionBackend } from "../src/session-backend";

afterEach(() => vi.unstubAllGlobals());

async function fixture() {
  const preview = createEmptyCircuitDocument("blank_component");
  const backend = new EphemeralCircuitSessionBackend({ documents: [preview] });
  const service = new CircuitDesignerService({ backend });
  // Exercise the normal HTTP route and per-document gate without opening ports.
  const send = (path: string, body: unknown = {}, method = "POST") => new Promise<{ status: number; body: any }>(resolve => {
    const request = Object.assign(Readable.from([Buffer.from(JSON.stringify(body))]), {
      method, url: `/api/circuit-designer/v1/documents/blank_component${path}`, headers: {},
    });
    const response = Object.assign(new EventEmitter(), {
      statusCode: 200, setHeader: () => undefined,
      end(value: string) { response.emit("finish"); resolve({ status: response.statusCode, body: JSON.parse(value) }); },
    });
    service.server.emit("request", request, response);
  });
  const binding: CircuitSourceBindingV1 = { schema_version: 1, binding_id: "blank", source_document_id: "spec",
    source_entity: { document_id: "spec", entity_kind: "component", entity_id: "component" },
    base_source_revision_hash: "base", writable: false, capabilities: ["create-internal-design"],
    omitted_bus_items: [], omitted_ports: [] };
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: URL, init: RequestInit) => {
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer private-token");
    calls++;
    const body = JSON.parse(init.body as string);
    const pending = url.pathname.endsWith("/prepare");
    const isSave = url.pathname.endsWith("/commit") || url.pathname.endsWith("/preview");
    return new Response(JSON.stringify({ accepted: true, source_revision_hash: isSave ? "saved" : "base",
      document: body.candidate_document ?? preview, diagnostics: [], binding: {
        ...binding, writable: pending || isSave, editable_design_id: pending || isSave ? "reserved_design" : undefined,
        pending_internal_design: pending, sv_choice_required: pending,
        capabilities: pending || isSave ? ["topology", "layout"] : ["create-internal-design"],
      } }));
  }));
  expect((await send("/source-binding", { binding, callback_url: "http://127.0.0.1/source/", token: "private-token" }, "PUT")).status).toBe(200);
  return { backend, send, calls: () => calls };
}

it("requires a lease, prepares privately, and replays a transition without rotating the lease twice", async () => {
  const f = await fixture();
  expect((await f.send("/source/internal-design/prepare", { request_id: "prepare", lease_id: "missing" })).status).toBe(423);
  expect(f.calls()).toBe(0);
  const lease = await f.backend.acquireLease("blank_component", "designer");
  const body = { request_id: "prepare", lease_id: lease.lease_id };
  const prepared = await f.send("/source/internal-design/prepare", body);
  expect(prepared.status).toBe(200);
  expect(prepared.body.binding.pending_internal_design).toBe(true);
  expect(prepared.body.lease.lease_id).not.toBe(lease.lease_id);
  expect((await f.send("/source/internal-design/prepare", body)).body).toEqual(prepared.body);
  expect(f.calls()).toBe(1);
  expect((await f.send("/source/internal-design/discard", { request_id: "discard", lease_id: lease.lease_id })).status).toBe(423);
  const discardBody = { request_id: "discard", lease_id: prepared.body.lease.lease_id };
  const discarded = await f.send("/source/internal-design/discard", discardBody);
  expect(discarded.status).toBe(200);
  expect(discarded.body.binding.writable).toBe(false);
  expect(discarded.body.binding.pending_internal_design).toBe(false);
  expect((await f.send("/source/internal-design/discard", discardBody)).body).toEqual(discarded.body);
  expect(f.calls()).toBe(2);
});

it("forwards the SV choice on empty first save and returns one receipt on retry", async () => {
  const f = await fixture();
  const lease = await f.backend.acquireLease("blank_component", "designer");
  const prepared = (await f.send("/source/internal-design/prepare", { request_id: "prepare", lease_id: lease.lease_id })).body;
  const body = { lease_id: prepared.lease.lease_id, sv_disposition: "retain_reference",
    batch: { request_id: "internal-design:prepare:prepare", expected_revision: prepared.snapshot.revision,
      operations: [{ operation_id: "save_layout", type: "set_layout_settings", direction: "RIGHT" }] } };
  const saved = await f.send("/source/commit", body);
  expect(saved.status, JSON.stringify(saved.body)).toBe(200);
  expect(saved.body.binding.pending_internal_design).toBe(false);
  expect(saved.body.binding.editable_design_id).toBe("reserved_design");
  expect(await f.backend.getLease("blank_component")).toBeNull();
  expect((await f.send("/source/commit", body)).body).toEqual(saved.body);
  expect(f.calls()).toBe(3);
  const writes = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith("/preview") || String(url).endsWith("/commit"));
  expect(writes).toHaveLength(2);
  expect(writes.every(([, init]) => JSON.parse(init!.body as string).sv_disposition === "retain_reference")).toBe(true);
});

it("rejects stale transition receipts after another designer takes the lease", async () => {
  const f = await fixture();
  const lease = await f.backend.acquireLease("blank_component", "first");
  const body = { request_id: "prepare", lease_id: lease.lease_id };
  const prepared = (await f.send("/source/internal-design/prepare", body)).body;
  await f.backend.takeOverLease("blank_component", prepared.lease.lease_id, "second");
  expect((await f.send("/source/internal-design/prepare", body)).status).toBeGreaterThanOrEqual(400);
  expect(f.calls()).toBe(1);
});

it("preserves the preview and lease when the provider returns invalid binding metadata", async () => {
  const f = await fixture();
  const lease = await f.backend.acquireLease("blank_component", "designer");
  const before = await f.backend.get("blank_component");
  vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ accepted: true,
    source_revision_hash: "base", document: before.document, diagnostics: [], binding: { writable: true } })));
  const result = await f.send("/source/internal-design/prepare", { request_id: "bad-provider", lease_id: lease.lease_id });
  expect(result.status).toBe(502);
  expect(await f.backend.get("blank_component")).toEqual(before);
  expect(await f.backend.getLease("blank_component")).toEqual(lease);
  expect((await f.send("/source-binding", {}, "GET")).body.writable).toBe(false);
});
