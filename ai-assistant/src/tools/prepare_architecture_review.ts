import { randomUUID } from "node:crypto";
import { registeredTool, nativeTool, type ToolRunContext } from "../tool-registry.js";
import type { ToolArguments } from "../tool-arguments.js";
import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { artifactDigest, ProductState } from "../state.js";
import type { ServiceClients } from "../service-clients.js";
import { decisionReview } from "../architecture-decision.js";
import { isRecord } from "../types.js";
export function registerArchitectureTool(
  agent: { id: string; ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } } },
  state: ProductState, owners: ServiceClients, currentRequest: () => string,
  onPrepared?: (record: Record<string, any>) => Promise<void>,
  instructions: InstructionBundle = defaultInstructions,
): void {
  agent.ctx.systemPrompt?.section({ name: "spec2gds:architecture", order: 180, text: instructions.text("architecture") });
  agent.ctx.tools.register(registeredTool({
    ...nativeTool("prepare_architecture_review", instructions),
    async execute(args: ToolArguments["prepare_architecture_review"], exec: ToolRunContext) {
      try {
        if (!args.title.trim()) throw new Error("title must be nonempty.");
        if (!args.decomposition_rationale.trim()) throw new Error("decomposition_rationale must be nonempty.");
        if (!args.components.length) throw new Error("components must contain at least one named component.");
        if (!args.interfaces.length) throw new Error("interfaces must contain {component, ports:[{name,direction,width}]} for each component; use ports:[] for a portless component.");
        if (!Object.keys(args.concrete_configuration).length) throw new Error("concrete_configuration must contain concrete values such as width, reset behavior or overflow behavior.");
        for (const [field, entities] of [["components", args.components], ["designs", args.designs]] as const) {
          if (entities.some(entity => !isRecord(entity) || typeof entity.name !== "string" || !entity.name.trim())
            || new Set(entities.map(entity => isRecord(entity) ? entity.name : null)).size !== entities.length) {
            throw new Error(`${field} entries require distinct nonempty name fields; use {name,purpose}.`);
          }
        }
        const flat = args.interfaces.every(item => "name" in item);
        if (flat && args.components.length !== 1) throw new Error("Multiple components require grouped interfaces: {component,ports} for each component.");
        if (!flat) {
          const groups = args.interfaces.filter(item => "component" in item);
          if (groups.length !== args.interfaces.length || groups.length !== args.components.length
            || new Set(groups.map(item => item.component)).size !== groups.length
            || args.components.some(component => !groups.some(item => item.component === component.name))) {
            throw new Error("interfaces must contain exactly one {component,ports} group per named component.");
          }
        }
        const portLists = flat ? [args.interfaces.filter(item => "name" in item)]
          : args.interfaces.flatMap(item => "ports" in item ? [item.ports] : []);
        for (const ports of portLists) {
          if (ports.some(port => !port.name.trim() || port.width < 1)
            || new Set(ports.map(port => port.name)).size !== ports.length) {
            throw new Error("Interface ports require distinct nonempty names and positive integer widths.");
          }
        }
        const old = state.architectureForCall(String(agent.id), String(exec.callId));
        if (old && old.digest !== artifactDigest(args)) throw new Error("This review call ID was reused with changed architecture.");
        let record = old;
        if (!record) {
          const binding = state.getBinding(String(agent.id));
          const context = binding ? await owners.context(binding, exec.signal) : null;
          if (binding && binding.domain !== "spec") throw new Error("Architecture review requires a Spec conversation.");
          if (binding && (!context || context.document_id !== binding.documentId || typeof context.source_revision_hash !== "string" || !context.source_revision_hash)) {
            throw new Error("Architecture review requires a fresh service context with the exact document identity and source revision.");
          }
          let originalRequest = currentRequest();
          const previous = decisionReview(state, String(agent.id), originalRequest);
          if (previous) originalRequest = previous.originalRequest;
          record = { reviewId: randomUUID(), sessionId: String(agent.id), callId: String(exec.callId), status: "pending",
            plan: args, digest: artifactDigest(args), originalRequest,
            documentId: binding?.documentId ?? null, serviceDocumentKey: context?.owner_document_key ?? binding?.serviceDocumentKey ?? null,
            scope: binding?.scope ?? null, entityId: binding?.entityId ?? null,
            sourceRevision: context?.source_revision_hash ?? null, createdAt: new Date().toISOString() };
          state.storeArchitecture(record);
        }
        if (record.status === "pending") await onPrepared?.(record);
        return snapshotJsonValue({ architecture_review: record,
          instruction: instructions.text("result.24") }) as JsonValue;
      } catch (error) { return { creation_error: error instanceof Error ? error.message : String(error),
        instruction: instructions.text("result.25") }; }
    },
  }));
}
