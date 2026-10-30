/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */
import { randomUUID } from "node:crypto";
import type { PromptSection } from "@ankdesh/dsh-system-prompt";
import { type ToolRunContext } from "../tool-registry.js";
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue, type JsonValue } from "@ankdesh/dsh-util-values";
import { rtlSizingFeedback } from "../rtl-authoring-feedback.js";
import { publicReview } from "../proposal-presentation.js";
import { type ProductState } from "../state.js";
import type { ProposalError, ProposalReview, SessionBinding } from "../types.js";
import { isRecord } from "../types.js";

export interface ProposalInputField {
  readonly name: string;
  readonly label: string;
  readonly description: string;
  readonly default_value: string;
}

export interface ProposalInputRequest {
  readonly title: string;
  readonly description: string;
  readonly fields: readonly ProposalInputField[];
  readonly submit_label: string;
}

/** Render model-supplied Circuit proposal fields. */
export function proposalInputRequest(
  _binding: SessionBinding,
  reason: string,
  provided: readonly ProposalInputField[] | undefined,
): ProposalInputRequest | null {
  if (_binding.domain !== "circuit") throw new Error("Spec inputs require a flow.");
  const fields = (provided ?? []).filter(field => field.name.trim() && field.label.trim());
  if (!fields.length) return null;
  return {
    title: "Complete the proposal details",
    description: reason.trim() || "More information is required before the proposal can be prepared.",
    fields,
    submit_label: "Continue proposal",
  };
}

export function structuredQuestionPrompt(enabled: boolean, instructions: InstructionBundle = defaultInstructions): PromptSection | null {
  if (!enabled) return null;
  return {
    name: "spec2gds:interactive-clarification",
    order: 250,
    text: instructions.text("clarification"),
  };
}

export function callId(exec: ToolRunContext): string { return String(exec.callId); }
export function id(prefix: string): string { return `${prefix}_${randomUUID().replaceAll("-", "")}`; }

export function json(value: unknown): JsonValue {
  const snapshot = snapshotJsonValue(value);
  if (snapshot === undefined) throw new Error("Tool result was not lossless JSON.");
  return snapshot as JsonValue;
}

export function reviewResult(review: ProposalReview, instructions: InstructionBundle = defaultInstructions): JsonValue {
  return json({
    success: review.state === "ready" || review.state === "applied",
    proposal_id: review.proposalId,
    state: review.state,
    diagnostics: review.diagnostics,
    ...(review.error ? { error: review.error } : {}),
    review: publicReview(review),
    instruction: review.state === "applied"
      ? instructions.text("result.18")
      : review.state === "ready"
      ? instructions.text("result.19")
      : instructions.text("result.20") + (review.domain === "spec" ? "\n" + rtlSizingFeedback(review.diagnostics, review.artifact) : ""),
  });
}

export function failureResult(error: ProposalError, instruction: string): JsonValue {
  return json({ success: false, error, instruction });
}

export function diagnostics(value: Record<string, unknown>): unknown {
  return value.diagnostics ?? value.detail ?? [];
}
export function confirmedValues(
  state: ProductState, binding: SessionBinding, inputId: string | undefined, supplied: unknown,
): string | null {
  if (!inputId) return supplied === undefined ? null : "Confirmed values require confirmed_input_id.";
  const stored = state.confirmedProposalInput(binding.sessionId, inputId);
  if (!stored) return "Confirmed proposal input is missing or was not submitted.";
  if (!isRecord(supplied) || Object.keys(supplied).length !== Object.keys(stored).length
    || Object.entries(stored).some(([name, value]) => supplied[name] !== value)) {
    return "confirmed_values must exactly match the submitted details card.";
  }
  return null;
}

