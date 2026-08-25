import { afterEach, describe, expect, it } from "vitest";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";
import { CircuitDesignerService } from "../src/server";
import { EphemeralCircuitSessionBackend } from "../src/session-backend";
import { StructuredLogger } from "@spec2gds/observability/node";
import { mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let service: CircuitDesignerService | undefined;

afterEach(async () => {
  await service?.close();
  service = undefined;
});

describe("Circuit Designer REST service", () => {
  it("accepts browser events into the trusted combined-log contract", async () => {
    const file = join(mkdtempSync(join(tmpdir(), "spec2gds-service-log-")), "combined.jsonl");
    const logger = new StructuredLogger("circuit-designer", {
      enabled: true, level: "debug", file, maxBytes: 100_000,
      viewerHost: "127.0.0.1", viewerPort: 6014,
    });
    service = new CircuitDesignerService({ logger });
    const port = await service.listen();
    const response = await fetch(`http://127.0.0.1:${port}/api/circuit-designer/v1/logs/events`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: "browser-1",
        events: [{ component: "canvas", event: "selected", message: "Selected block", details: { id: "producer_0" } }],
      }),
    });
    expect(response.status).toBe(204);
    const record = JSON.parse(readFileSync(file, "utf8"));
    expect(record).toMatchObject({ application: "circuit-designer", origin: "browser", session_id: "browser-1" });
  });

  it("exposes health and the shared service directory", async () => {
    service = new CircuitDesignerService();
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;

    expect(await (await fetch(`${base}/health`)).json()).toMatchObject({
      status: "ok",
      service: "circuit_designer",
    });
    const directory = await (await fetch(`${base}/services`)).json() as {
      services: { ai_assistant: { ui_url: string } };
    };
    expect(directory.services.ai_assistant.ui_url).toMatch(/^http:\/\/[^/]+:6013$/);
  });

  it("loads defaults and atomically persists a shared preference file", async () => {
    const directory = mkdtempSync(join(tmpdir(), "spec2gds-preferences-"));
    const preferencesPath = join(directory, "nested", "preferences.json");
    service = new CircuitDesignerService({ preferencesPath });
    let port = await service.listen();
    let base = `http://127.0.0.1:${port}/api/circuit-designer/v1/preferences`;
    const initial = await (await fetch(base)).json() as {
      persisted: boolean;
      preferences: { ui: { inspector_open: boolean }; action_bindings: Record<string, { keyboard: string }> };
    };
    expect(initial.persisted).toBe(false);
    expect(initial.preferences.ui.inspector_open).toBe(false);
    expect(initial.preferences.action_bindings["new-document"].keyboard).toBe("Mod+N");

    const changed = {
      ...initial.preferences,
      ui: { inspector_open: true },
      action_bindings: {
        ...initial.preferences.action_bindings,
        "fit-circuit": { keyboard: "F", mouse: "none" },
      },
    };
    expect((await fetch(base, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changed),
    })).status).toBe(200);
    expect(JSON.parse(readFileSync(preferencesPath, "utf8"))).toMatchObject(changed);
    expect(readdirSync(join(directory, "nested"))).toEqual(["preferences.json"]);

    await service.close();
    service = new CircuitDesignerService({ preferencesPath });
    port = await service.listen();
    base = `http://127.0.0.1:${port}/api/circuit-designer/v1/preferences`;
    const reloaded = await (await fetch(base)).json() as { persisted: boolean; preferences: typeof changed };
    expect(reloaded.persisted).toBe(true);
    expect(reloaded.preferences.ui.inspector_open).toBe(true);
    expect(reloaded.preferences.action_bindings["fit-circuit"].keyboard).toBe("F");
  });

  it("reports malformed and unsupported preference files without overwriting them", async () => {
    const directory = mkdtempSync(join(tmpdir(), "spec2gds-invalid-preferences-"));
    const preferencesPath = join(directory, "preferences.json");
    writeFileSync(preferencesPath, "{broken", "utf8");
    service = new CircuitDesignerService({ preferencesPath });
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1/preferences`;
    const malformed = await fetch(base);
    expect(malformed.status).toBe(400);
    expect((await malformed.json() as { message: string }).message).toContain("not valid JSON");
    expect(readFileSync(preferencesPath, "utf8")).toBe("{broken");

    const rejected = await fetch(base, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schema_version: 9, ui: {}, action_bindings: {} }),
    });
    expect(rejected.status).toBe(400);
    expect(readFileSync(preferencesPath, "utf8")).toBe("{broken");

    const oversized = await fetch(base, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schema_version: 1, padding: "x".repeat(262_144) }),
    });
    expect(oversized.status).toBe(400);
    expect((await oversized.json() as { message: string }).message).toContain("256 KiB");
    expect(readFileSync(preferencesPath, "utf8")).toBe("{broken");
  });

  it("uses ephemeral process memory by default", async () => {
    const document = simpleDocumentFixture();
    service = new CircuitDesignerService();
    let port = await service.listen();
    let base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;
    expect((await fetch(`${base}/documents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: "ephemeral_1", document }),
    })).status).toBe(200);
    await service.close();

    service = new CircuitDesignerService();
    port = await service.listen();
    base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;
    expect((await fetch(`${base}/documents/${document.document_id}`)).status).toBe(404);
  });

  it("creates, reads, commits, and maps revision conflicts", async () => {
    const backend = new EphemeralCircuitSessionBackend();
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
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
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

  it("accepts a proposal create request and owns its server state", async () => {
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
    service = new CircuitDesignerService({
      backend,
      now: () => new Date("2026-07-30T00:00:00.000Z"),
    });
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple`;
    const response = await fetch(`${base}/proposals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proposal_id: "external_proposal",
        document_id: "fixture_simple",
        base_revision: "1",
        title: "Move the producer",
        summary: "A reviewable external change.",
        rationale: "Keep the blocks visually separated.",
        assumptions: ["The current revision is still active."],
        batch: {
          request_id: "external_batch",
          expected_revision: "1",
          operations: [{
            operation_id: "external_move",
            type: "set_instance_geometry",
            instance_id: "producer_0",
            geometry: { x: 60, y: 60, width: 180, height: 100 },
          }],
        },
        status: "accepted",
        diagnostics: [{ severity: "error", code: "forged", message: "ignore me" }],
        created_at: "forged",
      }),
    });
    expect(response.status).toBe(201);
    const proposal = await response.json() as {
      status: string;
      created_at: string;
      diagnostics: Array<{ code: string }>;
      assumptions: string[];
    };
    expect(proposal.status).toBe("pending");
    expect(proposal.created_at).not.toBe("forged");
    expect(proposal.diagnostics.map((item) => item.code)).not.toContain("forged");
    expect(proposal.assumptions).toEqual(["The current revision is still active."]);
  });

  it("rejects non-loopback provider callbacks by default", async () => {
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
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
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
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
