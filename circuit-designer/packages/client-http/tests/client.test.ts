import { describe, expect, test, vi } from "vitest";
import { fixtureCatalog, mixedFixture } from "@spec2gds/circuit-core";
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
});
