import { randomUUID } from "node:crypto";
import type { PromptSection } from "@deepseek-ai/dsh-system-prompt";
import { defineTool, type ToolRunContext } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import type { OwnerClients } from "./owner-clients.js";
import { catalogPromptSectionsFor, promptSectionsFor, shapeBoundContext, type BoundPromptCatalog } from "./domain-context.js";
import { CIRCUIT_OPERATION_SCHEMA, SPEC_OPERATION_SCHEMA, validateProposalSemantics } from "./operation-schemas.js";
import { buildCircuitArtifact, buildSpecArtifact, reviewStateForPreview } from "./proposal-pipeline.js";
import {
  errorFromException,
  errorFromOwnerResult,
  logProposalFailure,
  proposalError,
  publicReview,
} from "./proposal-presentation.js";
import type { ProductState } from "./state.js";
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

function looksLikeMissingInformation(reason: string): boolean {
  return /\b(?:missing|need(?:s|ed)?|required|unspecified|unknown|lacks?|not (?:provided|specified|available)|does not provide|please provide)\b/i.test(reason);
}

function componentDefaults(text: string, proposedName?: string): readonly ProposalInputField[] {
  const kind = text.match(/\b(xnor|nand|nor|xor|and|or|not)[\s-]*gate\b/i)?.[1]?.toLowerCase()
    ?? (/\binverter\b/i.test(text) ? "not" : /\bbuffer\b/i.test(text) ? "buffer" : "component");
  const gates: Record<string, { name: string; inputs: string; behavior: string }> = {
    xnor: { name: "XnorGate", inputs: "A, B", behavior: "Y = ~(A ^ B)" },
    nand: { name: "NandGate", inputs: "A, B", behavior: "Y = ~(A & B)" },
    nor: { name: "NorGate", inputs: "A, B", behavior: "Y = ~(A | B)" },
    xor: { name: "XorGate", inputs: "A, B", behavior: "Y = A ^ B" },
    and: { name: "AndGate", inputs: "A, B", behavior: "Y = A & B" },
    or: { name: "OrGate", inputs: "A, B", behavior: "Y = A | B" },
    not: { name: "NotGate", inputs: "A", behavior: "Y = ~A" },
    buffer: { name: "Buffer", inputs: "A", behavior: "Y = A" },
    component: { name: "NewComponent", inputs: "A", behavior: "Y = A" },
  };
  const gate = (gates[kind] ?? gates.component)!;
  const requestedName = text.match(/\b(?:named|called)\s+([A-Za-z_][\w.-]*)\b/i)?.[1]
    ?? text.match(/\bcomponent name\s*(?:is|=|:)\s*([A-Za-z_][\w.-]*)\b/i)?.[1];
  const genericNames = /^(?:(?:and|or|xor|xnor|nand|nor|not|buffer)(?:gate)?|gate|component|newcomponent)$/i;
  const name = requestedName ?? (proposedName?.trim() && !genericNames.test(proposedName.trim()) ? proposedName.trim() : gate.name);
  const width = text.match(/\b(\d+)\s*(?:-|\s)?bit\b/i)?.[1] ?? "1";
  return [
    { name: "component_name", label: "Component name", description: "Unique name for the new component.", default_value: name },
    { name: "input_ports", label: "Input ports", description: "Comma-separated input port names.", default_value: gate.inputs },
    { name: "output_ports", label: "Output ports", description: "Comma-separated output port names.", default_value: "Y" },
    { name: "port_width", label: "Port width", description: "Width in bits for the listed ports.", default_value: width },
    { name: "behavior", label: "Behavior", description: "Intended logical behavior for the component.", default_value: gate.behavior },
  ];
}

/** Build a browser-editable request only for missing user input, never for a genuinely unsupported operation. */
export function proposalInputRequest(
  binding: SessionBinding,
  reason: string,
  provided: readonly ProposalInputField[] | undefined,
  context = "",
  proposedName?: string,
): ProposalInputRequest | null {
  const normalized: readonly ProposalInputField[] = (provided ?? []).filter(field => field.name.trim() && field.label.trim());
  const component = binding.domain === "spec" && binding.scope === "document" && /component|gate/i.test(`${reason} ${context}`);
  if (!normalized.length && !looksLikeMissingInformation(reason) && !component) return null;
  let fields: readonly ProposalInputField[] = normalized;
  if (component) {
    fields = componentDefaults(`${context} ${reason}`, proposedName);
  }
  if (!fields.length) {
    fields = [{
      name: "required_details",
      label: "Required details",
      description: "Add the information needed to complete the pending proposal.",
      default_value: context.trim() || "Use sensible implementation defaults.",
    }];
  }
  return {
    title: "Complete the proposal details",
    description: reason.trim() || "More information is required before the proposal can be prepared.",
    fields,
    submit_label: "Continue proposal",
  };
}

