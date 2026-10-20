import { createServer } from "node:http";
import { afterEach, expect, it } from "vitest";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";
import { CircuitDesignerService } from "../src/server";
import { EphemeralCircuitSessionBackend } from "../src/session-backend";

const cleanups: Array<() => Promise<void>> = [];
afterEach(async () => { for (const cleanup of cleanups.splice(0).reverse()) await cleanup(); });

async function fixture() {
  const saved = { document: simpleDocumentFixture(), commits: 0, rejectResolve: false, authorizations: [] as string[] };
  let unblock!: () => void;
  let entered!: () => void;
  const commitEntered = new Promise<void>(resolve => { entered = resolve; });
  const commitGate = new Promise<void>(resolve => { unblock = resolve; });
  let pause = false;
  const provider = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", chunk => chunks.push(chunk));
    request.on("end", () => { void (async () => {
      const body = JSON.parse(Buffer.concat(chunks).toString());
      saved.authorizations.push(String(request.headers.authorization));
      response.setHeader("Content-Type", "application/json");
      if (request.url?.endsWith("/resolve")) {
        response.end(JSON.stringify({ accepted: !saved.rejectResolve, source_revision_hash: "latest",
          document: saved.rejectResolve ? undefined : saved.document, diagnostics: [] }));
        return;
      }
      if (request.url?.endsWith("/commit")) {
        entered();
        if (pause) await commitGate;
        saved.document = body.candidate_document;
        saved.commits += 1;
      }
      response.end(JSON.stringify({ accepted: true, source_revision_hash: "latest", document: body.candidate_document, diagnostics: [] }));
    })(); });
  });
  await new Promise<void>(resolve => provider.listen(0, "127.0.0.1", resolve));
  cleanups.push(() => new Promise<void>((resolve, reject) => { unblock(); provider.close(error => error ? reject(error) : resolve()); }));
  const address = provider.address();
  if (!address || typeof address === "string") throw new Error("Provider has no port");
  const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
  const service = new CircuitDesignerService({ backend });
  const port = await service.listen();
  cleanups.push(() => { unblock(); return service.close(); });
  const base = `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple`;
  const send = (path: string, body: unknown, method = "POST") => fetch(`${base}${path}`, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const registration = {
    callback_url: `http://127.0.0.1:${address.port}/source/`, token: "old-token",
    binding: { schema_version: 1, binding_id: "binding", source_document_id: "spec",
      source_entity: { document_id: "spec", entity_kind: "design", entity_id: "top" },
      editable_design_id: "top", base_source_revision_hash: "base", writable: true,
      capabilities: ["topology"], omitted_bus_items: [], omitted_ports: [] },
  };
  expect((await send("/source-binding", registration, "PUT")).status).toBe(200);
  const lease = await (await send("/lock", { owner_id: "first-tab" })).json();
  const commitBody = { lease_id: lease.lease_id, batch: { expected_revision: "1", request_id: "save", operations: [
    { operation_id: "move", type: "set_instance_geometry", instance_id: "producer_0",
      geometry: { x: 20, y: 40, width: 180, height: 100 } },
  ] } };
  return { base, send, saved, backend, lease, registration, commitBody, commitEntered,
    pauseCommit: () => { pause = true; }, unblock };
}

it("refreshes saved source and conditionally replaces the lease without a source write", async () => {
  const f = await fixture();
  f.saved.document.label = "Latest saved Circuit";
  const response = await f.send("/source/recover", { expected_lease_id: f.lease.lease_id, owner_id: "second-tab" });
  expect(response.status).toBe(200);
  const result = await response.json();
  expect(result.snapshot.document.label).toBe("Latest saved Circuit");
  expect(result.binding.base_source_revision_hash).toBe("latest");
  expect(result.lease.lease_id).not.toBe(f.lease.lease_id);
  expect(f.saved.commits).toBe(0);
  expect((await f.send("/source/commit", f.commitBody)).status).toBe(423);
  expect((await f.send("/source/recover", { expected_lease_id: f.lease.lease_id, owner_id: "third-tab" })).status).toBe(423);
  expect((await f.backend.getLease("fixture_simple"))?.lease_id).toBe(result.lease.lease_id);
});

it("keeps the old lease and binding when source refresh fails", async () => {
  const f = await fixture();
  f.saved.rejectResolve = true;
  const response = await f.send("/source-binding", { ...f.registration, token: "new-token",
    binding: { ...f.registration.binding, binding_id: "replacement" },
    recovery: { expected_lease_id: f.lease.lease_id, owner_id: "second-tab" } }, "PUT");
  expect(response.status).toBe(502);
  expect(await f.backend.getLease("fixture_simple")).toEqual(f.lease);
  expect((await (await fetch(`${f.base}/source-binding`)).json()).binding_id).toBe("binding");
  expect(f.saved.commits).toBe(0);
});

it("re-establishes the callback binding only after confirmed recovery", async () => {
  const f = await fixture();
  const blocked = await f.send("/source-binding", { ...f.registration, token: "new-token" }, "PUT");
  expect(blocked.status).toBe(423);
  expect((await blocked.json()).details.lease.lease_id).toBe(f.lease.lease_id);
  expect(f.saved.authorizations).toEqual([]);
  const recovered = await f.send("/source/recover", { expected_lease_id: f.lease.lease_id, owner_id: "second-tab" });
  expect(recovered.status).toBe(200);
  expect(f.saved.authorizations).toEqual(["Bearer new-token"]);
  expect((await recovered.json()).binding.binding_id).toBe("binding");
});

it("serializes takeover behind a source save already in flight", async () => {
  const f = await fixture();
  f.pauseCommit();
  const saving = f.send("/source/commit", f.commitBody);
  await f.commitEntered;
  const takeover = f.send("/source/recover", { expected_lease_id: f.lease.lease_id, owner_id: "second-tab" });
  expect((await (await fetch(`${f.base}/lock`)).json()).lease.lease_id).toBe(f.lease.lease_id);
  f.unblock();
  expect((await saving).status).toBe(200);
  // Save closed the old lease; confirmation of that former lease cannot now
  // take over an unrelated successor or discard the just-saved source.
  expect((await takeover).status).toBe(423);
  expect(f.saved.commits).toBe(1);
  expect(f.saved.document.layout.instance_geometry.producer_0.x).toBe(20);
});
