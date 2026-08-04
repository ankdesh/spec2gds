import { describe, expect, it, vi } from "vitest";
import { SpecEditorHttpClient, type A2UIDocumentBatch } from "../src/index";

describe("SpecEditorHttpClient", () => {
  it("loads the shared service directory", async () => {
    const directory = {
      schema_version: 1,
      services: {
        spec_editor: { service_url: "http://127.0.0.1:8000", ui_url: "http://127.0.0.1:8000/editor" },
        circuit_designer: { service_url: "http://127.0.0.1:4100/api/circuit-designer/v1", ui_url: "http://127.0.0.1:4180" },
        ai_assistant: { service_url: "http://127.0.0.1:4200", ui_url: "http://127.0.0.1:4200" },
      },
    } as const;
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(directory), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(new SpecEditorHttpClient("/api").getServiceDirectory()).resolves.toEqual(directory);
    expect(fetchMock).toHaveBeenCalledWith("/api/services", undefined);
    vi.unstubAllGlobals();
  });

  it("creates a new package at an explicit path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ document_id: "new_spec" }), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new SpecEditorHttpClient("/api");
    await client.createDocument("/tmp/new.spec", "New accelerator");
    expect(fetchMock).toHaveBeenCalledWith("/api/documents/create", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path: "/tmp/new.spec", title: "New accelerator" }),
    });
    vi.unstubAllGlobals();
  });

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

  it("submits typed optimistic editor transactions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ committed: true, snapshot: { source_revision_hash: "sha256:next" } }), {
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new SpecEditorHttpClient("/api");
    await client.applyTransaction("sha256:base", [{
      type: "create_entity",
      kind: "component",
      name: "timer",
    }]);
    expect(fetchMock).toHaveBeenCalledWith("/api/transactions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        expected_source_revision_hash: "sha256:base",
        operations: [{ type: "create_entity", kind: "component", name: "timer" }],
      }),
    });
    vi.unstubAllGlobals();
  });

  it("launches a selected source design through the editor-side adapter", async () => {
    const launch = {
      document_id: "spec_demo_design_top_1234",
      entity_id: "design_top",
      entity_kind: "design" as const,
      editor_url: "http://127.0.0.1:4180?document_id=spec_demo_design_top_1234",
      reused_session: false,
      omitted_bus_items: ["control_bus"],
      omitted_ports: ["service"],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(launch), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new SpecEditorHttpClient("/api");
    await expect(client.launchCircuitDesigner("design", "design_top")).resolves.toEqual(launch);
    expect(fetchMock).toHaveBeenCalledWith("/api/circuit-designer/launch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ entity_kind: "design", entity_id: "design_top" }),
    });
    vi.unstubAllGlobals();
  });

  it("launches an entity-bound assistant chat and exposes source events", async () => {
    const target = {
      document_id: "spec_demo",
      entity_id: "component_leaf",
      entity_kind: "component" as const,
    };
    const launch = {
      assistant_url: "http://127.0.0.1:4200/launch/spec?document_id=spec_demo",
      target,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(launch), { headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new SpecEditorHttpClient("/api");
    await expect(client.launchAssistant(target)).resolves.toEqual(launch);
    expect(client.eventsUrl()).toBe("/api/events");
    expect(fetchMock).toHaveBeenCalledWith("/api/assistant/launch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ entity_kind: "component", entity_id: "component_leaf" }),
    });
    vi.unstubAllGlobals();
  });
});
