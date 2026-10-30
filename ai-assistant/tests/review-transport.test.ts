import assert from "node:assert/strict";
import test from "node:test";
import { modelProposalResult, proposalPresentation, MODEL_RESULT_LIMIT } from "../src/review-transport.js";
import { publicReview } from "../src/proposal-presentation.js";
import { apply as spillApply } from "@ankdesh/dsh-spill-policy";

const preview = { status: "valid", diff: [{ label: "Large SV section", before: "x".repeat(60000), after: "y".repeat(60000) }] };
const review: any = { proposalId: "proposal", sessionId: "conversation", callId: "call", domain: "spec", state: "ready", baseRevision: "rev",
  artifact: { operations: [], summary: "Large change" }, artifactDigest: "private", preview, diagnostics: [], error: null,
  serviceResult: { status: "approval_required", preview, review_number: 3 }, version: 1, createdAt: "", updatedAt: "" };

test("deduplication preserves the full preview, receipt and deterministic review number", () => {
  const value = publicReview(review);
  assert.equal(value.preview, preview);
  assert.equal(Object.hasOwn(value.serviceResult as any, "preview"), false);
  assert.equal(review.serviceResult.preview, preview);
  assert.equal(value.reviewNumber, 3);
});

test("large canonical results render bounded JSON with exact durable review identity", () => {
  const value = { success: true, proposal_id: review.proposalId, state: review.state, review, diagnostics: [], instruction: "Inspect review" };
  assert.ok(Buffer.byteLength(JSON.stringify(value)) > 50000);
  const text = modelProposalResult(value);
  assert.ok(Buffer.byteLength(text) <= MODEL_RESULT_LIMIT);
  assert.equal(JSON.parse(text).proposal_id, "proposal");
  assert.equal(proposalPresentation(value) && (proposalPresentation(value) as any).sessionId, "conversation");
  assert.equal(review.preview.diff[0].after.length, 60000);
});

test("field reduction preserves JSON for large multibyte diagnostics", () => {
  const value = { success: false, error: { details: "界".repeat(50000), issues: Array(200).fill({ details: "界".repeat(50000) }) } };
  const text = modelProposalResult(value);
  assert.ok(Buffer.byteLength(text) <= MODEL_RESULT_LIMIT);
  assert.equal(JSON.parse(text).success, false);
});

test("forced native text spilling preserves separate presentation metadata", async () => {
  let hook: any;
  spillApply({ on: (name: string, fn: any) => { if (name === "tools/post-execute") hook = fn; },
    get: () => ({ saveText: async () => ({ locator: "/tmp/review-probe", retrievalHint: "Read full result" }) }), logger: { warn() {} } } as any, { maxInlineBytes: 512 });
  const value = { review };
  const result = { content: [{ type: "text", text: JSON.stringify(value) }], meta: proposalPresentation(value) };
  const decision = await hook({ name: "prepare_spec_proposal", callId: "call", agent: { session: { header: { id: "conversation" } } } }, result, async () => ({ kind: "accept" }));
  assert.throws(() => JSON.parse(decision.content[0].text));
  assert.deepEqual(result.meta, { kind: "spec2gds.review", version: 1, sessionId: "conversation", proposalId: "proposal", state: "ready", operationCount: 0 });
});
