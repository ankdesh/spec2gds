/** Small model projections and durable references to complete service reviews. */
import type { JsonValue } from "@ankdesh/dsh-util-values";
import { isRecord } from "./types.js";

export const MODEL_RESULT_LIMIT = 40 * 1024;

export function operationCount(review: Record<string, unknown>): number {
  const artifact = isRecord(review.artifact) ? review.artifact : {};
  const batch = isRecord(artifact.batch) ? artifact.batch : {};
  const operations = artifact.operations ?? batch.operations;
  return Array.isArray(operations) ? operations.length : 0;
}

export function proposalPresentation(value: unknown): JsonValue {
  const review = isRecord(value) && isRecord(value.review) ? value.review : null;
  return review ? { kind: "spec2gds.review", version: 1,
    sessionId: String(review.sessionId), proposalId: String(review.proposalId), state: String(review.state), operationCount: operationCount(review) } : null;
}

function bounded(value: unknown, depth = 0): unknown {
  if (typeof value === "string") return value.length > 2048 ? value.slice(0, 2048) + "…" : value;
  if (depth > 5) return "Details are available in the stored review.";
  if (Array.isArray(value)) return value.slice(0, 8).map(item => bounded(item, depth + 1));
  if (isRecord(value)) return Object.fromEntries(Object.entries(value).slice(0, 12).map(([key, item]) => [key.slice(0, 128), bounded(item, depth + 1)]));
  return value;
}

export function modelProposalResult(value: unknown): string {
  if (!isRecord(value)) return JSON.stringify(value);
  const review = isRecord(value.review) ? value.review : null;
  const projected = review ? {
    success: value.success, proposal_id: value.proposal_id, state: value.state, operation_count: operationCount(review),
    diagnostics: bounded(value.diagnostics), error: bounded(value.error),
    review_reference: proposalPresentation(value),
    summary: bounded(isRecord(review.changeSummary) ? review.changeSummary.text : ""),
    instruction: bounded(value.instruction),
  } : bounded(value);
  let text = JSON.stringify(projected);
  if (Buffer.byteLength(text) > MODEL_RESULT_LIMIT) {
    text = JSON.stringify({ success: value.success, proposal_id: value.proposal_id, state: value.state,
      review_reference: proposalPresentation(value),
      error: value.error ? { details: "The proposal failed. Complete diagnostics are in the stored review." } : undefined,
      instruction: "Inspect the stored review for details. Do not repeat a completed submission." });
  }
  if (Buffer.byteLength(text) > MODEL_RESULT_LIMIT) throw new Error("Proposal identity exceeds the model result limit.");
  return text;
}
