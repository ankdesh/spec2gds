/** Durable architecture approval is separate from the owner's content policy. */
import { randomUUID } from "node:crypto";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { artifactDigest, ProductState } from "./state.js";
import type { OwnerClients } from "./owner-clients.js";
import { isRecord } from "./types.js";

const ENTITY_SCHEMA = {
  type: "object", additionalProperties: true,
  properties: {
    name: { type: "string", required: true, description: "Distinct nonempty entity name. Use name, not component or design." },
    purpose: { type: "string" },
    description: { type: "string" },
  },
} as const;

const PORT_SCHEMA = {
  type: "object", additionalProperties: false,
  properties: {
    name: { type: "string", required: true },
    direction: { type: "string", enum: ["in", "out", "inout"], required: true, description: "Spec port direction: in, out or inout." },
    width: { type: "integer", required: true, description: "Positive concrete width in bits; use 1 for a scalar." },
  },
} as const;

const INTERFACE_SCHEMA = {
  oneOf: [
    { type: "object", additionalProperties: false, properties: {
      component: { type: "string", required: true, description: "Exact name from components." },
      ports: { type: "array", items: PORT_SCHEMA, required: true },
    } },
    PORT_SCHEMA,
  ],
} as const;

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
Architecture tool arguments use components=[{name,purpose}] and designs=[{name,purpose}] (designs may be empty for a leaf). Supply interfaces=[{component: exact_component_name, ports:[{name,direction,width}]}] for every component, using direction in/out/inout and positive integer widths. Portless components use ports=[]. Supply a nonempty concrete_configuration object such as {width:16,reset:"synchronous active-high",overflow:"wrap"}. Record reasonable defaults as assumptions. Only essential unresolved requirements belong in open_questions; use [] when the request and explicit assumptions determine the implementation. If the tool reports an error, correct the specific fields before retrying; never repeat the unchanged invalid payload or claim a review/package exists.
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
      components: { type: "array", items: ENTITY_SCHEMA, required: true, description: "One or more components, each with name. Names must be nonempty and unique." },
      designs: { type: "array", items: ENTITY_SCHEMA, required: true, description: "Composition designs, each with name. Use [] for a leaf without composition." },
      interfaces: { type: "array", items: INTERFACE_SCHEMA, required: true, description: "Use {component, ports:[{name,direction,width}]} for each component. Flat port descriptors are supported only for a single component. Directions are in/out/inout." },
      clocks_resets: { type: "array", items: { type: "string" }, required: true },
      decomposition_rationale: { type: "string", required: true },
      assumptions: { type: "array", items: { type: "string" }, required: true },
      open_questions: { type: "array", items: { type: "string" }, required: true, description: "Essential unresolved requirements that must block approval. Use [] when requirements and stated assumptions suffice." },
      concrete_configuration: { type: "object", additionalProperties: true, required: true, description: "Nonempty object containing approved concrete values, e.g. {width:16,reset:'synchronous active-high',overflow:'wrap'}." },
    },
    output: { schema: { type: "json" }, render: (_args: unknown, value: unknown) => [{ type: "text", text: JSON.stringify(value) }] },
    async execute(args, exec) {
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
      } catch (error) { return { creation_error: error instanceof Error ? error.message : String(error),
        instruction: "Correct the reported architecture fields before retrying. Explain any remaining failure; do not claim architecture preparation or package creation succeeded." }; }
    },
  }));
}
