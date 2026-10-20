import { describe, expect, test, vi } from "vitest";
import {
  createDefaultCircuitDesignerPreferences,
  simpleDocumentFixture,
  type CircuitChangeResult,
  type CircuitOperationBatch,
} from "@spec2gds/circuit-core";
import { HttpCircuitDesignerBackend } from "../src/index";

const response = (body: unknown, status = 200) => new Response(
  body === undefined ? undefined : JSON.stringify(body),
  { status, headers: { "Content-Type": "application/json" } },
);

describe("HTTP circuit designer client", () => {
  test("takes over only the explicitly confirmed lease", async () => {
    const lease = { lease_id: "new", document_id: "fixture_simple", owner_id: "second-tab", expires_at: "2026-10-20T12:00:00Z" };
    const fetch = vi.fn().mockResolvedValue(response(lease));
    const client = new HttpCircuitDesignerBackend({ fetch });
    await expect(client.takeOverLease("fixture_simple", "confirmed-old", "second-tab")).resolves.toEqual(lease);
    expect(fetch.mock.calls[0][0]).toContain("/fixture_simple/lock/takeover");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ expected_lease_id: "confirmed-old", owner_id: "second-tab" });
  });

  test("rejects recovery responses without an authoritative snapshot", async () => {
    const client = new HttpCircuitDesignerBackend({ fetch: vi.fn().mockResolvedValue(response({
      lease: { lease_id: "new", document_id: "fixture_simple", owner_id: "second-tab", expires_at: "2026-10-20T12:00:00Z" },
      snapshot: { revision: "2" }, binding: {},
    })) });
    await expect(client.recoverSource("fixture_simple", "old", "second-tab")).rejects.toMatchObject({ status: 502 });
  });

  test("loads and validates a canonical snapshot", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ revision: "1", document: simpleDocumentFixture() }));
    const client = new HttpCircuitDesignerBackend({ baseUrl: "http://example.test/circuit/v1", fetch });
    expect((await client.get("fixture_simple")).document.design.id).toBe("simple");
    expect(fetch.mock.calls[0][0]).toBe("http://example.test/circuit/v1/documents/fixture_simple");
  });

  test("lists document summaries for target discovery", async () => {
    const summary = {
      document_id: "fixture_simple", label: "Simple", design_id: "simple",
      component_count: 2, instance_count: 2, net_count: 1, warning_count: 0,
    };
    const fetch = vi.fn().mockResolvedValue(response({ documents: [summary] }));
    const client = new HttpCircuitDesignerBackend({ baseUrl: "http://example.test/circuit/v1", fetch });
    await expect(client.listDocuments()).resolves.toEqual([summary]);
    expect(fetch.mock.calls[0][0]).toBe("http://example.test/circuit/v1/documents");
  });

  test("rejects invalid transport data", async () => {
    const client = new HttpCircuitDesignerBackend({ fetch: vi.fn().mockResolvedValue(response({ revision: "1" })) });
    await expect(client.get("fixture_simple")).rejects.toMatchObject({ status: 502 });
  });

  test("preserves standard error status and envelope message", async () => {
    const client = new HttpCircuitDesignerBackend({
      fetch: vi.fn().mockResolvedValue(response({ code: "not_found", message: "No circuit document." }, 404)),
    });
    await expect(client.get("fixture_simple")).rejects.toMatchObject({
      status: 404,
      message: "No circuit document.",
    });
  });

  test("loads and saves validated Circuit Designer preferences", async () => {
    const preferences = createDefaultCircuitDesignerPreferences();
    preferences.ui.inspector_open = true;
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ preferences, persisted: false }))
      .mockResolvedValueOnce(response({ preferences, persisted: true }));
    const client = new HttpCircuitDesignerBackend({ baseUrl: "http://example.test/circuit/v1", fetch });

    expect((await client.getPreferences()).persisted).toBe(false);
    expect((await client.putPreferences(preferences)).preferences.ui.inspector_open).toBe(true);
    expect(fetch.mock.calls[0][0]).toBe("http://example.test/circuit/v1/preferences");
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: "PUT" });
  });

  test("rejects invalid preference responses", async () => {
    const client = new HttpCircuitDesignerBackend({
      fetch: vi.fn().mockResolvedValue(response({ preferences: { schema_version: 9 }, persisted: true })),
    });
    await expect(client.getPreferences()).rejects.toMatchObject({ status: 502 });
  });

  test("uses the same revision-guarded batch for preview and commit", async () => {
    const batch: CircuitOperationBatch = {
      request_id: "batch_1",
      expected_revision: "1",
      operations: [{
        operation_id: "direction_1",
        type: "set_layout_settings",
        direction: "DOWN",
      }],
    };
    const result: CircuitChangeResult = {
      status: "accepted",
      candidate: { ...simpleDocumentFixture(), layout: { ...simpleDocumentFixture().layout, direction: "DOWN" } },
      diagnostics: [],
      diff: { added: [], removed: [], changed: [{ kind: "layout", id: "simple" }], connections_changed: [] },
      alias_map: {},
    };
    const fetch = vi.fn().mockResolvedValue(response(result));
    const client = new HttpCircuitDesignerBackend({ fetch });

    expect((await client.commit("fixture_simple", batch, "lease_1")).status).toBe("accepted");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ batch, lease_id: "lease_1" });
  });
});
