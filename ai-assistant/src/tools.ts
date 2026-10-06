/** Model capabilities for bound owner context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and owner
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */
import { randomUUID } from "node:crypto";
import type { PromptSection } from "@deepseek-ai/dsh-system-prompt";
import { defineTool, type ToolRunContext } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { OwnerError, type OwnerClients } from "./owner-clients.js";
import { catalogPromptSectionsFor, promptSectionsFor, shapeBoundContext, type BoundPromptCatalog } from "./domain-context.js";
import { validateProposalEnvelope } from "./operation-schemas.js";
import { compactWireRange, normalizeSpecFormatting } from "./normalize.js";
import { validateArchitectureOperations } from "./architecture-review.js";
import { parseOwnerOperationContract, specFormattingAdmission, validateOwnerOperations, verifyOwnerOperationContract, type OwnerOperationContract } from "./owner-operation-schema.js";
import { buildCircuitArtifact, buildSpecArtifact, reviewStateForPreview } from "./proposal-pipeline.js";
import {
  errorFromException,
  errorFromOwnerResult,
  logProposalFailure,
  proposalError,
  publicReview,
} from "./proposal-presentation.js";
import { artifactDigest, type ProductState } from "./state.js";
import type { ProposalError, ProposalReview, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

const resultOutput = {
  schema: { type: "json" } as const,
  render: (_args: unknown, value: unknown) => [{ type: "text" as const, text: JSON.stringify(value) }],
};

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

const REQUIRED_FIELD_SCHEMA = {
  type: "object",
  properties: {
    name: { type: "string", required: true },
    label: { type: "string", required: true },
    description: { type: "string", required: true },
    default_value: { type: "string", required: true },
  },
  additionalProperties: false,
} as const;

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

const SPEC_PROPOSAL_DESCRIPTION = `Prepare, owner-preview, and submit a typed Spec proposal after reading get_bound_context. Copy its exact source revision into base_source_revision_hash. The owner applies valid submissions automatically unless human approval is required.
For new entities, provide a proposal-local entity_id alias and use that same alias in dependent references. If entity_id is omitted, the creation operation_id is its alias. Component explanations use set_entity_metadata with entity={document_id: bound_document_id,entity_kind:"component",entity_id: creation_alias} and a nonempty description. entry_design applies only to design creation.
Use the operation types and field shapes in this binding's owner-published tool schema. Reuse existing IDs from context and use local aliases for new entities and their dependent references. Stay within the writable boundary. Complete replacements must copy unchanged fields. SystemVerilog content is module-body text only. New entities or architectural changes require an approved architecture_review_id; every new component needs an explanation in the same atomic proposal. Generate the approved concrete interfaces. The owner performs semantic validation.`;

const CIRCUIT_PROPOSAL_DESCRIPTION = `Prepare and owner-preview a typed Circuit operation batch after reading get_bound_context. This never commits or submits it.
Use the operation types and field shapes in this binding's owner-published tool schema. Use exact IDs from context, order dependent operations, and copy unchanged fields in complete replacements. Do not author geometry, routes, labels, or layout. The owner performs semantic validation.`;

export function structuredQuestionPrompt(enabled: boolean): PromptSection | null {
  if (!enabled) return null;
  return {
    name: "spec2gds:interactive-clarification",
    order: 250,
    text: `INTERACTIVE CLARIFICATION
After reading bound context, if a concrete proposal needs user-supplied values, call its prepare_*_proposal tool with supported=false, an empty operations list, and every missing value in required_fields. Supply an LLM-suggested default_value for every field. When the details card is submitted, use the confirmed values as authoritative, pass its input_id as confirmed_input_id and its exact values as confirmed_values, and author the matching typed operations yourself. The client will show one editable details card and continue the proposal from its submission. Do not list missing proposal fields in an ordinary assistant response and end the turn. For a non-proposal question or choice, you MUST call ask_user_question. Ask only for information that cannot be derived from bound context, and do not ask about optional data that can safely retain its current or default value. For immediate clarification in a goal or orchestrated request, use these same human input tools. When wait_for_event is available, use it for a durable correlated human answer or declared event that should suspend work across turns; do not burn continuation rounds polling for that response. Owner proposal review waits are correlated by the host.`,
  };
}

function callId(exec: ToolRunContext): string { return String(exec.callId); }
function id(prefix: string): string { return `${prefix}_${randomUUID().replaceAll("-", "")}`; }

function json(value: unknown): JsonValue {
  const snapshot = snapshotJsonValue(value);
  if (snapshot === undefined) throw new Error("Tool result was not lossless JSON.");
  return snapshot as JsonValue;
}

function reviewResult(review: ProposalReview): JsonValue {
  return json({
    success: review.state === "ready" || review.state === "applied",
    proposal_id: review.proposalId,
    state: review.state,
    diagnostics: review.diagnostics,
    ...(review.error ? { error: review.error } : {}),
    review: publicReview(review),
    instruction: review.state === "applied"
      ? "The owner saved this change. Describe the applied changes using source names; no approval is needed."
      : review.state === "ready"
      ? "The preview is ready. Tell the user to inspect the review card and use its explicit action button."
      : "The owner did not accept this preview. Explain the diagnostics and do not claim any change was made.",
  });
}

function failureResult(error: ProposalError, instruction: string): JsonValue {
  return json({ success: false, error, instruction });
}

function diagnostics(value: Record<string, unknown>): unknown {
  return value.diagnostics ?? value.detail ?? [];
}
function confirmedValues(
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


export function registerDomainTools(
  agentContext: {
    tools: { register(tool: unknown): () => void; get?(name: string): unknown };
    systemPrompt?: { section(value: PromptSection): () => void };
  },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  promptCatalog?: BoundPromptCatalog,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  currentUserRequest?: () => string,
  interactiveForms = false,
  operationContract?: OwnerOperationContract,
  schemaError?: string,
  onDomainToolUse?: () => Promise<void>,
  readOnly = false,
): void {
  let specContract = operationContract;
  let disposeSpecTool: (() => void) | undefined;
  const installSpecTool = (contract: OwnerOperationContract) => {
    disposeSpecTool?.();
    specContract = contract;
    disposeSpecTool = registerSpecProposalTool(agentContext, binding, state, owners, contract, interactiveForms, onReviewPrepared, currentUserRequest, onDomainToolUse);
  };
  const sections = promptCatalog ? catalogPromptSectionsFor(promptCatalog, binding) : promptSectionsFor(binding);
  for (const section of sections) agentContext.systemPrompt?.section(section);
  const interactive = agentContext.tools.get?.("ask_user_question") !== undefined;
  const interaction = structuredQuestionPrompt(interactive);
  if (interaction) agentContext.systemPrompt?.section(interaction);
  agentContext.tools.register(defineTool({
    name: "get_bound_context",
    description: "Read the current authoritative semantic context and revision for this conversation's immutable Spec or Circuit binding. Call this before discussing concrete design facts or preparing a proposal. It never mutates owner data.",
    parameters: { cursor: { type: "string" }, entity_ids: { type: "array", items: { type: "string" } } },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      await onDomainToolUse?.();
      const [context, svg] = await Promise.all([
        binding.domain === "spec" ? owners.contextPage(binding, args, exec.signal) : owners.context(binding, exec.signal),
        binding.domain === "circuit" ? owners.circuitSvg(binding, exec.signal).catch(() => undefined) : Promise.resolve(undefined),
      ]);
      if (binding.domain === "spec" && !readOnly) {
        if (typeof context.owner_document_key === "string" && !binding.ownerDocumentKey) {
          state.pinOwnerDocument(binding.sessionId, context.owner_document_key);
          binding.ownerDocumentKey = context.owner_document_key;
        }
        // Refresh tools between model steps, within the same conversation.
        try {
          const latest = parseOwnerOperationContract(await owners.operationContract(binding, exec.signal));
          if (!specContract || latest.digest !== specContract.digest) installSpecTool(latest);
        } catch {
          // Reading context remains available during a contract outage. The
          // proposal tool verifies the contract again before any submission.
        }
      }
      if (binding.domain === "spec" && (context.document_id !== binding.documentId || typeof context.source_revision_hash !== "string" || !context.source_revision_hash)) {
        throw new Error("Spec context is missing its authoritative document identity or source revision.");
      }
      if (context.document_id !== undefined && context.document_id !== binding.documentId) throw new Error("Context belongs to a different document.");
      if (context.schema_version === "spec2gds.assistant-context-page.v1" && (!Array.isArray(context.records)
        || typeof context.incomplete !== "boolean" || (context.incomplete ? typeof context.next_cursor !== "string" || !context.next_cursor : context.next_cursor !== null))) {
        throw new Error("Malformed context page: records, completeness and follow-up cursor are required. No truncated or spill-file context was accepted.");
      }
      if (context.schema_version === "spec2gds.assistant-context-page.v1" && (context.scope !== binding.scope
        || (binding.scope === "entity" && (!isRecord(context.target) || context.target.entity_id !== binding.entityId || context.target.entity_kind !== binding.entityKind)))) throw new Error("Context does not match the immutable binding.");
      const shaped = context.schema_version === "spec2gds.assistant-context-page.v1"
        ? { text: "Authoritative semantic context follows once. JSON paths and string offsets preserve complete values; follow next_cursor before replacing incomplete fields.", warnings: context.incomplete ? ["Incomplete context; read next_cursor with the same entity selection."] : [] }
        : shapeBoundContext(binding, context, svg);
      const revision = binding.domain === "spec" ? context.source_revision_hash : context.revision;
      if (typeof revision === "string") state.markRevisionStale(binding.sessionId, revision);
      const response = {
        binding: {
          domain: binding.domain,
          document_id: binding.documentId,
          scope: binding.scope,
          entity_kind: binding.entityKind,
          entity_id: binding.entityId,
        },
        model_context: binding.domain === "spec" ? "Use authoritative_context below; stored RTL defines implemented behavior and component descriptions guide implementation." : shaped.text,
        warnings: shaped.warnings,
        authoritative_context: context,
        architecture_reviews: binding.domain === "spec" ? state.listArchitectureReviews().filter(review => {
          try { state.requireArchitecture(binding.sessionId, review.reviewId, typeof revision === "string" ? revision : undefined); return true; }
          catch { return false; }
        }).map(review => ({ review_id: review.reviewId, number: review.reviewNumber || null, title: review.plan.title, status: review.status, plan: review.plan })) : [],
        rules: [
          "Owner-provided IDs and revision values are authoritative.",
          "Stay inside the writable boundary stated by Spec context.",
          "Circuit geometry, routes, labels, and layout are not AI-authored.",
          "Complete-replacement operations must copy every unchanged field.",
          ...(binding.domain === "spec" ? [
            "Copy this source_revision_hash into base_source_revision_hash when preparing a proposal.",
            context.approval_policy === "automatic"
              ? "Valid proposals apply automatically. Use available defaults and record assumptions; ask only for genuinely missing values."
              : "Human approval is required before changes are saved.",
          ] : []),
        ],
      };
      if (binding.domain === "spec" && Buffer.byteLength(JSON.stringify(response)) >= 40 * 1024) throw new Error("Owner context exceeds 40 KiB. A paged context-capable Spec owner is required; no truncated or spill-file result was accepted.");
      return json(response);
    },
  }));

  if (readOnly) return;
  if (!operationContract) {
    const disposeUnavailable = agentContext.tools.register(defineTool({
      name: binding.domain === "spec" ? "prepare_spec_proposal" : "prepare_circuit_proposal",
      description: "Proposal preparation is unavailable because the owning service operation schema could not be loaded.",
      parameters: {},
      output: resultOutput,
      async execute(_args, exec) {
        return failureResult(proposalError(binding, callId(exec), "OWNER_CONTRACT_ERROR", schemaError ?? "Owner operation schema unavailable."),
          "Explain that proposal preparation is unavailable until the owner schema can be loaded.");
      },
    }));
    if (binding.domain === "spec") disposeSpecTool = disposeUnavailable;
    return;
  }
  if (binding.domain === "spec") installSpecTool(operationContract);
  else registerCircuitProposalTool(agentContext, binding, state, owners, operationContract, interactiveForms, onReviewPrepared, onDomainToolUse);
}

function registerSpecProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  contract: OwnerOperationContract,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  currentUserRequest?: () => string,
  onDomainToolUse?: () => Promise<void>,
): () => void {
  return agentContext.tools.register(defineTool({
    name: "prepare_spec_proposal",
    description: SPEC_PROPOSAL_DESCRIPTION,
    parameters: {
      supported: { type: "boolean", required: true },
      base_source_revision_hash: { type: "string", required: true },
      unsupported_reason: { oneOf: [{ type: "string" }, { type: "null" }], required: true },
      title: { type: "string", required: true },
      summary: { type: "string", required: true },
      rationale: { type: "string", required: true },
      assumptions: { type: "array", items: { type: "string" }, required: true },
      operations: { type: "array", items: specFormattingAdmission(contract.tool_schema), required: true },
      required_fields: { type: "array", items: REQUIRED_FIELD_SCHEMA },
      confirmed_input_id: { type: "string" },
      confirmed_values: { type: "json" },
      architecture_review_id: { type: "string" },
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      await onDomainToolUse?.();
      let policy: Awaited<ReturnType<OwnerClients["specPolicy"]>>;
      try { policy = await owners.specPolicy(binding.ownerUrl, exec.signal); }
      catch (error) {
        return failureResult(errorFromException(binding, callId(exec), error), "The owner approval policy could not be read. No change was submitted.");
      }
      try { args = { ...args, operations: snapshotJsonValue(normalizeSpecFormatting(args.operations, binding.documentId)) as typeof args.operations };
        validateProposalEnvelope(args.supported, args.unsupported_reason, args.operations);
        if (args.supported) validateOwnerOperations(contract, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
      }
      if (!args.supported) {
        const providedFields = args.required_fields ?? [];
        const missingFields = policy.approval_policy === "automatic"
          ? providedFields.filter(field => !field.default_value.trim()) : providedFields;
        if (policy.approval_policy === "automatic" && providedFields.length && !missingFields.length) {
          return json({ success: false, suggested_defaults: providedFields,
            instruction: "Use these suggested defaults to author typed operations now, record them in assumptions, and submit without a confirmation card." });
        }
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", missingFields) : null;
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: "A details card is visible. Ask the user to review its defaults and submit it; do not present this as an error.",
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain why the request cannot be represented safely and do not claim a proposal was created.");
      }
      const previous = state.reviewForCall(binding.sessionId, callId(exec));
      if (previous) {
        const replay = buildSpecArtifact(binding, args.base_source_revision_hash, previous.proposalId, args);
        if (artifactDigest(replay) !== previous.artifactDigest) {
          return failureResult(proposalError(binding, previous.proposalId, "INVALID_PROPOSAL", "This tool call ID was reused with changed proposal content."),
            "Use a new tool call for a new proposal. The stored submission was not changed.");
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
        return reviewResult(review);
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
      } catch (error) { return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error)), "Resolve the architecture review or missing component explanation and retry."); }
      if (policy.approval_policy === "review" && interactiveForms && componentCreation && !args.confirmed_input_id && !args.architecture_review_id) {
        const fields = args.required_fields?.length ? args.required_fields : proposedComponentFields(componentCreation as Record<string, unknown>);
        const requiredInput = proposalInputRequest(binding, "Review the component details before the proposal is prepared.", fields);
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: "A details card is visible. Ask the user to review its defaults and submit it; do not claim the proposal is ready yet.",
        });
      }
      const inputError = confirmedValues(state, binding, args.confirmed_input_id, args.confirmed_values);
      if (inputError) return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", inputError),
        "Use the submitted details card values and retry the proposal.");
      const proposalArgs = args;
      let context: Record<string, unknown>;
      try { context = await owners.context(binding, exec.signal); }
      catch (error) {
        const normalized = errorFromException(binding, callId(exec), error);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "The authoritative context could not be read. Do not claim a proposal was created.");
      }
      const revision = context.source_revision_hash;
      if (typeof revision !== "string" || !revision) {
        const normalized = proposalError(binding, callId(exec), "OWNER_CONTRACT_ERROR", "Spec context did not include a source revision.");
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "The owner response was incomplete. Do not claim a proposal was created.");
      }
      if (args.base_source_revision_hash !== revision) {
        return failureResult(proposalError(binding, callId(exec), "STALE_REVISION", {
          diagnostics: ["The specification changed after the context used to author these operations."],
          submitted_source_revision_hash: args.base_source_revision_hash,
          source_revision_hash: revision,
        }, true), "Read get_bound_context again and regenerate the operations. Never relabel old operations with a new revision.");
      }
      const proposalId = id("proposal");
      let artifact: Record<string, unknown>;
      try { artifact = buildSpecArtifact(binding, revision, proposalId, proposalArgs); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
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
        return reviewResult(review);
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

function registerCircuitProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  contract: OwnerOperationContract,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void | Promise<void>,
  onDomainToolUse?: () => Promise<void>,
): void {
  agentContext.tools.register(defineTool({
    name: "prepare_circuit_proposal",
    description: CIRCUIT_PROPOSAL_DESCRIPTION,
    parameters: {
      supported: { type: "boolean", required: true },
      unsupported_reason: { oneOf: [{ type: "string" }, { type: "null" }], required: true },
      title: { type: "string", required: true },
      summary: { type: "string", required: true },
      rationale: { type: "string", required: true },
      assumptions: { type: "array", items: { type: "string" }, required: true },
      operations: { type: "array", items: contract.tool_schema, required: true },
      required_fields: { type: "array", items: REQUIRED_FIELD_SCHEMA },
      confirmed_input_id: { type: "string" },
      confirmed_values: { type: "json" },
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      await onDomainToolUse?.();
      try { validateProposalEnvelope(args.supported, args.unsupported_reason, args.operations);
        if (args.supported) validateOwnerOperations(contract, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
      }
      if (!args.supported) {
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", args.required_fields) : null;
        if (requiredInput) return json({
          success: false,
          required_input: { ...requiredInput, input_id: state.createProposalInput(binding.sessionId, requiredInput.fields) },
          instruction: "A details card is visible. Ask the user to review its defaults and submit it; do not present this as an error.",
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain why the request cannot be represented safely and do not claim a proposal was created.");
      }
      const inputError = confirmedValues(state, binding, args.confirmed_input_id, args.confirmed_values);
      if (inputError) return failureResult(proposalError(binding, callId(exec), "INVALID_PROPOSAL", inputError),
        "Use the submitted details card values and retry the proposal.");
      let snapshot: Record<string, unknown>;
      try { snapshot = await owners.context(binding, exec.signal); }
      catch (error) {
        const normalized = errorFromException(binding, callId(exec), error);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "The authoritative context could not be read. Do not claim a proposal was created.");
      }
      const revision = snapshot.revision;
      if (typeof revision !== "string" || !revision) {
        const normalized = proposalError(binding, callId(exec), "OWNER_CONTRACT_ERROR", "Circuit snapshot did not include a revision.");
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "The owner response was incomplete. Do not claim a proposal was created.");
      }
      const proposalId = id("proposal");
      state.discardOpenReviews(binding.sessionId, "circuit");
      let artifact: Record<string, unknown>;
      try { artifact = buildCircuitArtifact(binding, revision, proposalId, id("request"), args); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
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
        return reviewResult(review);
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

export function findProposal(value: Record<string, unknown>, proposalId: string): Record<string, unknown> | null {
  const proposals = value.proposals;
  if (!Array.isArray(proposals)) return null;
  return proposals.find(item => isRecord(item) && item.proposal_id === proposalId) as Record<string, unknown> | undefined ?? null;
}

export function findSpecChange(value: Record<string, unknown>, proposalId: string): Record<string, unknown> | null {
  const changes = value.assistant_changes;
  if (!Array.isArray(changes)) return null;
  return changes.find(item => isRecord(item) && item.proposal_id === proposalId) as Record<string, unknown> | undefined ?? null;
}
