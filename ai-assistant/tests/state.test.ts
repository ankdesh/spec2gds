import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ProductState } from "../src/state.js";

test("persists immutable bindings and compare-and-swap review transitions", async () => {
  const root = await mkdtemp(join(tmpdir(), "spec2gds-assistant-state-"));
  try {
    const state = new ProductState(join(root, "product.sqlite3"));
    state.createBinding("session-1", {
      domain: "spec", serviceBaseUrl: "http://ignored", ownerUrl: "http://127.0.0.1:6010",
      documentId: "doc-1", scope: "document", title: "Spec: doc-1",
    });
    assert.equal(state.getBinding("session-1")?.status, "creating");
    state.activateBinding("session-1");
    assert.equal(state.updateBinding("session-1", { title: "Renamed", archived: true }).title, "Renamed");
    assert.equal(state.listBindings().length, 0);
    assert.equal(state.listBindings(true)[0]?.archived, true);
    state.updateBinding("session-1", { archived: false });
    const review = state.createReview({
      proposalId: "proposal-1", sessionId: "session-1", callId: "call-1", domain: "spec",
      state: "previewing", baseRevision: "rev-1", artifact: { proposal_id: "proposal-1" },
      preview: null, diagnostics: [], ownerResult: null,
    });
    assert.match(review.artifactDigest, /^sha256:/);
    const ready = state.transitionReview("session-1", "proposal-1", ["previewing"], "ready", { preview: { status: "valid" } });
    assert.equal(ready.version, 1);
    assert.equal(state.markRevisionStale("session-1", "rev-2"), 1);
    assert.equal(state.getReview("session-1", "proposal-1")?.state, "stale");
    state.transitionReview("session-1", "proposal-1", ["stale"], "ready");
    assert.throws(() => state.transitionReview("session-1", "proposal-1", ["previewing"], "discarded"), /Review is ready/);
    state.transitionReview("session-1", "proposal-1", ["ready"], "applying");
    assert.equal(state.recoverInterruptedReviews(), 1);
    assert.equal(state.getReview("session-1", "proposal-1")?.state, "reconcile");
    state.close();

    const reopened = new ProductState(join(root, "product.sqlite3"));
    assert.equal(reopened.getBinding("session-1")?.documentId, "doc-1");
    assert.equal(reopened.getReview("session-1", "proposal-1")?.state, "reconcile");
    reopened.close();
  } finally { await rm(root, { recursive: true, force: true }); }
});