const SPEC_PROPOSAL_DESCRIPTION = `Prepare and owner-preview a typed Spec proposal after reading get_bound_context. This never applies it.
Document scope permits only create_entity. A component may atomically include ports and module-body systemverilog: {type:"create_entity",kind:"component",name,instances:[],ports:[complete component port objects],systemverilog:"assign ...;"}; a design may include initial instances {name,component_vlnv} copied from available references.
Entity scope supports: set_entity_metadata; upsert/delete_parameter; upsert/delete_component_port; upsert_bus_interface; upsert_channel; upsert/delete/reorder_instance; upsert/delete/reorder_connection; set/clear_internal_design; update_bus_definition; set_abstraction_bus_type; upsert_abstraction_port; narrative block operations; and upsert/delete_entity_section.
Use the exact public field names and existing IDs from context. A port, interface, instance, connection, bus-definition properties object, or SystemVerilog section update is a complete replacement: copy every unchanged field. Ad-hoc connections use port_endpoints and external_ports; interface connections use interface_endpoints and hierarchy_interfaces. Component ports use the wire, transactional, or structured editor profile described by owner context. SystemVerilog content is module-body text only. clear_fields is allowed only for metadata and bus-definition nullable fields. Narrative options are [{key,value}]. Stay inside the writable boundary and do not invent references.`;

const CIRCUIT_PROPOSAL_DESCRIPTION = `Prepare and owner-preview a typed Circuit operation batch after reading get_bound_context. This never commits or submits it.
Intent mapping: add a definition -> add_component; place a definition -> add_instance; add a pin -> update_component with the complete component; add a top-level port -> add_boundary_terminal; connect a new net -> create_net; extend an existing net -> connect_endpoint.
Supported operations are add/update/remove_component, add/update/remove_instance, add/update/remove_boundary_terminal, create/update/delete_net, and connect/disconnect_endpoint. Complete replacements must copy every unchanged field. New normal components use {id,label,origin:"local",editable:true,terminals,parameters,appearance:{renderer_key:"default",properties:[{name,value}]}}. Instances use {id,label,component_id,parameter_values:[{name,value}]}. Endpoints are exactly {kind:"instance",instance_id,terminal_id,slice:null} or {kind:"boundary",terminal_id,slice:null}; use {lsb,width} only for an explicit numeric slice. Reuse exact existing IDs, order dependent operations, prefer cascade:false, and never author geometry, routes, labels, or layout.`;

export function structuredQuestionPrompt(enabled: boolean): PromptSection | null {
  if (!enabled) return null;
  return {
    name: "spec2gds:interactive-clarification",
    order: 250,
    text: `INTERACTIVE CLARIFICATION
After reading bound context, if a concrete proposal needs user-supplied values, call its prepare_*_proposal tool with supported=false, an empty operations list, and every missing value in required_fields. Supply a sensible default_value for every field. The client will show one editable details card and continue the proposal from its submission. Do not list missing proposal fields in an ordinary assistant response and end the turn. For a non-proposal question or choice, you MUST call ask_user_question. Ask only for information that cannot be derived from bound context, and do not ask about optional data that can safely retain its current or default value. When a goal or orchestrated workflow instead needs to stop durably for a consequential decision, use its workflow input request capability.`,
  };
}

const CONFIRMED_COMPONENT_PREFIX = "Continue the pending design proposal using these user-confirmed values:";

export function applyConfirmedComponentDetails<T>(
  operations: T[],
  request: string,
): T[] {
  if (!request.startsWith(CONFIRMED_COMPONENT_PREFIX)) return operations;
  const values = new Map<string, string>();
  for (const line of request.slice(CONFIRMED_COMPONENT_PREFIX.length).split("\n")) {
    const match = /^-\s*([^:]+):\s*(.*)$/.exec(line.trim());
    if (match) values.set(match[1]!.trim().toLowerCase(), match[2]!.trim());
  }
  const componentName = values.get("component name") ?? "";
  const inputs = splitPortNames(values.get("input ports") ?? "");
  const outputs = splitPortNames(values.get("output ports") ?? "");
  const widthText = values.get("port width") ?? "";
  const behavior = values.get("behavior") ?? "";
  if (!componentName || !inputs.length || !outputs.length || !behavior) {
    throw new Error("Confirmed component details require a name, input ports, output ports, and behavior.");
  }
  const width = Number(widthText);
  if (!Number.isSafeInteger(width) || width < 1) throw new Error("Port width must be a positive integer.");
  const names = [...inputs, ...outputs];
  if (new Set(names).size !== names.length) throw new Error("Input and output port names must be unique.");
  const range = width === 1 ? null : `${width - 1}:0`;
  const ports = [
    ...inputs.map(name => ({ name, family: "wire", display_name: null, description: null, direction: "in", range })),
    ...outputs.map(name => ({ name, family: "wire", display_name: null, description: null, direction: "out", range })),
  ];
  const systemverilog = /^(?:assign\b)/i.test(behavior)
    ? `${behavior.replace(/;+\s*$/, "")};`
    : `assign ${behavior.replace(/;+\s*$/, "")};`;
  let enriched = false;
  const result = operations.map(operation => {
    if (enriched || !isRecord(operation) || operation.type !== "create_entity" || operation.kind !== "component") return operation;
    enriched = true;
    return { ...operation, name: componentName, ports, systemverilog };
  });
  if (!enriched) throw new Error("Confirmed component details require a component create operation.");
  return result as T[];
}

