import { describe, expect, it, vi } from "vitest";
import { SpecEditorHttpClient, type A2UIDocumentBatch } from "../src/index";

describe("SpecEditorHttpClient", () => {
  it("opens a package and reads an A2UI batch without renderer dependencies", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ document_id: "demo" }), { headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        protocol_version: "v0.9",
        catalog_id: "urn:spec2gds:a2ui:document:v1",
        surface_id: "spec-document-demo",
        source_revision_hash: "sha256:test",
        messages: [],
      } satisfies A2UIDocumentBatch), { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new SpecEditorHttpClient("/api");
    await client.openDocument("/tmp/demo.spec");
    const batch = await client.getA2UIBatch();
    expect(batch.catalog_id).toBe("urn:spec2gds:a2ui:document:v1");
    expect(fetchMock).toHaveBeenLastCalledWith("/api/documents/a2ui", undefined);
    vi.unstubAllGlobals();
  });
});
