/** Model capabilities for bound service context, typed proposals and clarification.
 * Tool schemas admit structural arguments; fresh authored revisions and service
 * preview enforce meaning. Standing specialists stay read-only; primary tools
 * cannot bypass immutable binding, review claims or native execution permission. */

import { registeredTool, nativeTool, type ToolRunContext } from "../tool-registry.js";
import type { ToolArguments } from "../tool-arguments.js";
import { type InstructionBundle } from "../instructions.js";
import { type ServiceClients } from "../service-clients.js";
import { shapeBoundContext } from "../domain-context.js";
import { type ProductState } from "../state.js";
import type { SessionBinding } from "../types.js";
import { isRecord } from "../types.js";
import { json } from "./shared.js";
export function registerContextTool(
  agentContext: { tools: { register(tool: unknown): () => void } }, binding: SessionBinding,
  state: ProductState, owners: ServiceClients, instructions: InstructionBundle,
  readOnly: boolean, onDomainToolUse?: () => Promise<void>,
): void {
  agentContext.tools.register(registeredTool({
    ...nativeTool("get_bound_context", instructions),
    async execute(args: ToolArguments["get_bound_context"], exec: ToolRunContext) {
      await onDomainToolUse?.();
      const [context, svg] = await Promise.all([
        binding.domain === "spec" ? owners.contextPage(binding, args, exec.signal) : owners.context(binding, exec.signal),
        binding.domain === "circuit" ? owners.circuitSvg(binding, exec.signal).catch(() => undefined) : Promise.resolve(undefined),
      ]);
      if (binding.domain === "spec" && !readOnly) {
        if (typeof context.owner_document_key === "string" && !binding.serviceDocumentKey) {
          state.pinServiceDocument(binding.sessionId, context.owner_document_key);
          binding.serviceDocumentKey = context.owner_document_key;
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
        ? { text: instructions.text("context.34"), warnings: context.incomplete ? [instructions.text("context.35")] : [] }
        : shapeBoundContext(binding, context, svg, instructions);
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
        model_context: binding.domain === "spec" ? instructions.text("context.36") : shaped.text,
        warnings: shaped.warnings,
        authoritative_context: context,
        architecture_reviews: binding.domain === "spec" ? state.listArchitectureReviews().filter(review => {
          try { if (!review.flow_execution_id) return false; state.requireArchitecture(binding.sessionId, review.reviewId, typeof revision === "string" ? revision : undefined); return true; }
          catch { return false; }
        }).map(review => ({ review_id: review.reviewId, number: review.reviewNumber || null, title: review.plan.title, status: review.status, plan: review.plan })) : [],
        rules: [
          instructions.text("context.37"),
          instructions.text("context.38"),
          instructions.text("context.39"),
          instructions.text("context.40"),
          ...(binding.domain === "spec" ? [
            instructions.text("context.41"),
            context.approval_policy === "automatic"
              ? instructions.text("context.42")
              : instructions.text("context.43"),
          ] : []),
        ],
      };
      if (binding.domain === "spec" && Buffer.byteLength(JSON.stringify(response)) >= 40 * 1024) throw new Error("Owner context exceeds 40 KiB. A paged context-capable Spec service is required; no truncated or spill-file result was accepted.");
      return json(response);
    },
  }));

}
