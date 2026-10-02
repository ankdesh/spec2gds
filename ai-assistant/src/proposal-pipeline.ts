/** Construct normalized immutable owner artifacts from model-authored operations.
 * Preserve the authored source revision and immutable binding. Artifact creation
 * and preview are distinct from owner application policy; human review actions
 * later use stored content rather than replacement browser payloads. */
import { normalizeCircuitOperations, normalizeSpecOperations } from "./normalize.js";
import type { ReviewState, SessionBinding } from "./types.js";

export interface ProposalInput {
  supported: boolean;
  unsupported_reason: string | null;
  title: string;
  summary: string;
  rationale: string;
  assumptions: string[];
  operations: unknown[];
}

export function buildSpecArtifact(
  binding: SessionBinding,
  revision: string,
  proposalId: string,
  input: ProposalInput,
): Record<string, unknown> {
  return {
    schema_version: "1.0",
    kind: "spec_change_proposal",
    proposal_id: proposalId,
    document_id: binding.documentId,
    scope: binding.scope,
    target: binding.scope === "entity" ? {
      document_id: binding.documentId,
      entity_kind: binding.entityKind,
      entity_id: binding.entityId,
    } : null,
    base_source_revision_hash: revision,
    title: input.title,
    summary: input.summary,
    rationale: input.rationale,
    assumptions: input.assumptions,
    operations: normalizeSpecOperations(input.operations, proposalId),
  };
}

export function buildCircuitArtifact(
  binding: SessionBinding,
  revision: string,
  proposalId: string,
  requestId: string,
  input: ProposalInput,
): Record<string, unknown> {
  return {
    schema_version: "1",
    kind: "circuit_change_proposal",
    proposal_id: proposalId,
    document_id: binding.documentId,
    base_revision: revision,
    title: input.title,
    summary: input.summary,
    rationale: input.rationale,
    assumptions: input.assumptions,
    batch: {
      request_id: requestId,
      expected_revision: revision,
      operations: normalizeCircuitOperations(input.operations),
    },
  };
}

export function reviewStateForPreview(domain: "spec" | "circuit", status: unknown): ReviewState {
  if (domain === "spec") return status === "valid" ? "ready" : status === "stale" ? "stale" : "rejected";
  return status === "accepted" ? "ready" : status === "conflict" || status === "revision_conflict" ? "stale" : "rejected";
}
