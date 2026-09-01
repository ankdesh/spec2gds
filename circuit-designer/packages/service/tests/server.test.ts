import { afterEach, describe, expect, it } from "vitest";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";
import { CircuitDesignerService } from "../src/server";
import { EphemeralCircuitSessionBackend } from "../src/session-backend";
import { StructuredLogger } from "@spec2gds/observability/node";
import { mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer } from "node:http";

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

  it("boots without shared configuration and exposes portable capabilities", async () => {
    service = new CircuitDesignerService();
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;

    expect(await (await fetch(`${base}/health`)).json()).toMatchObject({
      status: "ok",
      service: "circuit_designer",
    });
    expect(await (await fetch(`${base}/capabilities`)).json()).toMatchObject({
      schema_version: 1,
      service: "circuit_designer",
      capabilities: expect.arrayContaining(["canonical-documents", "source-bindings", "exports"]),
      integrations: { service_directory: false },
    });
    expect((await fetch(`${base}/services`)).status).toBe(404);
  });

  it("retains the legacy service-directory endpoint when a host supplies one", async () => {
    const location = { service_url: "http://127.0.0.1:1", ui_url: "http://127.0.0.1:2" };
    service = new CircuitDesignerService({
      serviceDirectory: {
        schema_version: 2,
        services: { spec_editor: location, circuit_designer: location, ai_assistant: location },
        logging: { enabled: false, level: "info" },
      },
    });
    const port = await service.listen();
    const base = `http://127.0.0.1:${port}/api/circuit-designer/v1`;
    expect(await (await fetch(`${base}/services`)).json()).toMatchObject({ services: { ai_assistant: location } });
    expect(await (await fetch(`${base}/capabilities`)).json()).toMatchObject({ integrations: { service_directory: true } });
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

  it("commits source-bound drafts through the provider before replacing the session", async () => {
    let authorization = "";
    const providerCalls: string[] = [];
    const provider = createServer((request, response) => {
      authorization = String(request.headers.authorization ?? "");
      providerCalls.push(request.url ?? "");
      const chunks: Buffer[] = [];
      request.on("data", (chunk) => chunks.push(chunk));
      request.on("end", () => {
        const body = JSON.parse(Buffer.concat(chunks).toString()) as { candidate_document: ReturnType<typeof simpleDocumentFixture> };
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({
          accepted: true,
          source_revision_hash: "sha256:next",
          document: body.candidate_document,
          diagnostics: [],
        }));
      });
    });
    await new Promise<void>((resolve) => provider.listen(0, "127.0.0.1", resolve));
    const providerAddress = provider.address();
    const providerPort = typeof providerAddress === "object" && providerAddress ? providerAddress.port : 0;
    try {
      const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
      service = new CircuitDesignerService({ backend });
      const port = await service.listen();
      const documentBase = `http://127.0.0.1:${port}/api/circuit-designer/v1/documents/fixture_simple`;
      expect((await fetch(`${documentBase}/source-binding`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_url: `http://127.0.0.1:${providerPort}/source/`,
          token: "secret-token",
          binding: {
            schema_version: 1,
            binding_id: "source_fixture",
            source_document_id: "spec_fixture",
            source_entity: { document_id: "spec_fixture", entity_id: "design_fixture", entity_kind: "design" },
            editable_design_id: "design_fixture",
            base_source_revision_hash: "sha256:base",
            writable: true,
            capabilities: ["topology", "layout"],
            omitted_bus_items: [],
            omitted_ports: [],
          },
        }),
      })).status).toBe(200);
      const lease = await (await fetch(`${documentBase}/lock`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_id: "test" }),
      })).json() as { lease_id: string };
      const commitBody = {
        lease_id: lease.lease_id,
        batch: {
          request_id: "source_move",
          expected_revision: "1",
          operations: [{
            operation_id: "move",
            type: "set_instance_geometry",
            instance_id: "producer_0",
            geometry: { x: 40, y: 60, width: 180, height: 100, pinned: true },
          }],
        },
      };
      const response = await fetch(`${documentBase}/source/commit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(commitBody),
      });
      expect(response.status).toBe(200);
      const saved = await response.json() as { accepted: boolean; snapshot: { document: ReturnType<typeof simpleDocumentFixture> } };
      expect(saved.accepted).toBe(true);
      expect(saved.snapshot.document.layout.instance_geometry.producer_0.x).toBe(40);
      expect(authorization).toBe("Bearer secret-token");
      expect(providerCalls).toEqual(["/source/preview", "/source/commit"]);
      expect((await (await fetch(`${documentBase}/lock`)).json() as { lease: unknown }).lease).toBeNull();
      expect((await (await fetch(`${documentBase}/source-binding`)).json() as { base_source_revision_hash: string }).base_source_revision_hash).toBe("sha256:next");
      const replay = await fetch(`${documentBase}/source/commit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(commitBody),
      });
      expect(replay.status).toBe(200);
      expect((await replay.json() as { accepted: boolean }).accepted).toBe(true);
      expect(providerCalls).toEqual(["/source/preview", "/source/commit"]);
    } finally {
      await new Promise<void>((resolve) => provider.close(() => resolve()));
    }
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
