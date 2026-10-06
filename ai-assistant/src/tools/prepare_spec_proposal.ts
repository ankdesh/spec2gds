/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */

import { registeredTool, nativeTool, type ToolRunContext } from "../tool-registry.js";
import type { ToolArguments } from "../tool-arguments.js";
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue } from "@deepseek-ai/dsh-util-values";
import { OwnerError, type OwnerClients } from "../owner-clients.js";
import { validateProposalEnvelope } from "../operation-schemas.js";
import { normalizeSpecFormatting } from "../normalize.js";
import { validateArchitectureOperations } from "../architecture-review.js";
import { specFormattingAdmission, validateOwnerOperations, verifyOwnerOperationContract, type OwnerOperationContract } from "../owner-operation-schema.js";
import { buildSpecArtifact, reviewStateForPreview } from "../proposal-pipeline.js";
import { errorFromException, errorFromOwnerResult, logProposalFailure, proposalError } from "../proposal-presentation.js";
import { artifactDigest, type ProductState } from "../state.js";
import type { ProposalReview, SessionBinding } from "../types.js";
import { isRecord } from "../types.js";
import { callId, id, json, reviewResult, failureResult, diagnostics, confirmedValues, proposalInputRequest, proposedComponentFields } from "./shared.js";
export function registerSpecProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  contract: OwnerOperationContract,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  currentUserRequest?: () => string,
  onDomainToolUse?: () => Promise<void>,
  instructions: InstructionBundle = defaultInstructions,
): () => void {
  return agentContext.tools.register(registeredTool({
    ...nativeTool("prepare_spec_proposal", instructions, specFormattingAdmission(contract.tool_schema)),
    async execute(args: ToolArguments["prepare_spec_proposal"], exec: ToolRunContext) {
      await onDomainToolUse?.();
      let policy: Awaited<ReturnType<OwnerClients["specPolicy"]>>;
      try { policy = await owners.specPolicy(binding.ownerUrl, exec.signal); }
      catch (error) {
        return failureResult(errorFromException(binding, callId(exec), error), instructions.text("result.9"));
      }
      try { args = { ...args, operations: snapshotJsonValue(normalizeSpecFormatting(args.operations, binding.documentId)) as typeof args.operations };
        validateProposalEnvelope(args.supported, args.unsupported_reason, args.operations);
        if (args.supported) validateOwnerOperations(contract, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.10"));
      }
      if (!args.supported) {
        const providedFields = args.required_fields ?? [];
        const missingFields = policy.approval_policy === "automatic"
          ? providedFields.filter(field => !field.default_value.trim()) : providedFields;
        if (policy.approval_policy === "automatic" && providedFields.length && !missingFields.length) {
          return json({ success: false, suggested_defaults: providedFields,
            instruction: instructions.text("result.5") });
        }
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", missingFields) : null;
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, confirmation_instruction: instructions.text("confirmed-values"), input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: instructions.text("result.6"),
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, instructions.text("result.11"));
      }
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
                { error: null, diagnostics: [], ownerResult: receipt.owner_result });
              await onReviewPrepared?.(review);
            }
          } catch { /* Preserve uncertain state until the exact owner receipt is available. */ }
        }
        return reviewResult(review, instructions);
      }
      const componentCreation = binding.scope === "document"
        ? args.operations.find(operation => isRecord(operation) && operation.type === "create_entity" && operation.kind === "component")
        : undefined;
      try {
        const structural = args.operations.some(operation => isRecord(operation) && (
          ["create_entity", "delete_entity", "set_internal_design", "clear_internal_design", "upsert_instance", "delete_instance", "upsert_connection", "delete_connection", "upsert_component_port", "delete_component_port", "upsert_bus_interface", "delete_bus_interface", "upsert_channel", "delete_channel"].includes(String(operation.type))
          || (["upsert_section", "delete_section"].includes(String(operation.type)) && ["instances", "connections", "ports"].includes(String(operation.section_type)))));
        if (structural) {
          const architecture = state.requireArchitecture(binding.sessionId, args.architecture_review_id, args.base_source_revision_hash);
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
      if (policy.approval_policy === "review" && interactiveForms && componentCreation && !args.confirmed_input_id && !args.architecture_review_id) {
        const fields = args.required_fields?.length ? args.required_fields : proposedComponentFields(componentCreation as Record<string, unknown>);
        const requiredInput = proposalInputRequest(binding, "Review the component details before the proposal is prepared.", fields);
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, confirmation_instruction: instructions.text("confirmed-values"), input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: instructions.text("result.7"),
        });
      }
      const inputError = confirmedValues(state, binding, args.confirmed_input_id, args.confirmed_values);
      if (inputError) return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", inputError),
        instructions.text("result.14"));
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
        const normalized = proposalError(binding, callId(exec), "OWNER_CONTRACT_ERROR", "Spec context did not include a source revision.");
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
        state: "previewing", baseRevision: revision, artifact, preview: null, diagnostics: [], error: null, ownerResult: null,
      });
      try {
        const latest = await owners.operationContract(binding, exec.signal);
        verifyOwnerOperationContract(contract, latest);
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
            throw new OwnerError(502, "The owner returned an unknown submission outcome.", true);
          }
          review = state.transitionReview(binding.sessionId, proposalId, ["applying"],
            result.status === "applied" ? "applied" : "ready", { ownerResult: result });
        }
        if (review.state === "ready" || review.state === "applied") await onReviewPrepared?.(review);
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
  }));
}

