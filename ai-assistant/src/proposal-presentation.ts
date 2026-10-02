import { OwnerError } from "./owner-clients.js";
import { OwnerContractError } from "./owner-operation-schema.js";
import type {
  ProposalChangeSummary,
  ProposalError,
  ProposalErrorCode,
  ProposalIssue,
  ProposalReview,
  PublicProposalReview,
  SessionBinding,
} from "./types.js";
import { isRecord } from "./types.js";

function strings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function detailText(value: unknown): string {
  if (typeof value === "string") return value;
  if (isRecord(value)) {
    for (const key of ["message", "detail", "reason"]) {
      if (typeof value[key] === "string") return value[key];
    }
  }
  try { return JSON.stringify(value); }
  catch { return String(value); }
}

function issue(value: unknown, fallbackCode: string): ProposalIssue {
  const record = isRecord(value) ? value : {};
  const actions = strings(record.suggested_actions ?? record.suggestedActions);
  const targetValue = record.target ?? record.target_element ?? record.path ?? null;
  return {
    error_code: typeof record.code === "string" && record.code ? record.code : fallbackCode,
    target: typeof targetValue === "string" && targetValue ? targetValue : null,
    details: detailText(value),
    suggested_actions: actions,
  };
}

function diagnosticValues(value: unknown): unknown[] {
  if (Array.isArray(value)) return value.length ? value : [];
  if (isRecord(value) && Array.isArray(value.diagnostics)) return value.diagnostics;
  return value === undefined || value === null ? [] : [value];
}

function bindingTarget(binding: SessionBinding): string {
  return binding.scope === "entity" && binding.entityId
    ? `${binding.entityKind ?? "entity"}:${binding.entityId}`
    : `document:${binding.documentId}`;
}

export function proposalError(
  binding: SessionBinding,
  correlationId: string,
  errorCode: ProposalErrorCode,
  diagnostics: unknown,
  retryable = false,
): ProposalError {
  const values = diagnosticValues(diagnostics);
  const issues = values.map(value => issue(value, errorCode));
  const first = issues[0] ?? {
    error_code: errorCode,
    target: null,
    details: "The proposal could not be prepared.",
    suggested_actions: [],
  };
  return {
    error_code: errorCode,
    target: first.target ?? bindingTarget(binding),
    details: first.details,
    retryable,
    suggested_actions: [...new Set(issues.flatMap(item => item.suggested_actions))],
    issues,
    owner_diagnostics: diagnostics,
    correlation_id: correlationId,
  };
}

export function errorCodeForOwnerStatus(status: unknown): { code: ProposalErrorCode; retryable: boolean } {
  switch (status) {
    case "stale":
    case "conflict":
    case "revision_conflict":
      return { code: "STALE_REVISION", retryable: true };
    case "locked":
      return { code: "OWNER_LOCKED", retryable: true };
    case "provider_failed":
      return { code: "OWNER_UNAVAILABLE", retryable: true };
    default:
      return { code: "OWNER_REJECTED", retryable: false };
  }
}

export function errorFromOwnerResult(
  binding: SessionBinding,
  correlationId: string,
  result: Record<string, unknown>,
): ProposalError {
  const classification = errorCodeForOwnerStatus(result.status);
  return proposalError(binding, correlationId, classification.code, result.diagnostics ?? result.detail ?? result, classification.retryable);
}

export function errorFromException(
  binding: SessionBinding,
  correlationId: string,
  error: unknown,
): ProposalError {
  if (error instanceof OwnerContractError) {
    return proposalError(binding, correlationId, "OWNER_CONTRACT_ERROR", error.message, false);
  }
  if (error instanceof OwnerError) {
    if (error.status === 409) return proposalError(binding, correlationId, "STALE_REVISION", error.detail, true);
    if (error.status === 502 && typeof error.detail === "string" && (
      error.detail.startsWith("Owner response exceeded")
      || error.detail.startsWith("Owner returned non-JSON")
      || error.detail.startsWith("Owner returned a non-object JSON")
    )) {
      return proposalError(binding, correlationId, "OWNER_CONTRACT_ERROR", error.detail, false);
    }
    if (error.status === 408 || error.status === 429 || error.status >= 500) {
      return proposalError(binding, correlationId, "OWNER_UNAVAILABLE", error.detail, true);
    }
    return proposalError(binding, correlationId, "OWNER_REJECTED", error.detail, false);
  }
  return proposalError(binding, correlationId, "INTERNAL_ERROR", error instanceof Error ? error.message : String(error), false);
}

