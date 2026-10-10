/** Submit a flow-authored Spec batch through semantic guards and durable service receipts. */

import type { ToolRunContext } from "../tool-registry.js";
export interface SpecChangeInputs { supported: boolean; unsupported_reason: string | null; base_source_revision_hash: string; title: string; summary: string; rationale: string; assumptions: string[]; operations: unknown[]; architecture_review_id?: string; }
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue } from "@deepseek-ai/dsh-util-values";
import { ServiceError, type ServiceClients } from "../service-clients.js";
import { validateProposalEnvelope } from "../operation-schemas.js";
import { normalizeSpecFormatting } from "../normalize.js";
import { validateArchitectureOperations } from "../architecture-review.js";
import { validateServiceOperations, verifyServiceOperationContract, type ServiceOperationContract } from "../service-operation-schema.js";
import { buildSpecArtifact, reviewStateForPreview } from "../proposal-pipeline.js";
import { errorFromException, errorFromOwnerResult, logProposalFailure, proposalError } from "../proposal-presentation.js";
import { artifactDigest, type ProductState } from "../state.js";
import type { ProposalReview, SessionBinding } from "../types.js";
import { isRecord } from "../types.js";
import { callId, id, json, reviewResult, failureResult, diagnostics } from "../tools/shared.js";
/** Determine architecture approval from operation types, never request prose. */
export function requiresSpecArchitecture(operations: readonly unknown[]): boolean {
  const contentOnly = new Set(["set_entity_metadata", "upsert_narrative_block", "delete_narrative_block", "reorder_narrative_blocks", "set_narrative_entity_links"]);
  return operations.some(operation => !isRecord(operation) || !contentOnly.has(String(operation.type)));
}
export function submitSpecChangeCommand(
  binding: SessionBinding,
  state: ProductState,
  owners: ServiceClients,
  contract: ServiceOperationContract,
  instructions: InstructionBundle = defaultInstructions,
) {
  return {
    async execute(args: SpecChangeInputs, exec: ToolRunContext) {
      let policy: Awaited<ReturnType<ServiceClients["specPolicy"]>>;
      try { policy = await owners.specPolicy(binding.serviceUrl, exec.signal); }
      catch (error) {
        return failureResult(errorFromException(binding, callId(exec), error), instructions.text("result.9"));
      }
      try { args = { ...args, operations: snapshotJsonValue(normalizeSpecFormatting(args.operations, binding.documentId)) as typeof args.operations };
        validateProposalEnvelope(args.supported, args.unsupported_reason, args.operations);
        if (args.supported) validateServiceOperations(contract, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.10"));
      }
      if (!policy.submissions) return failureResult(proposalError(binding, callId(exec), "SERVICE_CONTRACT_ERROR", "Spec flows require durable service submission receipts."), "No write was submitted.");
      if (!args.supported) return failureResult(proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason), "The flow draft cannot be submitted.");
      const previous = state.reviewForCall(binding.sessionId, callId(exec));
      if (previous) {
        const replay = buildSpecArtifact(binding, args.base_source_revision_hash, previous.proposalId, args);
        if (artifactDigest(replay) !== previous.artifactDigest) {
          return failureResult(proposalError(binding, previous.proposalId, "INVALID_PROPOSAL", instructions.text("result.12")),
            instructions.text("context.44"));
        }
        let review = previous;
        if (["ready", "applying", "reconcile"].includes(review.state) && policy.submissions) {
          try {
            const receipt = await owners.specSubmission(binding, review.proposalId, exec.signal);
            if (isRecord(receipt.artifact) && artifactDigest(receipt.artifact) === review.artifactDigest
                && receipt.state === "applied" && isRecord(receipt.owner_result)) {
              review = state.transitionReview(binding.sessionId, review.proposalId, [review.state], "applied",
                { error: null, diagnostics: [], serviceResult: receipt.owner_result });
            }
          } catch { /* Preserve uncertain state until the exact owner receipt is available. */ }
        }
        return reviewResult(review, instructions);
      }
      try {
        const structural = requiresSpecArchitecture(args.operations);
        if (structural) {
          const architecture = state.requireArchitecture(binding.sessionId, args.architecture_review_id, args.base_source_revision_hash);
          if (architecture.approved_operations_digest && architecture.approved_operations_digest !== artifactDigest(args.operations)) throw new Error("The operation batch differs from the architecture review.");
          validateArchitectureOperations(architecture.plan, args.operations);
        }
        for (const operation of args.operations) {
          if (!isRecord(operation) || operation.type !== "create_entity" || operation.kind !== "component") continue;
          const explanation = args.operations.find(edit => isRecord(edit) && edit.type === "set_entity_metadata"
            && isRecord(edit.entity) && edit.entity.entity_id === operation.entity_id
            && edit.entity.entity_kind === "component" && edit.entity.document_id === binding.documentId);
          if (!isRecord(explanation) || typeof explanation.description !== "string" || !explanation.description.trim()) {
            throw new Error(`New component ${String(operation.name)} (alias ${String(operation.entity_id)}) needs set_entity_metadata.description in the same proposal, referencing this alias with entity_kind=component and document_id=${binding.documentId}.`);
          }
        }
      } catch (error) { return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error)), instructions.text("result.13")); }
      const proposalArgs = args;
      let context: Record<string, unknown>;
      try { context = await owners.context(binding, exec.signal); }
      catch (error) {
        const normalized = errorFromException(binding, callId(exec), error);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.15"));
      }
      const revision = context.source_revision_hash;
      if (typeof revision !== "string" || !revision) {
        const normalized = proposalError(binding, callId(exec), "SERVICE_CONTRACT_ERROR", "Spec context did not include a source revision.");
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.16"));
      }
      if (args.base_source_revision_hash !== revision) {
        return failureResult(proposalError(binding, callId(exec), "STALE_REVISION", {
          diagnostics: ["The specification changed after the context used to author these operations."],
          submitted_source_revision_hash: args.base_source_revision_hash,
          source_revision_hash: revision,
        }, true), instructions.text("result.17"));
      }
      const proposalId = id("proposal");
      let artifact: Record<string, unknown>;
      try { artifact = buildSpecArtifact(binding, revision, proposalId, proposalArgs); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.10"));
      }
      state.createReview({
        proposalId, sessionId: binding.sessionId, callId: callId(exec), domain: "spec",
        state: "previewing", baseRevision: revision, artifact, preview: null, diagnostics: [], error: null, serviceResult: null,
      });
      try {
        const latest = await owners.operationContract(binding, exec.signal);
        verifyServiceOperationContract(contract, latest);
        const preview = await owners.previewSpec(binding, artifact, exec.signal);
        const next = reviewStateForPreview("spec", preview.status);
        const normalized = next === "ready" ? null : errorFromOwnerResult(binding, proposalId, preview);
        if (normalized) logProposalFailure(binding, normalized, proposalId);
        let review = state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview, diagnostics: diagnostics(preview), error: normalized,
        });
        if (review.state === "ready" && policy.submissions) {
          state.transitionReview(binding.sessionId, proposalId, ["ready"], "applying");
          const result = await owners.submitSpec(binding, artifact, exec.signal);
          if (result.status !== "applied" && result.status !== "approval_required") {
            throw new ServiceError(502, "The service returned an unknown submission outcome.", true);
          }
          review = state.transitionReview(binding.sessionId, proposalId, ["applying"],
            result.status === "applied" ? "applied" : "ready", { serviceResult: result });
        }
        return reviewResult(review, instructions);
      } catch (error) {
        const confirmed = state.getReview(binding.sessionId, proposalId);
        // Execution notifications cannot relabel the persisted owner result.
        if (confirmed && ["ready", "applied", "sent"].includes(confirmed.state)) {
          console.warn(JSON.stringify({ event: "spec2gds.execution_notification_failed", proposal_id: proposalId, domain: binding.domain }));
          return reviewResult(confirmed);
        }
        const normalized = errorFromException(binding, proposalId, error);
        logProposalFailure(binding, normalized, proposalId);
        const current = state.getReview(binding.sessionId, proposalId)!;
        const uncertain = current.state === "applying" && isRecord(error) && error.uncertain === true;
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, [current.state],
          uncertain ? "reconcile" : normalized.error_code === "STALE_REVISION" ? "stale" : "rejected", {
            diagnostics: normalized.owner_diagnostics, error: normalized,
          }));
      }
    },
  };
}

