import { describe, expect, test, vi } from "vitest";
import { fixtureCatalog, mixedFixture, type CommandBatch } from "@spec2gds/circuit-core";
import { HttpCircuitDesignerReadApi } from "../src/index";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

describe("HTTP circuit designer client", () => {
  test("loads and validates catalogs and graphs", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response(fixtureCatalog()))
      .mockResolvedValueOnce(response(mixedFixture()));
    const client = new HttpCircuitDesignerReadApi({ baseUrl: "http://example.test/circuit", fetch });

    expect((await client.getCatalog()).designs).toHaveLength(6);
    expect((await client.getGraph("mixed")).design.id).toBe("mixed");
    expect(fetch.mock.calls[1][0]).toBe("http://example.test/circuit/designs/mixed");
  });

  test("rejects invalid transport data", async () => {
    const client = new HttpCircuitDesignerReadApi({ fetch: vi.fn().mockResolvedValue(response({ designs: [] })) });
    await expect(client.getCatalog()).rejects.toMatchObject({ status: 502 });
  });

  test("preserves HTTP status and server detail", async () => {
    const client = new HttpCircuitDesignerReadApi({ fetch: vi.fn().mockResolvedValue(response({ detail: "No V1 .spec package is open." }, 400)) });
    await expect(client.getCatalog()).rejects.toMatchObject({
      status: 400,
      message: "No V1 .spec package is open.",
    });
  });

  test("uses the same revision-guarded batch for preview and apply", async () => {
    const graph = mixedFixture();
    const batch: CommandBatch = {
      batch_id: "batch_1",
      expected_source_revision_hash: graph.source_revision_hash,
      commands: [{ type: "set_layout_direction", command_id: "direction_1", design_id: graph.design.id, direction: "DOWN" }],
    };
    const preview = { batch, diagnostics: [], candidate: graph };
    const fetch = vi.fn().mockResolvedValue(response(preview));
    const client = new HttpCircuitDesignerReadApi({ fetch });

    expect((await client.apply(batch, "lease_1")).candidate?.design.id).toBe("mixed");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ batch, lease_id: "lease_1" });
  });
});
