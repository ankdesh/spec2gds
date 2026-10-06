import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { ProductState } from "../src/state.js";

test("persists immutable bindings and compare-and-swap review transitions", async () => {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-assistant-state-"));
  try {
    const state = new ProductState(join(root, "product.sqlite3"));
    state.createBinding("session-1", {
      domain: "spec", serviceBaseUrl: "http://ignored", serviceUrl: "http://127.0.0.1:6010",
      documentId: "doc-1", scope: "document", title: "Spec: doc-1",
      workspaceKey: "workspace-1", workspaceTitle: "Spec: doc-1", workspacePath: join(root, "workspace-1"),
      workspaceDomain: "spec", workspaceServiceUrl: "http://127.0.0.1:6010", workspaceDocumentId: "doc-1",
    });
    assert.equal(state.getBinding("session-1")?.status, "creating");
    state.activateBinding("session-1");
    assert.equal(state.updateBinding("session-1", { title: "Renamed", archived: true }).title, "Renamed");
    state.refreshSourceName("session-1", "Timer controller", "Timer controller");
    assert.equal(state.getBinding("session-1")?.sourceName, "Timer controller");
    assert.equal(state.getBinding("session-1")?.title, "Renamed");
    assert.equal(state.getBinding("session-1")?.documentId, "doc-1");
    assert.equal(state.listBindings().length, 0);
    assert.equal(state.listBindings(true)[0]?.archived, true);
    state.updateBinding("session-1", { archived: false });
    const review = state.createReview({
      proposalId: "proposal-1", sessionId: "session-1", callId: "call-1", domain: "spec",
      state: "previewing", baseRevision: "rev-1", artifact: { proposal_id: "proposal-1" },
      preview: null, diagnostics: [], error: null, serviceResult: null,
    });
    assert.match(review.artifactDigest, /^sha256:/);
    const ready = state.transitionReview("session-1", "proposal-1", ["previewing"], "ready", { preview: { status: "valid" } });
    assert.equal(ready.version, 1);
    assert.equal(state.markRevisionStale("session-1", "rev-2"), 0);
    assert.equal(state.getReview("session-1", "proposal-1")?.state, "ready");
    assert.equal(state.getReview("session-1", "proposal-1")?.error, null);
    assert.throws(() => state.transitionReview("session-1", "proposal-1", ["previewing"], "discarded"), /Review is ready/);
    state.transitionReview("session-1", "proposal-1", ["ready"], "applying");
    assert.equal(state.recoverInterruptedReviews(), 1);
    assert.equal(state.getReview("session-1", "proposal-1")?.state, "reconcile");
    state.close();

    const reopened = new ProductState(join(root, "product.sqlite3"));
    assert.equal(reopened.getBinding("session-1")?.documentId, "doc-1");
    assert.equal(reopened.getBinding("session-1")?.sourceName, "Timer controller");
    assert.equal(reopened.getBinding("session-1")?.title, "Renamed");
    assert.equal(reopened.getReview("session-1", "proposal-1")?.state, "reconcile");
    assert.equal(reopened.getReview("session-1", "proposal-1")?.error, null);
    reopened.close();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("migrates pre-error-envelope review databases in place", async () => {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-assistant-migration-"));
  const path = join(root, "legacy.sqlite3");
  try {
    const legacy = new DatabaseSync(path);
    legacy.exec(`
      CREATE TABLE reviews (
        proposal_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        call_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        state TEXT NOT NULL,
        base_revision TEXT NOT NULL,
        artifact_json TEXT NOT NULL,
        artifact_digest TEXT NOT NULL,
        preview_json TEXT,
        diagnostics_json TEXT,
        owner_result_json TEXT,
        version INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    `);
    legacy.close();
    const migrated = new ProductState(path);
    const columns = migrated.database.prepare("PRAGMA table_info(reviews)").all() as Array<Record<string, unknown>>;
    assert.ok(columns.some(column => column.name === "error_json"));
    migrated.close();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("stores confirmed proposal details as structured session state", async () => {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-assistant-input-"));
  try {
    const path = join(root, "product.sqlite3");
    const state = new ProductState(path);
    state.createBinding("session-1", {
      domain: "spec", serviceBaseUrl: "http://ignored", serviceUrl: "http://127.0.0.1:6010",
      documentId: "doc-1", scope: "document", title: "Spec: doc-1",
      workspaceKey: "workspace-1", workspaceTitle: "Spec: doc-1", workspacePath: join(root, "workspace-1"),
      workspaceDomain: "spec", workspaceServiceUrl: "http://127.0.0.1:6010", workspaceDocumentId: "doc-1",
    });
    const inputId = state.createProposalInput("session-1", [{ name: "component_name" }, { name: "width" }]);
    assert.equal(state.confirmedProposalInput("session-1", inputId), null);
    assert.throws(() => state.confirmProposalInput(inputId, { width: "8" }), /do not match/);
    state.confirmProposalInput(inputId, { component_name: "adder", width: "8" });
    state.close();
    const reopened = new ProductState(path);
    assert.deepEqual(reopened.confirmedProposalInput("session-1", inputId), { component_name: "adder", width: "8" });
    assert.equal(reopened.confirmedProposalInput("another-session", inputId), null);
    reopened.close();
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("reads legacy service fields in saved creation records without changing source artifacts", async () => {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-terminology-"));
  const state = new ProductState(join(root, "product.sqlite3"));
  try {
    const legacy = { requestId: "request", sourceSessionId: "source", callId: "call", status: "prepared",
      ownerDocumentKey: "original", destinationOwnerDocumentKey: "destination",
      artifact: { ownerDocumentKey: "immutable source value" } };
    state.database.prepare("INSERT INTO source_creation_requests(request_id,source_session_id,call_id,status,request_json,updated_at) VALUES(?,?,?,?,?,?)")
      .run("request", "source", "call", "prepared", JSON.stringify(legacy), "2026-10-06");
    const restored = state.getSourceCreation("request") as unknown as Record<string, any>;
    assert.equal(restored.serviceDocumentKey, "original");
    assert.equal(restored.destinationServiceDocumentKey, "destination");
    assert.deepEqual(restored.artifact, legacy.artifact);
  } finally { state.close(); await rm(root, { recursive: true, force: true }); }
});
