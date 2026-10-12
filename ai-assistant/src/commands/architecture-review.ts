import { randomUUID } from "node:crypto";
import type { ToolRunContext } from "../tool-registry.js";
export interface InterfacePort { name: string; direction: "in" | "out" | "inout"; range: string | null; description: string; }
export interface InterfaceParameter { name: string; rtl_type: string; value: string; description: string; }
export interface ArchitectureInputs { title: string; components: Array<{ name: string; purpose?: string; description?: string }>; designs: Array<{ name: string; purpose?: string; description?: string }>; interfaces: Array<{ component: string; ports: InterfacePort[]; parameters: InterfaceParameter[]; constant_context: string }>; clocks_resets: string[]; decomposition_rationale: string; assumptions: string[]; open_questions: string[]; concrete_configuration: Record<string, unknown>; }

import { defaultInstructions, type InstructionBundle } from "../instructions.js";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { artifactDigest, ProductState } from "../state.js";
import type { ServiceClients } from "../service-clients.js";
import { isRecord } from "../types.js";
export function prepareArchitectureCommand(
  agent: { id: string },
  state: ProductState, owners: ServiceClients, currentRequest: () => string,
  onPrepared?: (record: Record<string, any>) => Promise<void>,
  instructions: InstructionBundle = defaultInstructions,
  independentCreation = false,
) {
  return {
    async execute(args: ArchitectureInputs, exec: ToolRunContext) {
      try {
        if (!args.title.trim()) throw new Error("title must be nonempty.");
        if (!args.decomposition_rationale.trim()) throw new Error("decomposition_rationale must be nonempty.");
        if (!args.components.length) throw new Error("components must contain at least one named component.");
        if (!args.interfaces.length) throw new Error("interfaces must contain {component, ports:[{name,direction,range,description}]} for each component; use ports:[] for a portless component.");
        if (!Object.keys(args.concrete_configuration).length) throw new Error("concrete_configuration must contain concrete values such as width, reset behavior or overflow behavior.");
        for (const [field, entities] of [["components", args.components], ["designs", args.designs]] as const) {
          if (entities.some(entity => !isRecord(entity) || typeof entity.name !== "string" || !entity.name.trim())
            || new Set(entities.map(entity => isRecord(entity) ? entity.name : null)).size !== entities.length) {
            throw new Error(`${field} entries require distinct nonempty name fields; use {name,purpose}.`);
          }
        }
        const groups = args.interfaces;
        if (groups.some(item => !("component" in item) || !Array.isArray(item.ports)) || groups.length !== args.components.length
          || new Set(groups.map(item => "component" in item ? item.component : null)).size !== groups.length
          || args.components.some(component => !groups.some(item => "component" in item && item.component === component.name))) {
          throw new Error("interfaces must contain exactly one {component,ports} group per named Component.");
        }
        const portLists = groups.flatMap(item => "ports" in item ? [item.ports] : []);
        for (const ports of portLists) {
          if (ports.some(port => !port.name.trim() || !["in", "out", "inout"].includes(port.direction) || !(port.range === null || typeof port.range === "string") || !port.description?.trim() || Object.hasOwn(port, "width"))
            || new Set(ports.map(port => port.name)).size !== ports.length) {
            throw new Error("Interface ports require distinct IDs, directions, exact ranges, and descriptions; width is calculated from bounds.");
          }
        }
        if (groups.some(group => !Array.isArray(group.parameters) || typeof group.constant_context !== "string")) throw new Error("Prepare a new interface review with parameters and constant context.");
        const old = state.architectureForCall(String(agent.id), String(exec.callId));
        if (old && old.digest !== artifactDigest(args)) throw new Error("This review call ID was reused with changed architecture.");
        let record = old;
        if (!record) {
          const binding = independentCreation ? null : state.getBinding(String(agent.id));
          const context = binding ? await owners.context(binding, exec.signal) : null;
          if (binding && binding.domain !== "spec") throw new Error("Architecture review requires a Spec conversation.");
          if (binding && (!context || context.document_id !== binding.documentId || typeof context.source_revision_hash !== "string" || !context.source_revision_hash)) {
            throw new Error("Architecture review requires a fresh service context with the exact document identity and source revision.");
          }
          const originalRequest = currentRequest();
          record = { reviewId: randomUUID(), sessionId: String(agent.id), callId: String(exec.callId), status: "pending",
            plan: args, digest: artifactDigest(args), originalRequest,
            documentId: binding?.documentId ?? null, serviceDocumentKey: context?.owner_document_key ?? binding?.serviceDocumentKey ?? null,
            scope: binding?.scope ?? null, entityId: binding?.entityId ?? null,
            sourceRevision: context?.source_revision_hash ?? null, createdAt: new Date().toISOString() };
          state.storeArchitecture(record);
        }
        if (record.status === "pending") {
          await onPrepared?.(record);
          // The durable card is the decision boundary. Do not let another
          // model step replace it with a generic approval question.
          exec.concludeTurn?.();
        }
        return snapshotJsonValue({ architecture_review: record,
          instruction: instructions.text("result.24") }) as JsonValue;
      } catch (error) { return { creation_error: error instanceof Error ? error.message : String(error),
        instruction: instructions.text("result.25") }; }
    },
  };
}

