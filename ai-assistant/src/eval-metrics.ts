import { isRecord } from "./types.js";

export interface EvaluationMetrics {
  cases: number;
  proposalCalls: number;
  schemaValidProposalCalls: number;
  firstPreviewReadyCases: number;
  proposedOperations: number;
  appliedOrSentOperations: number;
  clarificationTurns: number;
  retries: number;
  latencyMs: { count: number; total: number };
  tokens: { input: number; cacheRead: number; output: number; reasoning: number };
  falseCompletionViolations: number;
}

export function parseJsonLines(text: string): Record<string, unknown>[] {
  return text.split(/\r?\n/).filter(line => line.trim()).map((line, index) => {
    const value: unknown = JSON.parse(line);
    if (!isRecord(value)) throw new Error(`JSONL row ${index + 1} is not an object.`);
    return value;
  });
}

function contentText(value: unknown): string {
  if (!isRecord(value)) return "";
  const message = isRecord(value.message) ? value.message : value;
  if (!Array.isArray(message.content)) return "";
  return message.content.filter(isRecord).filter(block => block.type === "text" && typeof block.text === "string")
    .map(block => String(block.text)).join("\n");
}

function resultPayload(event: Record<string, unknown>): Record<string, unknown> | null {
  const data = isRecord(event.data) ? event.data : {};
  const message = isRecord(data.message) ? data.message : {};
  if (!Array.isArray(message.content)) return null;
  const block = message.content.filter(isRecord).flatMap(item => item.type === "tool-result" && Array.isArray(item.content) ? item.content.filter(isRecord) : [])
    .find(item => item.type === "text" && typeof item.text === "string");
  if (!block || typeof block.text !== "string") return null;
  try { const parsed: unknown = JSON.parse(block.text); return isRecord(parsed) ? parsed : null; }
  catch { return null; }
}

export function calculateMetrics(events: Record<string, unknown>[], caseCount: number): EvaluationMetrics {
  const metrics: EvaluationMetrics = {
    cases: caseCount, proposalCalls: 0, schemaValidProposalCalls: 0, firstPreviewReadyCases: 0,
    proposedOperations: 0, appliedOrSentOperations: 0, clarificationTurns: 0, retries: 0,
    latencyMs: { count: 0, total: 0 }, tokens: { input: 0, cacheRead: 0, output: 0, reasoning: 0 },
    falseCompletionViolations: 0,
  };
  const proposalCallsByTurn = new Map<number, number>();
  const proposalTurns = new Set<number>();
  const firstResultSeen = new Set<number>();
  const turnStarts = new Map<number, number>();
  for (const event of events) {
    const data = isRecord(event.data) ? event.data : {};
    const turn = typeof data.turn === "number" ? data.turn : 0;
    if (event.type === "turn/start" && typeof event.time === "number") turnStarts.set(turn, event.time);
    if (event.type === "turn/end" && typeof event.time === "number" && turnStarts.has(turn)) {
      metrics.latencyMs.count += 1;
      metrics.latencyMs.total += event.time - turnStarts.get(turn)!;
    }
    if (event.type === "tool/call" && (data.name === "prepare_spec_proposal" || data.name === "prepare_circuit_proposal")) {
      metrics.proposalCalls += 1;
      proposalTurns.add(turn);
      const count = proposalCallsByTurn.get(turn) ?? 0;
      if (count > 0) metrics.retries += 1;
      proposalCallsByTurn.set(turn, count + 1);
    }
    if (event.type === "tool/result") {
      const payload = resultPayload(event);
      const metadata = isRecord(data.meta) && data.meta.kind === "spec2gds.review" ? data.meta : null;
      if ((!payload || !("success" in payload)) && !metadata) continue;
      metrics.schemaValidProposalCalls += 1;
      const review = payload && isRecord(payload.review) ? payload.review : null;
      const artifact = review && isRecord(review.artifact) ? review.artifact : {};
      const batch = isRecord(artifact.batch) ? artifact.batch : {};
      const operations = Array.isArray(artifact.operations) ? artifact.operations : Array.isArray(batch.operations) ? batch.operations : [];
      const count = review ? operations.length : Number(metadata?.operationCount ?? payload?.operation_count ?? 0);
      const state = review?.state ?? metadata?.state ?? payload?.state;
      metrics.proposedOperations += count;
      if (state === "applied" || state === "sent") metrics.appliedOrSentOperations += count;
      if (typeof state === "string" && !firstResultSeen.has(turn)) {
        firstResultSeen.add(turn);
        if (state === "ready") metrics.firstPreviewReadyCases += 1;
      }
    }
    if (event.type === "assistant/message") {
      const usage = isRecord(data.usage) ? data.usage : {};
      metrics.tokens.input += Number(usage.inputTokens ?? 0);
      metrics.tokens.cacheRead += Number(usage.cacheReadTokens ?? 0);
      metrics.tokens.output += Number(usage.outputTokens ?? 0);
      metrics.tokens.reasoning += Number(usage.reasoningTokens ?? 0);
      const text = contentText(data);
      if (!proposalTurns.has(turn) && /\?\s*$/.test(text)) metrics.clarificationTurns += 1;
    }
    if (event.type === "spec2gds/evaluation" && data.assertion === "false_completion" && data.passed === false) {
      metrics.falseCompletionViolations += 1;
    }
  }
  return metrics;
}
