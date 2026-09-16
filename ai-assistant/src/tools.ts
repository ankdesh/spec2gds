import { randomUUID } from "node:crypto";
import { defineTool, type ToolRunContext } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import type { OwnerClients } from "./owner-clients.js";
import { OwnerError } from "./owner-clients.js";
import { normalizeCircuitOperations, normalizeSpecOperations } from "./normalize.js";
import { instructionsFor, shapeBoundContext } from "./domain-context.js";
import { CIRCUIT_OPERATION_SCHEMA, SPEC_OPERATION_SCHEMA, validateProposalSemantics } from "./operation-schemas.js";
import type { ProductState } from "./state.js";
import type { ProposalReview, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

const resultOutput = {
  schema: { type: "json" } as const,
  render: (_args: unknown, value: unknown) => [{ type: "text" as const, text: JSON.stringify(value) }],
};

const SPEC_PROPOSAL_DESCRIPTION = `Prepare and owner-preview a typed Spec proposal after reading get_bound_context. This never applies it.
Document scope permits only create_entity. A component uses {type:"create_entity",kind:"component",name,instances:[]}; a design may include initial instances {name,component_vlnv} copied from available references.
Entity scope supports: set_entity_metadata; upsert/delete_parameter; upsert/delete_component_port; upsert_bus_interface; upsert_channel; upsert/delete/reorder_instance; upsert/delete/reorder_connection; set/clear_internal_design; update_bus_definition; set_abstraction_bus_type; upsert_abstraction_port; narrative block operations; and upsert/delete_entity_section.
Use the exact public field names and existing IDs from context. A port, interface, instance, connection, bus-definition properties object, or SystemVerilog section update is a complete replacement: copy every unchanged field. Ad-hoc connections use port_endpoints and external_ports; interface connections use interface_endpoints and hierarchy_interfaces. Component ports use the wire, transactional, or structured editor profile described by owner context. SystemVerilog content is module-body text only. clear_fields is allowed only for metadata and bus-definition nullable fields. Narrative options are [{key,value}]. Stay inside the writable boundary and do not invent references.`;

const CIRCUIT_PROPOSAL_DESCRIPTION = `Prepare and owner-preview a typed Circuit operation batch after reading get_bound_context. This never commits or submits it.
Intent mapping: add a definition -> add_component; place a definition -> add_instance; add a pin -> update_component with the complete component; add a top-level port -> add_boundary_terminal; connect a new net -> create_net; extend an existing net -> connect_endpoint.
Supported operations are add/update/remove_component, add/update/remove_instance, add/update/remove_boundary_terminal, create/update/delete_net, and connect/disconnect_endpoint. Complete replacements must copy every unchanged field. New normal components use {id,label,origin:"local",editable:true,terminals,parameters,appearance:{renderer_key:"default",properties:[{name,value}]}}. Instances use {id,label,component_id,parameter_values:[{name,value}]}. Endpoints are exactly {kind:"instance",instance_id,terminal_id,slice:null} or {kind:"boundary",terminal_id,slice:null}; use {lsb,width} only for an explicit numeric slice. Reuse exact existing IDs, order dependent operations, prefer cascade:false, and never author geometry, routes, labels, or layout.`;

function callId(exec: ToolRunContext): string { return String(exec.callId); }
function id(prefix: string): string { return `${prefix}_${randomUUID().replaceAll("-", "")}`; }

function json(value: unknown): JsonValue {
  const snapshot = snapshotJsonValue(value);
  if (snapshot === undefined) throw new Error("Tool result was not lossless JSON.");
  return snapshot as JsonValue;
}

function reviewResult(review: ProposalReview): JsonValue {
  return json({
    proposal_id: review.proposalId,
    state: review.state,
    diagnostics: review.diagnostics,
    instruction: review.state === "ready"
      ? "The preview is ready. Tell the user to inspect the review card and use its explicit action button."
      : "The owner did not accept this preview. Explain the diagnostics and do not claim any change was made.",
  });
}

function diagnostics(value: Record<string, unknown>): unknown {
  return value.diagnostics ?? value.detail ?? [];
}

export function registerDomainTools(
  agentContext: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
): void {
  agentContext.systemPrompt?.section({
    name: `spec2gds:${binding.domain}-editing-contract`,
    order: 150,
    complete: true,
    text: instructionsFor(binding),
  });
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

  if (binding.domain === "spec") registerSpecProposalTool(agentContext, binding, state, owners);
  else registerCircuitProposalTool(agentContext, binding, state, owners);
}

function registerSpecProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
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
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      validateProposalSemantics("spec", args.supported, args.unsupported_reason, args.operations);
      if (!args.supported) return json({ supported: false, unsupported_reason: args.unsupported_reason, instruction: "Explain why the request cannot be represented safely and do not claim a proposal was created." });
      if (binding.scope === "document" && args.operations.some(operation => !isRecord(operation) || operation.type !== "create_entity")) {
        throw new Error("Document-scoped Spec conversations may only propose create_entity operations.");
      }
      const context = await owners.context(binding, exec.signal);
      const revision = context.source_revision_hash;
      if (typeof revision !== "string" || !revision) throw new Error("Spec context did not include a source revision.");
      const proposalId = id("proposal");
      state.discardOpenReviews(binding.sessionId, "spec");
      const artifact: Record<string, unknown> = {
        schema_version: "1.0", kind: "spec_change_proposal", proposal_id: proposalId,
        document_id: binding.documentId, scope: binding.scope,
        target: binding.scope === "entity" ? {
          document_id: binding.documentId, entity_kind: binding.entityKind, entity_id: binding.entityId,
        } : null,
        base_source_revision_hash: revision,
        title: args.title, summary: args.summary, rationale: args.rationale,
        assumptions: args.assumptions, operations: normalizeSpecOperations(args.operations),
      };
      state.createReview({
        proposalId, sessionId: binding.sessionId, callId: callId(exec), domain: "spec",
        state: "previewing", baseRevision: revision, artifact, preview: null, diagnostics: [], ownerResult: null,
      });
      try {
        const preview = await owners.previewSpec(binding, artifact, exec.signal);
        const status = preview.status;
        const next = status === "valid" ? "ready" : status === "stale" ? "stale" : "rejected";
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview, diagnostics: diagnostics(preview),
        }));
      } catch (error) {
        const detail = error instanceof OwnerError ? error.detail : error instanceof Error ? error.message : String(error);
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, ["previewing"],
          error instanceof OwnerError && error.status === 409 ? "stale" : "rejected", { diagnostics: detail }));
      }
    },
  }));
}

