import { afterEach, describe, expect, it } from "vitest";
import { MemoryCircuitDesignerBackend } from "@spec2gds/circuit-client-local";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";
import { CircuitDesignerService } from "../src/server";

let service: CircuitDesignerService | undefined;

afterEach(async () => {
  await service?.close();
  service = undefined;
});

describe("Circuit Designer REST service", () => {
  it("creates, reads, commits, and maps revision conflicts", async () => {
    const backend = new MemoryCircuitDesignerBackend();
    service = new CircuitDesignerService({ backend });
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;
    const document = simpleDocumentFixture();

    const created = await fetch(`${base}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: "create_1", document }),
    });
    expect(created.status).toBe(200);
    const snapshot = await (await fetch(`${base}/documents/fixture_simple`)).json() as { revision: string };
    expect(snapshot.revision).toBe("1");

    const conflict = await fetch(`${base}/documents/fixture_simple/operations/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batch: {
          request_id: "move_1",
          expected_revision: "stale",
          operations: [{
            operation_id: "move",
            type: "set_instance_geometry",
            instance_id: "producer_0",
            geometry: { x: 10, y: 10, width: 180, height: 100 },
          }],
        },
      }),
    });
    expect(conflict.status).toBe(409);
    expect((await conflict.json() as { status: string }).status).toBe("conflict");
  });

  it("maps manual lock conflicts to HTTP 423", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    service = new CircuitDesignerService({ backend });
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple`;
    const lease = await (await fetch(`${base}/lock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner_id: "canvas" }),
    })).json() as { lease_id: string };
    expect(lease.lease_id).toBeTruthy();

    const locked = await fetch(`${base}/operations/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batch: {
          request_id: "move_1",
          expected_revision: "1",
          operations: [{
            operation_id: "move",
            type: "set_instance_geometry",
            instance_id: "producer_0",
            geometry: { x: 10, y: 10, width: 180, height: 100 },
          }],
        },
      }),
    });
    expect(locked.status).toBe(423);
  });

  it("rejects non-loopback provider callbacks by default", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    service = new CircuitDesignerService({ backend });
    const port = await service.listen();
    const response = await fetch(
      `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple/provider`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ callback_url: "https://provider.example/child" }),
      },
    );
    expect(response.status).toBe(400);
    expect((await response.json() as { message: string }).message).toContain("not loopback");
  });

  it("exports a deterministic PNG from canonical geometry", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    service = new CircuitDesignerService({ backend });
    const port = await service.listen();
    const response = await fetch(
      `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple/exports`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: "png" }),
      },
    );
    expect(response.headers.get("Content-Type")).toBe("image/png");
    expect([...new Uint8Array(await response.arrayBuffer()).slice(0, 8)])
      .toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  });
});
