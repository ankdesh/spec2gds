/** Architecture decisions carry identity independently of display text. */
import { isRecord } from "./types.js";
import type { ProductState } from "./state.js";

export interface ArchitectureDecision {
  kind: "architecture_decision";
  architecture_review_id: string;
  decision: "approved" | "revised" | "cancelled";
  feedback: string;
}

export function architectureDecision(review: Record<string, any>): ArchitectureDecision {
  return { kind: "architecture_decision", architecture_review_id: review.reviewId,
    decision: review.status, feedback: review.feedback || "" };
}

export function decisionReview(state: ProductState, sessionId: string, text: string): Record<string, any> | null {
  let value: unknown;
  try { value = JSON.parse(text); } catch { return null; }
  if (!isRecord(value)) return null;
  const legacy = value.kind === undefined && typeof value.architecture_review_id === "string" && typeof value.decision === "string";
  if (value.kind !== "architecture_decision" && !legacy) return null;
  const review = typeof value.architecture_review_id === "string" ? state.architectureReview(value.architecture_review_id) : null;
  if (!review || review.sessionId !== sessionId || review.status !== value.decision
    || !["approved", "revised", "cancelled"].includes(String(value.decision))
    || (value.feedback ?? "") !== (review.feedback ?? "")) {
    throw new Error("Architecture decision does not match the saved review and conversation.");
  }
  return review;
}
