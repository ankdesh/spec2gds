/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */

import { registeredTool, nativeTool, type ToolRunContext } from "../tool-registry.js";
import type { ToolArguments } from "../tool-arguments.js";
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { type OwnerClients } from "../owner-clients.js";
import { validateProposalEnvelope } from "../operation-schemas.js";
import { validateOwnerOperations, verifyOwnerOperationContract, type OwnerOperationContract } from "../owner-operation-schema.js";
import { buildCircuitArtifact, reviewStateForPreview } from "../proposal-pipeline.js";
import { errorFromException, errorFromOwnerResult, logProposalFailure, proposalError } from "../proposal-presentation.js";
import { type ProductState } from "../state.js";
import type { ProposalReview, SessionBinding } from "../types.js";
import { callId, id, json, reviewResult, failureResult, diagnostics, confirmedValues, proposalInputRequest } from "./shared.js";
export function registerCircuitProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  contract: OwnerOperationContract,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  onDomainToolUse?: () => Promise<void>,
  instructions: InstructionBundle = defaultInstructions,
): void {
  agentContext.tools.register(registeredTool({
    ...nativeTool("prepare_circuit_proposal", instructions, contract.tool_schema),
    async execute(args: ToolArguments["prepare_circuit_proposal"], exec: ToolRunContext) {
      await onDomainToolUse?.();
      try { validateProposalEnvelope(args.supported, args.unsupported_reason, args.operations);
        if (args.supported) validateOwnerOperations(contract, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.10"));
      }
      if (!args.supported) {
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", args.required_fields) : null;
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, confirmation_instruction: instructions.text("confirmed-values"), input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: instructions.text("result.6"),
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.11"));
      }
      const inputError = confirmedValues(state, binding, args.confirmed_input_id, args.confirmed_values);
      if (inputError) return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", inputError),
        instructions.text("result.14"));
      let snapshot: Record<string, unknown>;
      try { snapshot = await owners.context(binding, exec.signal); }
      catch (error) {
        const normalized = errorFromException(binding, callId(exec), error);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.15"));
      }
      const revision = snapshot.revision;
      if (typeof revision !== "string" || !revision) {
        const normalized = proposalError(binding, callId(exec), "OWNER_CONTRACT_ERROR", "Circuit snapshot did not include a revision.");
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.16"));
      }
      const proposalId = id("proposal");
      state.discardOpenReviews(binding.sessionId, "circuit");
      let artifact: Record<string, unknown>;
      try { artifact = buildCircuitArtifact(binding, revision, proposalId, id("request"), args); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.10"));
      }
      const batch = artifact.batch as Record<string, unknown>;
      state.createReview({
        proposalId, sessionId: binding.sessionId, callId: callId(exec), domain: "circuit",
        state: "previewing", baseRevision: revision, artifact, preview: null, diagnostics: [], error: null, ownerResult: null,
      });
      try {
        const latest = await owners.operationContract(binding, exec.signal);
        verifyOwnerOperationContract(contract, latest);
        const preview = await owners.previewCircuit(binding, batch, exec.signal);
        const next = reviewStateForPreview("circuit", preview.status);
        const normalized = next === "ready" ? null : errorFromOwnerResult(binding, proposalId, preview);
        if (normalized) logProposalFailure(binding, normalized, proposalId);
        const review = state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview: { ...preview, base_document: snapshot.document }, diagnostics: diagnostics(preview), error: normalized,
        });
        if (review.state === "ready") await onReviewPrepared?.(review);
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
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, ["previewing"],
          normalized.error_code === "STALE_REVISION" ? "stale" : "rejected", {
            diagnostics: normalized.owner_diagnostics, error: normalized,
          }));
      }
    },
  }));
}