function operations(review: ProposalReview): Record<string, unknown>[] {
  const direct = review.artifact.operations;
  if (Array.isArray(direct)) return direct.filter(isRecord);
  const batch = isRecord(review.artifact.batch) ? review.artifact.batch : {};
  return Array.isArray(batch.operations) ? batch.operations.filter(isRecord) : [];
}

function operationCounts(review: ProposalReview): Array<{ type: string; count: number }> {
  const counts = new Map<string, number>();
  for (const operation of operations(review)) {
    const type = typeof operation.type === "string" && operation.type ? operation.type : "unknown";
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return [...counts].sort(([left], [right]) => left.localeCompare(right)).map(([type, count]) => ({ type, count }));
}

function specTargets(preview: Record<string, unknown>): string[] {
  if (!Array.isArray(preview.diff)) return [];
  return preview.diff.filter(isRecord).flatMap(item => {
    if (typeof item.path !== "string") return [];
    return [`${typeof item.change === "string" ? item.change : "changed"} ${item.path}`];
  });
}

function circuitTargets(preview: Record<string, unknown>): string[] {
  const diff = isRecord(preview.diff) ? preview.diff : {};
  const targets: string[] = [];
  for (const key of ["added", "removed", "changed"] as const) {
    if (!Array.isArray(diff[key])) continue;
    for (const value of diff[key]) {
      if (isRecord(value) && typeof value.id === "string") targets.push(`${key}:${String(value.kind ?? "element")}:${value.id}`);
    }
  }
  if (Array.isArray(diff.connections_changed)) {
    for (const value of diff.connections_changed) if (typeof value === "string") targets.push(`connections_changed:net:${value}`);
  }
  return targets;
}

function diagnosticTexts(value: unknown): string[] {
  return diagnosticValues(value).map(detailText).filter(Boolean);
}

export function changeSummaryFor(review: ProposalReview): ProposalChangeSummary {
  const counts = operationCounts(review);
  const changedTargets = [...new Set(review.preview
    ? review.domain === "spec" ? specTargets(review.preview) : circuitTargets(review.preview)
    : [])].sort();
  const count = counts.reduce((total, item) => total + item.count, 0);
  const countText = counts.map(item => `${item.count} ${item.type}`).join(", ");
  const targetText = changedTargets.length
    ? ` Owner preview reports ${changedTargets.length} changed target${changedTargets.length === 1 ? "" : "s"}.`
    : " Owner preview reports no semantic diff targets.";
  return {
    text: `Proposes ${count} operation${count === 1 ? "" : "s"}${countText ? ` (${countText})` : ""}.${targetText}`,
    operationCounts: counts,
    changedTargets,
    assumptions: strings(review.artifact.assumptions),
    diagnostics: diagnosticTexts(review.diagnostics),
  };
}

export function publicReview(review: ProposalReview): PublicProposalReview {
  const { artifactDigest: _digest, ...value } = review;
  return { ...value, changeSummary: changeSummaryFor(review) };
}

export function logProposalFailure(binding: SessionBinding, error: ProposalError, proposalId?: string): void {
  console.error(JSON.stringify({
    event: "spec2gds.proposal_failed",
    correlation_id: error.correlation_id,
    domain: binding.domain,
    document_id: binding.documentId,
    proposal_id: proposalId ?? null,
    error_code: error.error_code,
    details: error.details,
    issues: error.issues,
    retryable: error.retryable,
  }));
}