/** Explicit recovery of a committed proposal intent. Repeat only its exact
 * stable artifact when the service has no receipt; the service keeps save and
 * content-decision authority. Callers must first validate the architecture receipt.
 */
export async function recoverSpecSubmission(binding: SessionBinding, state: ProductState, owners: ServiceClients, review: ProposalReview, signal?: AbortSignal): Promise<Record<string, unknown> | undefined> {
  try {
    const receipt = await owners.specSubmission(binding, review.proposalId, signal);
    if (!isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== review.artifactDigest) return undefined;
    return receipt;
  } catch (error) {
    if (!(error instanceof ServiceError) || error.status !== 404) throw error;
  }
  if (!["previewing", "ready", "applying", "reconcile"].includes(review.state)) throw new Error("The recorded proposal cannot be submitted again after a terminal decision.");
  if (artifactDigest(review.artifact) !== review.artifactDigest) throw new Error("The recorded proposal artifact changed.");
  const policy = await owners.specPolicy(binding.serviceUrl);
  if (!policy.submissions) throw new Error("The selected service has no durable submission receipts.");
  let current = state.getReview(binding.sessionId, review.proposalId)!;
  if (current.state === "previewing") {
    const preview = await owners.previewSpec(binding, review.artifact, signal);
    const next = reviewStateForPreview("spec", preview.status);
    current = state.transitionReview(binding.sessionId, review.proposalId, [current.state], next, { preview, diagnostics: diagnostics(preview), error: next === "ready" ? null : errorFromOwnerResult(binding, review.proposalId, preview) });
    if (next !== "ready") throw new Error("The recorded proposal did not pass service validation.");
  }
  // The durable applying claim precedes the replay. Its ID and bytes remain
  // unchanged, so an in-flight prior save and this replay converge at the service.
  state.transitionReview(binding.sessionId, review.proposalId, [current.state], "applying");
  const result = await owners.submitSpec(binding, review.artifact, signal);
  if (!["applied", "approval_required"].includes(String(result.status))) throw new ServiceError(502, "The service did not identify the recovered submission outcome.", true);
  state.transitionReview(binding.sessionId, review.proposalId, ["applying"], result.status === "applied" ? "applied" : "ready", { serviceResult: result });
  return owners.specSubmission(binding, review.proposalId, signal);
}
