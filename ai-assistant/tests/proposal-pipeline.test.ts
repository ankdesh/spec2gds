import assert from "node:assert/strict";
import test from "node:test";
import { buildCircuitArtifact, buildSpecArtifact, reviewStateForPreview } from "../src/proposal-pipeline.js";
import type { SessionBinding } from "../src/types.js";

const base: SessionBinding = {
  sessionId: "session", status: "active", preset: "focused", domain: "spec", ownerUrl: "http://owner", documentId: "doc", scope: "entity",
  entityKind: "component", entityId: "component-1", title: "Test", workspaceKey: "workspace", workspaceTitle: "Test",
  workspacePath: "/tmp/test", workspaceDomain: "spec", workspaceOwnerUrl: "http://owner", workspaceDocumentId: "doc",
  archived: false, createdAt: "", updatedAt: "",
};
const input = {
  supported: true, unsupported_reason: null, title: "Change", summary: "Change it", rationale: "Requested",
  assumptions: ["A"], operations: [{ operation_id: "delete", type: "delete_parameter", entity: { document_id: "doc", entity_kind: "component", entity_id: "component-1" }, name: "OLD" }],
};

test("proposal builders keep owner contracts independent from the model tool", () => {
  const spec = buildSpecArtifact(base, "sha256:one", "proposal-1", input);
  assert.deepEqual(spec.target, { document_id: "doc", entity_kind: "component", entity_id: "component-1" });
  assert.equal(spec.base_source_revision_hash, "sha256:one");
  assert.equal((spec.operations as unknown[]).length, 1);

  const circuitBinding = { ...base, domain: "circuit" as const, scope: "document" as const, entityKind: null, entityId: null, workspaceDomain: "circuit" as const };
  const circuit = buildCircuitArtifact(circuitBinding, "rev-1", "proposal-2", "request-1", {
    ...input, operations: [{ operation_id: "delete", type: "delete_net", net_id: "old" }],
  });
  assert.deepEqual(circuit.batch, { request_id: "request-1", expected_revision: "rev-1", operations: [{ operation_id: "delete", type: "delete_net", net_id: "old" }] });
});

test("preview status mapping is explicit and fail closed", () => {
  assert.equal(reviewStateForPreview("spec", "valid"), "ready");
  assert.equal(reviewStateForPreview("spec", "stale"), "stale");
  assert.equal(reviewStateForPreview("spec", "mystery"), "rejected");
  assert.equal(reviewStateForPreview("circuit", "accepted"), "ready");
  assert.equal(reviewStateForPreview("circuit", "revision_conflict"), "stale");
  assert.equal(reviewStateForPreview("circuit", "locked"), "rejected");
});
