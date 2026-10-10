/** Authoring data from a saved leaf architecture. This does not generate behavior or apply edits. */
import type { SessionBinding } from "./types.js";

export function initialContentTemplate(binding: SessionBinding, review: Record<string, any>, revision: string): Record<string, any> | null {
  const plan = review.plan;
  if (binding.domain !== "spec" || binding.scope !== "document" || review.status !== "approved"
    || !binding.serviceDocumentKey || review.destinationServiceDocumentKey !== binding.serviceDocumentKey
    || review.destinationDocumentId !== binding.documentId || review.destinationSessionId !== binding.sessionId
    || review.destinationSourceRevision !== revision || !Array.isArray(plan?.components) || plan.components.length !== 1
    || !Array.isArray(plan.designs) || plan.designs.length || !Array.isArray(plan.interfaces)) return null;
  const component = plan.components[0];
  const group = plan.interfaces.find((item: any) => item.component === component.name);
  const ports = group?.ports ?? plan.interfaces;
  const template = {
    supported: true, unsupported_reason: null, base_source_revision_hash: revision,
    architecture_review_id: review.reviewId, title: plan.title, summary: "Implement the approved leaf Component.",
    rationale: "Populate the already-created Spec according to the saved architecture decision.", assumptions: plan.assumptions,
    operations: [
      { operation_id: "create_approved_component", type: "create_entity", kind: "component", name: component.name,
        entity_id: "approved_component", instances: [], ports: ports.map((port: any) => ({
          name: port.name, family: "wire", direction: port.direction,
          ...(port.width > 1 ? { range: `${port.width - 1}:0` } : {}),
        })), systemverilog: "" },
      { operation_id: "explain_approved_component", type: "set_entity_metadata",
        entity: { document_id: binding.documentId, entity_kind: "component", entity_id: "approved_component" }, description: "" },
    ],
  };
  // Keep the context response bounded. Large architectures retain the ordinary paged authoring path.
  return Buffer.byteLength(JSON.stringify(template)) < 8192 ? template : null;
}
