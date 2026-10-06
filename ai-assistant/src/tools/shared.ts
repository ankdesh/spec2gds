/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */
import { randomUUID } from "node:crypto";
import type { PromptSection } from "@deepseek-ai/dsh-system-prompt";
import { type ToolRunContext } from "../tool-registry.js";
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { compactWireRange } from "../normalize.js";
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

/** Render fields supplied by the model for either owner domain. */
export function proposalInputRequest(
  _binding: SessionBinding,
  reason: string,
  provided: readonly ProposalInputField[] | undefined,
): ProposalInputRequest | null {
  const fields = (provided ?? []).filter(field => field.name.trim() && field.label.trim());
  if (!fields.length) return null;
  return {
    title: "Complete the proposal details",
    description: reason.trim() || "More information is required before the proposal can be prepared.",
    fields,
    submit_label: "Continue proposal",
  };
}

export function proposedComponentFields(operation: Record<string, unknown>): ProposalInputField[] {
  const ports = Array.isArray(operation.ports) ? operation.ports.filter(isRecord) : [];
  const listed = (direction: string) => ports.filter(port => port.direction === direction).map(port => String(port.name ?? "")).join(", ");
  const width = (port: Record<string, unknown>) => {
    const range = compactWireRange(port.range);
    const vector = typeof range === "string" ? /^\s*(\d+)\s*:\s*0\s*$/.exec(range) : null;
    return vector ? String(Number(vector[1]) + 1) : "1";
  };
  const widths = ports.map(width);
  const widthFields: ProposalInputField[] = new Set(widths).size <= 1
    ? [{ name: "port_width", label: "Port width", description: "Width in bits for the listed ports.", default_value: widths[0] ?? "1" }]
    : ports.map((port, index) => ({
      name: `port_width_${index + 1}`,
      label: `${String(port.name ?? `Port ${index + 1}`)} width`,
      description: `Width in bits for ${String(port.name ?? `port ${index + 1}`)} (${String(port.direction ?? "port")}).`,
      default_value: width(port),
    }));
  return [
    { name: "component_name", label: "Component name", description: "Name for the new component.", default_value: String(operation.name ?? "") },
    { name: "input_ports", label: "Input ports", description: "Comma-separated input port names.", default_value: listed("in") },
    { name: "output_ports", label: "Output ports", description: "Comma-separated output port names.", default_value: listed("out") },
    ...widthFields,
    { name: "behavior", label: "Behavior", description: "Intended module-body behavior.", default_value: String(operation.systemverilog ?? "") },
  ];
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
      : instructions.text("result.20"),
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

