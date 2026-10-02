/** Durable architecture approval is separate from the owner's content policy. */
import { randomUUID } from "node:crypto";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { artifactDigest, ProductState } from "./state.js";
import type { OwnerClients } from "./owner-clients.js";
import { isRecord } from "./types.js";

/** Bind creation to the names and concrete interfaces the human reviewed. */
export function validateArchitectureOperations(plan: Record<string, any>, operations: readonly unknown[]): void {
  for (const operation of operations) {
    if (!isRecord(operation) || operation.type !== "create_entity" || !["component", "design"].includes(String(operation.kind))) continue;
    const entities = operation.kind === "component" ? plan.components : plan.designs;
    const approved = entities.find((entity: unknown) => isRecord(entity) && entity.name === operation.name);
    if (!approved) throw new Error(`Creation of ${String(operation.kind)} ${String(operation.name)} was not included in the approved architecture. Prepare a revised architecture review.`);
    if (operation.kind !== "component") continue;
    const grouped = plan.interfaces.find((item: unknown) => isRecord(item) && item.component === operation.name && Array.isArray(item.ports));
    const expected = grouped?.ports ?? (plan.components.length === 1 && plan.interfaces.every((item: unknown) => isRecord(item) && typeof item.name === "string") ? plan.interfaces : null);
    if (!expected) continue;
    const ports = Array.isArray(operation.ports) ? operation.ports : [];
    if (ports.length !== expected.length) throw new Error(`Component ${String(operation.name)} ports differ from its approved interface.`);
    for (const descriptor of expected) {
      if (!isRecord(descriptor) || typeof descriptor.name !== "string") throw new Error("Approved port descriptors require names.");
      const port = ports.find(item => isRecord(item) && item.name === descriptor.name);
      if (!isRecord(port) || (descriptor.direction !== undefined && descriptor.direction !== port.direction)) throw new Error(`Port ${String(operation.name)}.${descriptor.name} differs from its approved interface.`);
      if (descriptor.width !== undefined) {
        const range = typeof port.range === "string" ? /^(\d+):(\d+)$/.exec(port.range) : null;
        const width = range ? Math.abs(Number(range[1]) - Number(range[2])) + 1 : port.range === undefined || port.range === null ? 1 : null;
        if (width !== descriptor.width) throw new Error(`Port ${String(operation.name)}.${descriptor.name} width differs from its approved concrete configuration.`);
      }
    }
  }
}

export const ARCHITECTURE_PROMPT = `ARCHITECTURE AND IMPLEMENTATION AUTHORITY
For new contentful packages, new components/designs, or changes to structured composition, first read existing bound context if applicable and call prepare_architecture_review. Wait for the architecture card's approve/revise/cancel decision. Approval is required even for an owner that saves content automatically. Use its architecture_review_id for package creation and the initial content proposal. A revision request requires a new review; cancellation stops this request. Subsequent text/RTL refinements use the ordinary proposal workflow.
A component defines an interface and an implementation. A design defines composition: typed instances and connections. A composite component owns an internal design (entry_design=false). Keep cohesive state machines/counters unified; decompose where reusable responsibilities and interfaces justify it. Never hide composition solely in SV or create unnecessary hierarchy. Generate concrete approved configurations; parameterized RTL generation is deferred.
Every new component, including children, needs set_entity_metadata.description in the same proposal. Explain purpose, interface behavior, clocks/reset, timing/state, corner cases and implementation assumptions where applicable; explain composite child responsibilities. Link document requirements, behavior, architecture, assumptions and verification criteria to entities.
Stored SV defines implemented behavior; structured ports/designs define interfaces/wiring. Description text guides implementation. Read fresh SV and wiring before describing existing implementations; distinguish implemented behavior from proposed intent and unresolved assumptions. Flag observed text/RTL disagreements and preserve both. Text edits alone never authorize RTL changes or automatic synchronization. Preserve user-authored explanations. No stored functional RTL means unimplemented; a compile-safe scaffold is not a functional implementation.`;

export function registerArchitectureTool(
  agent: { id: string; ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } } },
  state: ProductState, owners: OwnerClients, currentRequest: () => string,
  onPrepared?: (record: Record<string, any>) => Promise<void>,
): void {
  agent.ctx.systemPrompt?.section({ name: "spec2gds:architecture", order: 180, text: ARCHITECTURE_PROMPT });
  agent.ctx.tools.register(defineTool({
    name: "prepare_architecture_review",
    description: "Present a durable architecture for human approval before contentful creation or structured architecture changes. No content is saved by this tool.",
    parameters: {
      title: { type: "string", required: true },
      components: { type: "array", items: { type: "json" }, required: true },
      designs: { type: "array", items: { type: "json" }, required: true },
      interfaces: { type: "array", items: { type: "json" }, required: true, description: "Use {component, ports:[{name,direction,width}]} for each component; widths describe the approved concrete configuration." },
      clocks_resets: { type: "array", items: { type: "string" }, required: true },
      decomposition_rationale: { type: "string", required: true },
      assumptions: { type: "array", items: { type: "string" }, required: true },
      open_questions: { type: "array", items: { type: "string" }, required: true },
      concrete_configuration: { type: "json", required: true },
    },
    output: { schema: { type: "json" }, render: (_args: unknown, value: unknown) => [{ type: "text", text: JSON.stringify(value) }] },
    async execute(args, exec) {
      try {
        if (!args.title.trim() || !args.decomposition_rationale.trim() || !args.components.length || !args.interfaces.length
          || !args.concrete_configuration || typeof args.concrete_configuration !== "object" || Array.isArray(args.concrete_configuration)) {
          throw new Error("Supply components, interfaces, decomposition rationale and a concrete configuration.");
        }
        for (const entities of [args.components, args.designs]) {
          if (entities.some(entity => !isRecord(entity) || typeof entity.name !== "string" || !entity.name.trim())
            || new Set(entities.map(entity => isRecord(entity) ? entity.name : null)).size !== entities.length) {
            throw new Error("Architecture components and designs require distinct nonempty names.");
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
            throw new Error("Architecture review requires a fresh owner context with the exact document identity and source revision.");
          }
          let originalRequest = currentRequest();
          if (originalRequest.trim().startsWith("{")) {
            try {
              const decision = JSON.parse(originalRequest);
              const previous = isRecord(decision) && typeof decision.architecture_review_id === "string" ? state.architectureReview(decision.architecture_review_id) : null;
              if (previous?.sessionId === String(agent.id)) originalRequest = previous.originalRequest;
            } catch { /* An ordinary user request can contain non-JSON prose. */ }
          }
          record = { reviewId: randomUUID(), sessionId: String(agent.id), callId: String(exec.callId), status: "pending",
            plan: args, digest: artifactDigest(args), originalRequest,
            documentId: binding?.documentId ?? null, ownerDocumentKey: context?.owner_document_key ?? binding?.ownerDocumentKey ?? null,
            scope: binding?.scope ?? null, entityId: binding?.entityId ?? null,
            sourceRevision: context?.source_revision_hash ?? null, createdAt: new Date().toISOString() };
          state.storeArchitecture(record);
        }
        if (record.status === "pending") await onPrepared?.(record);
        return snapshotJsonValue({ architecture_review: record,
          instruction: "The architecture card is ready. Await approval before package or content creation; essential open questions must be resolved in a revised review." }) as JsonValue;
      } catch (error) { return { creation_error: error instanceof Error ? error.message : String(error) }; }
    },
  }));
}
