import assert from "node:assert/strict";
import test from "node:test";
import { OwnerError } from "../src/owner-clients.js";
import {
  changeSummaryFor,
  errorCodeForOwnerStatus,
  errorFromException,
  errorFromOwnerResult,
  proposalError,
  publicReview,
} from "../src/proposal-presentation.js";
import type { ProposalReview, SessionBinding } from "../src/types.js";

const binding = (domain: "spec" | "circuit"): SessionBinding => ({
  sessionId: "session-1", status: "active", domain, ownerUrl: "http://owner", documentId: "doc-1", scope: "document",
  entityKind: null, entityId: null, title: "Test", archived: false, createdAt: "", updatedAt: "",
  workspaceKey: "test", workspaceTitle: "Test", workspacePath: "/tmp/test",
  workspaceDomain: domain, workspaceOwnerUrl: "http://owner", workspaceDocumentId: "doc-1",
});

function review(domain: "spec" | "circuit", overrides: Partial<ProposalReview> = {}): ProposalReview {
  return {
    proposalId: "proposal-1", sessionId: "session-1", callId: "call-1", domain, state: "ready", baseRevision: "rev-1",
    artifact: domain === "spec"
      ? { operations: [{ type: "create_entity" }, { type: "create_entity" }], assumptions: ["Clock is synchronous."] }
      : { batch: { operations: [{ type: "add_instance" }, { type: "create_net" }] }, assumptions: [] },
    artifactDigest: "sha256:test", preview: null, diagnostics: [], error: null, ownerResult: null,
    version: 1, createdAt: "", updatedAt: "", ...overrides,
  };
}

test("Spec summary is derived from operation counts and owner diff", () => {
  const summary = changeSummaryFor(review("spec", { preview: { status: "valid", diff: [
    { change: "added", path: "$.components[timer]" },
    { change: "changed", path: "$.components[alu].description" },
  ] } }));
  assert.equal(summary.text, "Proposes 2 operations (2 create_entity). Owner preview reports 2 changed targets.");
  assert.deepEqual(summary.operationCounts, [{ type: "create_entity", count: 2 }]);
  assert.deepEqual(summary.changedTargets, ["added $.components[timer]", "changed $.components[alu].description"]);
  assert.deepEqual(summary.assumptions, ["Clock is synchronous."]);
});

test("Circuit summary sorts operation types and normalizes graph targets", () => {
  const summary = changeSummaryFor(review("circuit", { preview: { status: "accepted", diff: {
    added: [{ kind: "instance", id: "u_timer" }], removed: [], changed: [{ kind: "net", id: "clock" }], connections_changed: ["clock"],
  } } }));
  assert.deepEqual(summary.operationCounts, [{ type: "add_instance", count: 1 }, { type: "create_net", count: 1 }]);
  assert.deepEqual(summary.changedTargets, ["added:instance:u_timer", "changed:net:clock", "connections_changed:net:clock"]);
  assert.match(summary.text, /^Proposes 2 operations/);
});

test("public review removes the private digest and adds the deterministic summary", () => {
  const value = publicReview(review("spec"));
  assert.equal(Object.hasOwn(value, "artifactDigest"), false);
  assert.equal(value.changeSummary.operationCounts[0]?.count, 2);
});

test("owner diagnostics become stable issues without invented advice", () => {
  const error = errorFromOwnerResult(binding("circuit"), "proposal-1", {
    status: "rejected",
    diagnostics: [
      { code: "missing_terminal", message: "Terminal does not exist.", path: "design.nets[clock]" },
      { code: "bad_width", message: "Widths differ.", suggested_actions: ["Choose equal-width endpoints."] },
    ],
  });
  assert.equal(error.error_code, "OWNER_REJECTED");
  assert.equal(error.target, "design.nets[clock]");
  assert.equal(error.retryable, false);
  assert.deepEqual(error.suggested_actions, ["Choose equal-width endpoints."]);
  assert.equal(error.issues.length, 2);
  assert.deepEqual(error.owner_diagnostics, [
    { code: "missing_terminal", message: "Terminal does not exist.", path: "design.nets[clock]" },
    { code: "bad_width", message: "Widths differ.", suggested_actions: ["Choose equal-width endpoints."] },
  ]);
});

test("owner and exception classifications fail closed", () => {
  assert.deepEqual(errorCodeForOwnerStatus("conflict"), { code: "STALE_REVISION", retryable: true });
  assert.deepEqual(errorCodeForOwnerStatus("locked"), { code: "OWNER_LOCKED", retryable: true });
  assert.deepEqual(errorCodeForOwnerStatus("provider_failed"), { code: "OWNER_UNAVAILABLE", retryable: true });
  assert.equal(errorFromException(binding("spec"), "p", new OwnerError(409, "stale")).error_code, "STALE_REVISION");
  assert.equal(errorFromException(binding("spec"), "p", new OwnerError(503, "offline")).error_code, "OWNER_UNAVAILABLE");
  assert.equal(errorFromException(binding("spec"), "p", new OwnerError(502, "Owner returned non-JSON content.")).error_code, "OWNER_CONTRACT_ERROR");
  assert.equal(errorFromException(binding("spec"), "p", new Error("boom")).error_code, "INTERNAL_ERROR");
  assert.equal(proposalError(binding("spec"), "call", "UNSUPPORTED_REQUEST", "Cannot rename identity.").target, "document:doc-1");
});
