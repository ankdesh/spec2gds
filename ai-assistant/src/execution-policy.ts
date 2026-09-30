/** Product resource ceilings and proposal ownership for native event/goal execution. */
import type { EventSystemSnapshot, ExecutionLimits } from "@deepseek-ai/dsh-event-system";
import { isRecord } from "./types.js";

const ceilings = {
  goal: { maxRounds: 24, maxRequests: 96, maxTokens: 1_000_000, maxActiveMillis: 7_200_000, maxMembers: 1, maxConcurrency: 1 },
  orchestrated: { maxRounds: 24, maxRequests: 144, maxTokens: 2_000_000, maxActiveMillis: 7_200_000, maxMembers: 21, maxConcurrency: 4 },
};

/** Resolve explicitly configured limits and reject values above the existing product ceilings. */
export function executionLimits(mode: "goal" | "orchestrated", value: unknown, outputTokens: number): ExecutionLimits {
  if (!isRecord(value)) throw new Error(`execution.${mode} must contain explicit resource limits.`);
  const names = ["maxRounds", "maxRequests", "maxTokens", "maxActiveMillis", "maxMembers", "maxConcurrency", "maxPending", "maxEvents", "maxPayloadBytes", "maxDepth"] as const;
  const extra = Object.keys(value).filter(name => !names.includes(name as typeof names[number]));
  if (extra.length) throw new Error(`Unknown execution limit: ${extra.join(", ")}.`);
  for (const name of names) {
    if (typeof value[name] !== "number" || !Number.isSafeInteger(value[name]) || Number(value[name]) < 1) {
      throw new Error(`execution.${mode}.${name} must be a positive safe integer.`);
    }
    const cap = ceilings[mode][name as keyof typeof ceilings.goal];
    if (cap !== undefined && Number(value[name]) > cap) throw new Error(`execution.${mode}.${name} exceeds the product ceiling ${cap}.`);
  }
  if (Number(value.maxConcurrency) > Number(value.maxMembers)) throw new Error("Execution concurrency exceeds member capacity.");
  return { ...value, maxOutputTokens: outputTokens } as ExecutionLimits;
}

/** Only the primary may prepare a proposal, after review of the latest orchestrated request. */
export function proposalExecutionDenial(state: EventSystemSnapshot, member: string): string | undefined {
  if (state.status !== "active") return `Execution is ${state.status}; resume it before preparing a proposal.`;
  if (member !== state.definition.primary) return "Only the primary agent may prepare owner proposals.";
  if (state.mode === "goal") return undefined;
  const request = state.events.findLast(event => event.type === "user.requested");
  if (!request) return "An orchestrated proposal requires a recorded user request.";
  const reviewed = state.events.filter(event => event.type === "review.ready").some(event => {
    let current = event;
    while (current.causation) {
      const cause = state.events.find(candidate => candidate.id === current.causation);
      if (!cause) return false;
      if (cause.id === request.id) return true;
      current = cause;
    }
    return false;
  });
  return reviewed ? undefined : "Wait for the reviewer result before preparing this request's owner proposal.";
}