function splitPortNames(value: string): string[] {
  const names = value.split(",").map(name => name.trim()).filter(Boolean);
  if (names.some(name => !/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(name))) {
    throw new Error("Port names must be comma-separated XML-compatible identifiers.");
  }
  return names;
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
    success: review.state === "ready",
    proposal_id: review.proposalId,
    state: review.state,
    diagnostics: review.diagnostics,
    ...(review.error ? { error: review.error } : {}),
    review: publicReview(review),
    instruction: review.state === "ready"
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

export function registerDomainTools(
  agentContext: {
    tools: { register(tool: unknown): () => void; get?(name: string): unknown };
    systemPrompt?: { section(value: PromptSection): () => void };
  },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  promptCatalog?: BoundPromptCatalog,
  onReviewPrepared?: (review: ProposalReview) => void,
  currentUserRequest?: () => string,
  interactiveForms = false,
): void {
  const sections = promptCatalog ? catalogPromptSectionsFor(promptCatalog, binding) : promptSectionsFor(binding);
  for (const section of sections) agentContext.systemPrompt?.section(section);
  const interactive = agentContext.tools.get?.("ask_user_question") !== undefined;
  const interaction = structuredQuestionPrompt(interactive);
  if (interaction) agentContext.systemPrompt?.section(interaction);
  agentContext.tools.register(defineTool({
    name: "get_bound_context",
    description: "Read the current authoritative semantic context and revision for this conversation's immutable Spec or Circuit binding. Call this before discussing concrete design facts or preparing a proposal. It never mutates owner data.",
    parameters: {},
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(_args, exec) {
      const [context, svg] = await Promise.all([
        owners.context(binding, exec.signal),
        binding.domain === "circuit" ? owners.circuitSvg(binding, exec.signal).catch(() => undefined) : Promise.resolve(undefined),
      ]);
      const shaped = shapeBoundContext(binding, context, svg);
      const revision = binding.domain === "spec" ? context.source_revision_hash : context.revision;
      if (typeof revision === "string") state.markRevisionStale(binding.sessionId, revision);
      return json({
        binding: {
          domain: binding.domain,
          document_id: binding.documentId,
          scope: binding.scope,
          entity_kind: binding.entityKind,
          entity_id: binding.entityId,
        },
        model_context: shaped.text,
        warnings: shaped.warnings,
        authoritative_context: context,
        rules: [
          "Owner-provided IDs and revision values are authoritative.",
          "Stay inside the writable boundary stated by Spec context.",
          "Circuit geometry, routes, labels, and layout are not AI-authored.",
          "Complete-replacement operations must copy every unchanged field.",
        ],
      });
    },
  }));

  if (binding.domain === "spec") registerSpecProposalTool(agentContext, binding, state, owners, interactiveForms, onReviewPrepared, currentUserRequest);
  else registerCircuitProposalTool(agentContext, binding, state, owners, interactiveForms, onReviewPrepared);
}

function registerSpecProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void,
  currentUserRequest?: () => string,
): void {
  agentContext.tools.register(defineTool({
    name: "prepare_spec_proposal",
    description: SPEC_PROPOSAL_DESCRIPTION,
    parameters: {
      supported: { type: "boolean", required: true },
      unsupported_reason: { oneOf: [{ type: "string" }, { type: "null" }], required: true },
      title: { type: "string", required: true },
      summary: { type: "string", required: true },
      rationale: { type: "string", required: true },
      assumptions: { type: "array", items: { type: "string" }, required: true },
      operations: { type: "array", items: SPEC_OPERATION_SCHEMA, required: true },
      required_fields: { type: "array", items: REQUIRED_FIELD_SCHEMA },
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      try { validateProposalSemantics("spec", args.supported, args.unsupported_reason, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
      }
      if (!args.supported) {
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", args.required_fields,
          `${currentUserRequest?.() ?? ""} ${args.title} ${args.summary} ${args.rationale} ${args.assumptions.join(" ")}`) : null;
        if (requiredInput) return json({
          success: false,
          required_input: requiredInput,
          instruction: "A details card is visible. Ask the user to review its defaults and submit it; do not present this as an error.",
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain why the request cannot be represented safely and do not claim a proposal was created.");
      }
      const componentCreation = binding.scope === "document"
        ? args.operations.find(operation => isRecord(operation) && operation.type === "create_entity" && operation.kind === "component")
        : undefined;
      const request = currentUserRequest?.() ?? "";
      const confirmed = request.startsWith(CONFIRMED_COMPONENT_PREFIX);
      if (interactiveForms && componentCreation && !confirmed) {
        const proposedName = isRecord(componentCreation) && typeof componentCreation.name === "string" ? componentCreation.name : undefined;
        const requiredInput = proposalInputRequest(binding, "Review the component details before the proposal is prepared.", [],
          `${request} ${args.title} ${args.summary} ${args.rationale} ${args.assumptions.join(" ")}`, proposedName);
        if (requiredInput) return json({
          success: false,
          required_input: requiredInput,
          instruction: "A details card is visible. Ask the user to review its request-derived defaults and submit it; do not claim the proposal is ready yet.",
        });
      }
      let proposalArgs = args;
      if (confirmed && componentCreation) {
        try {
          proposalArgs = { ...args, operations: applyConfirmedComponentDetails(args.operations, request) };
          validateProposalSemantics("spec", proposalArgs.supported, proposalArgs.unsupported_reason, proposalArgs.operations);
        } catch (error) {
          const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
          logProposalFailure(binding, normalized);
          return failureResult(normalized, "Explain the invalid confirmed value and do not claim a proposal was created.");
        }
      }
      if (binding.scope === "document" && proposalArgs.operations.some(operation => !isRecord(operation) || operation.type !== "create_entity")) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", "Document-scoped Spec conversations may only propose create_entity operations.");
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
      }
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
      const proposalId = id("proposal");
      state.discardOpenReviews(binding.sessionId, "spec");
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
        const preview = await owners.previewSpec(binding, artifact, exec.signal);
        const next = reviewStateForPreview("spec", preview.status);
        const normalized = next === "ready" ? null : errorFromOwnerResult(binding, proposalId, preview);
        if (normalized) logProposalFailure(binding, normalized, proposalId);
        const review = state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview, diagnostics: diagnostics(preview), error: normalized,
        });
        if (review.state === "ready") onReviewPrepared?.(review);
        return reviewResult(review);
      } catch (error) {
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

function registerCircuitProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
  interactiveForms: boolean,
  onReviewPrepared?: (review: ProposalReview) => void,
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
      operations: { type: "array", items: CIRCUIT_OPERATION_SCHEMA, required: true },
      required_fields: { type: "array", items: REQUIRED_FIELD_SCHEMA },
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      try { validateProposalSemantics("circuit", args.supported, args.unsupported_reason, args.operations); }
      catch (error) {
        const normalized = proposalError(binding, callId(exec), "INVALID_PROPOSAL", error instanceof Error ? error.message : String(error));
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain the validation failure and do not claim a proposal was created.");
      }
      if (!args.supported) {
        const requiredInput = interactiveForms ? proposalInputRequest(binding, args.unsupported_reason ?? "Required proposal details were not provided.", args.required_fields,
          `${args.title} ${args.summary} ${args.rationale} ${args.assumptions.join(" ")}`) : null;
        if (requiredInput) return json({
          success: false,
          required_input: requiredInput,
          instruction: "A details card is visible. Ask the user to review its defaults and submit it; do not present this as an error.",
        });
        const normalized = proposalError(binding, callId(exec), "UNSUPPORTED_REQUEST", args.unsupported_reason);
        logProposalFailure(binding, normalized);
        return failureResult(normalized, "Explain why the request cannot be represented safely and do not claim a proposal was created.");
      }
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
        const preview = await owners.previewCircuit(binding, batch, exec.signal);
        const next = reviewStateForPreview("circuit", preview.status);
        const normalized = next === "ready" ? null : errorFromOwnerResult(binding, proposalId, preview);
        if (normalized) logProposalFailure(binding, normalized, proposalId);
        const review = state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview: { ...preview, base_document: snapshot.document }, diagnostics: diagnostics(preview), error: normalized,
        });
        if (review.state === "ready") onReviewPrepared?.(review);
        return reviewResult(review);
      } catch (error) {
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