function registerCircuitProposalTool(
  agentContext: { tools: { register(tool: unknown): () => void } },
  binding: SessionBinding,
  state: ProductState,
  owners: OwnerClients,
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
    },
    output: resultOutput,
    timeoutMs: 35_000,
    async execute(args, exec) {
      validateProposalSemantics("circuit", args.supported, args.unsupported_reason, args.operations);
      if (!args.supported) return json({ supported: false, unsupported_reason: args.unsupported_reason, instruction: "Explain why the request cannot be represented safely and do not claim a proposal was created." });
      const snapshot = await owners.context(binding, exec.signal);
      const revision = snapshot.revision;
      if (typeof revision !== "string" || !revision) throw new Error("Circuit snapshot did not include a revision.");
      const proposalId = id("proposal");
      state.discardOpenReviews(binding.sessionId, "circuit");
      const batch = {
        request_id: id("request"), expected_revision: revision,
        operations: normalizeCircuitOperations(args.operations),
      };
      const artifact: Record<string, unknown> = {
        schema_version: "1", kind: "circuit_change_proposal", proposal_id: proposalId,
        document_id: binding.documentId, base_revision: revision,
        title: args.title, summary: args.summary, rationale: args.rationale,
        assumptions: args.assumptions, batch,
      };
      state.createReview({
        proposalId, sessionId: binding.sessionId, callId: callId(exec), domain: "circuit",
        state: "previewing", baseRevision: revision, artifact, preview: null, diagnostics: [], ownerResult: null,
      });
      try {
        const preview = await owners.previewCircuit(binding, batch, exec.signal);
        const status = preview.status;
        const next = status === "accepted" ? "ready" : status === "conflict" || status === "revision_conflict" ? "stale" : "rejected";
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, ["previewing"], next, {
          preview: { ...preview, base_document: snapshot.document }, diagnostics: diagnostics(preview),
        }));
      } catch (error) {
        const detail = error instanceof OwnerError ? error.detail : error instanceof Error ? error.message : String(error);
        return reviewResult(state.transitionReview(binding.sessionId, proposalId, ["previewing"],
          error instanceof OwnerError && error.status === 409 ? "stale" : "rejected", { diagnostics: detail }));
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
