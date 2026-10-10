/** Spec-specific operations over the independent Harness flow executor. */
import type { Context } from "@deepseek-ai/cordis";
import type { Agent } from "@deepseek-ai/dsh-agent";
import { SessionId } from "@deepseek-ai/dsh-session";
import { ToolCallId } from "@deepseek-ai/dsh-llm";
import { FlowOperationError } from "@deepseek-ai/dsh-flow-runtime";
import type { FlowExecutionId, FlowOperationContext, FlowRuntime, FlowView } from "@deepseek-ai/dsh-flow";
import { registerFlowTools } from "@deepseek-ai/dsh-tool-flow";
import type { ToolRunContext, ToolExecutionToken, JsonSchemaNode } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import type { ProductState } from "./state.js";
import { artifactDigest } from "./state.js";
import { ServiceClients, ServiceError } from "./service-clients.js";
import type { SourceCreations } from "./source-creation.js";
import type { InstructionBundle } from "./instructions.js";
import { prepareArchitectureCommand } from "./commands/architecture-review.js";
import { submitSpecChangeCommand, recoverSpecSubmission, requiresSpecArchitecture } from "./commands/submit-spec-change.js";
import { validateServiceOperations, parseServiceOperationContract } from "./service-operation-schema.js";
import type { SessionBinding, AssistantPreset } from "./types.js";
import { isRecord } from "./types.js";
import { normalizeSpecFormatting } from "./normalize.js";
import { validateArchitectureOperations } from "./architecture-review.js";

const object: JsonSchemaNode = { type: "object", additionalProperties: true };
const string: JsonSchemaNode = { type: "string" };
const shape = (properties: Record<string, JsonSchemaNode>): JsonSchemaNode => ({ type: "object", properties, required: Object.keys(properties), additionalProperties: false });
const requestSchema = shape({ request_id: string });
const reviewSchema = shape({ review_id: string });
const bindingSchema = shape({ session_id: string, document_id: string, source_revision_hash: string, path: string });
const receiptSchema = shape({ proposal_id: string, state: { type: "string", enum: ["applied", "discarded", "rejected", "stale"] }, source_revision_hash: string });

export interface SpecFlowOptions {
  ctx: Context; flows: FlowRuntime; state: ProductState; owners: ServiceClients; creations: SourceCreations;
  instructionsFor(id: string): InstructionBundle; preferredService: string; pollMillis: number;
  activate(id: string): Promise<SessionBinding>;
}
/** Build one complete atomic batch; model output never selects service commands. */
export function componentFlowOperations(documentId: string, plan: Record<string, any>, draft: Record<string, any>, identity: string): Record<string, unknown>[] {
  if (plan.components.length !== 1 || plan.designs.length || draft.name !== plan.components[0].name) throw new Error("This flow requires exactly the approved leaf Component.");
  if (!draft.description?.trim() || !draft.systemverilog?.trim()) throw new Error("The complete Component requires description and functional SystemVerilog.");
  if (!Array.isArray(draft.ports) || draft.ports.some((port: Record<string, any>) => !port.name?.trim() || !["in", "out", "inout"].includes(port.direction) || !Number.isSafeInteger(port.width) || port.width < 1) || new Set(draft.ports.map((port: Record<string, any>) => port.name)).size !== draft.ports.length) throw new Error("The complete Component requires unique ports with positive concrete widths and directions.");
  const entity = { document_id: documentId, entity_kind: "component", entity_id: "flow_component" };
  const operations: Record<string, unknown>[] = [
    { operation_id: "create_component", type: "create_entity", kind: "component", name: draft.name, entity_id: "flow_component", instances: [],
      ports: draft.ports.map((p: Record<string, any>) => ({ name: p.name, family: "wire", direction: p.direction, ...(p.width > 1 ? { range: `${p.width - 1}:0` } : {}) })), systemverilog: draft.systemverilog },
    { operation_id: "describe_component", type: "set_entity_metadata", entity, description: draft.description },
  ];
  if (draft.narrative?.trim()) operations.push({ operation_id: "component_narrative", type: "upsert_narrative_block", block: {
    block_id: "flow_narrative_" + artifactDigest(identity).replace(/^sha256:/, "").slice(0, 24), type: "paragraph", text: draft.narrative, entity_refs: [entity] } });
  validateArchitectureOperations(plan, operations);
  return operations;
}
function record(input: JsonValue): Record<string, any> { if (!isRecord(input)) throw new Error("Flow operation requires an object."); return input; }
function json(value: unknown): JsonValue { const output = snapshotJsonValue(value); if (output === undefined) throw new Error("Flow result is not JSON."); return output as JsonValue; }
function known(error: unknown): never { if (error instanceof FlowOperationError) throw error; throw new FlowOperationError(error instanceof Error ? error.message : String(error), error instanceof ServiceError && error.uncertain); }

/** Product adapter owns semantic guards, approvals, and authoritative receipt reads. */
export class SpecFlows {
  private closing = false;
  private readonly attached = new Set<string>();
  private polling: Promise<void> | undefined;
  private readonly handles = new Set<() => void>();
  private readonly timer: ReturnType<typeof setInterval>;
  constructor(private readonly options: SpecFlowOptions) {
    if (!Number.isSafeInteger(options.pollMillis) || options.pollMillis < 100) throw new Error("flowReceiptPollMillis must be at least 100.");
    const { ctx, state, flows, creations } = options;
    state.database.exec(`CREATE TABLE IF NOT EXISTS flow_goal_claims(execution_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, goal_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS flow_decision_outbox(delivery_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, value_json TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS flow_revision_outbox(delivery_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, parent_revision INTEGER NOT NULL, feedback TEXT NOT NULL, target_id TEXT);
      CREATE TABLE IF NOT EXISTS flow_goal_releases(execution_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, goal_json TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);`);
    this.registerOperations();
    ctx.on("flow/changed", flow => { void this.changed(flow).catch(error => ctx.logger.warn(String(error))); });
    ctx.on("flow/control-accepted", async ({ flow, command }) => {
      if (!flow.definition.id.startsWith("spec2gds.") || command !== "resume") return;
      for (const sessionId of flow.conversations) {
        const execution = ctx.eventSystems.get(sessionId);
        if (execution && ["needs-resume", "paused"].includes(execution.status)) await ctx.eventSystems.control(sessionId, execution.revision, "resume");
      }
    });
    ctx.on("flow/model-phase", ({ agent, executionId, sourceSessionId, scope }) => {
      if (this.preset(String(sourceSessionId), executionId) === "goal" && ctx.eventSystems.get(sourceSessionId)) scope.effect(() => ctx.eventSystems.routeRequestBudget(agent, sourceSessionId));
    });
    ctx.on("flow/model-input-accepted", ({ executionId, agent }) => {
      const request = state.database.prepare("SELECT request_id FROM source_creation_requests WHERE json_extract(request_json,'$.flowExecutionId')=? AND json_extract(request_json,'$.destinationSessionId')=?")
        .get(executionId, agent.id) as { request_id: string } | undefined;
      if (request) creations.markConversationBound(request.request_id);
      else {
        const execution = flows.get(executionId, { kind: "host", sessionId: agent.id });
        const destination = execution.nodes.findLast(node => node.id === "destination" && node.state === "succeeded");
        if (isRecord(destination?.output) && typeof destination.output.request_id === "string") {
          const reused = creations.get(destination.output.request_id);
          if (reused.destinationSessionId === agent.id && reused.sourceRevisionHash) creations.markConversationBound(reused.requestId);
        }
      }
    });
    ctx.effect(() => ctx.goals.registerControlGuard((agent, operation) => flows.active(agent.id) || state.database.prepare("SELECT 1 FROM flow_goal_claims WHERE session_id=?").get(agent.id)
      ? `A flow is active. Use its controls before ${operation} of the Goal.` : undefined));
    this.timer = setInterval(() => { this.kick(); }, options.pollMillis);
    ctx.effect(() => async () => { this.closing = true; clearInterval(this.timer); for (const dispose of this.handles) dispose(); await this.polling; });
  }
  attach(agent: Agent, binding?: SessionBinding | null): void {
    if (this.attached.has(String(agent.id))) return;
    const preset = binding?.preset ?? agent.session.header.agentPreset ?? "focused";
    if (preset === "orchestrated" || agent.session.header.origin === "subagent" || binding?.domain === "circuit") return;
    this.attached.add(String(agent.id));
    const context = binding?.domain === "spec" ? binding.scope === "entity" ? "spec2gds.entity" : "spec2gds.document" : "spec2gds.new";
    const dispose = registerFlowTools(agent, this.options.flows, context); this.handles.add(dispose);
    agent.ctx.effect(() => () => { dispose(); this.handles.delete(dispose); this.attached.delete(String(agent.id)); });
    agent.ctx.systemPrompt.section({ name: "spec2gds:flows", order: 185, text:
      this.instructions(String(agent.id))! });
    agent.ctx.tools.guard(exec => this.options.flows.active(agent.id) && ["update_goal"].includes(exec.name)
      ? "The flow controls this request. Resolve its wait or use its controls." : undefined);
  }
  instructions(sessionId: string): string | undefined {
    return this.attached.has(sessionId) ? "All Spec writes use published flows. Use flow_create_empty_spec for an empty new Spec, flow_create_spec_with_component for a new Spec with a complete leaf Component, flow_add_component for a new leaf Component in this document, and flow_edit_spec for edits to the bound Spec or selected Component or Design. Supply a readable title and the full original request. The flow reads fresh context, obtains required architecture approval, and waits for the exact saved receipt. Read-only explanations can use get_bound_context. If no published flow supports the request, report that limitation. Do not use another write path or infer completion from a preview." : undefined;
  }
  creationConfirmation(flow: FlowView): Record<string, unknown> | undefined {
    if (!["spec2gds.create_empty_spec", "spec2gds.create_spec_with_component"].includes(flow.definition.id)) return undefined;
    const destination = flow.nodes.find(node => node.id === "destination" && node.state === "succeeded");
    if (!isRecord(destination?.output) || typeof destination.output.request_id !== "string") return undefined;
    const creation = this.options.creations.get(destination.output.request_id);
    if (!creation.sourceRevisionHash || !creation.serviceDocumentKey) return undefined;
    return { path: creation.destination, conversation_id: creation.destinationSessionId,
      binding_confirmed: creation.status === "bound" && this.options.state.getBinding(creation.destinationSessionId)?.status === "active",
      content_required: flow.definition.id !== "spec2gds.create_empty_spec",
      editor_url: `${creation.serviceBaseUrl}/editor?owner_document_key=${encodeURIComponent(creation.serviceDocumentKey)}` };
  }
  private binding(sessionId: string): SessionBinding {
    const binding = this.options.state.getBinding(sessionId);
    if (!binding || binding.domain !== "spec" || binding.status !== "active") throw new Error("This flow requires an active Spec conversation.");
    return binding;
  }
  private commandContext(context: FlowOperationContext, sessionId: string, args: unknown): ToolRunContext {
    return { callId: ToolCallId(context.operationId), rootCallId: ToolCallId(context.operationId), token: Symbol("flow-command") as ToolExecutionToken,
      name: "spec-flow-command", arguments: args, signal: context.signal, agent: this.options.ctx.agents.get(SessionId(sessionId)), deferContext() {}, concludeTurn() {} };
  }
  private preset(sessionId: string, executionId?: FlowExecutionId): AssistantPreset {
    const binding = this.options.state.getBinding(sessionId);
    const recorded = executionId ? this.options.flows.get(executionId, { kind: "host", sessionId: SessionId(sessionId) }).callerContext : null;
    const preset = binding?.preset ?? this.options.ctx.agents.get(SessionId(sessionId))?.session.header.agentPreset
      ?? (isRecord(recorded) ? recorded.agentPreset : undefined);
    return preset === "goal" ? "goal" : "focused";
  }
  private async contextPages(binding: SessionBinding, context: FlowOperationContext): Promise<Record<string, any>> {
    const signal = context.signal;
    const pages: Record<string, unknown>[] = []; const cursors = new Set<string>(); let cursor: string | undefined, revision: unknown;
    do {
      const page = await this.options.owners.contextPage(binding, cursor ? { cursor } : {}, signal);
      if (page.schema_version !== "spec2gds.assistant-context-page.v1" || !Array.isArray(page.records) || typeof page.incomplete !== "boolean"
        || (!page.incomplete && page.next_cursor !== null)) throw new Error("Spec flows require the complete paged context contract. No legacy or malformed context was accepted.");
      if (page.document_id !== binding.documentId || typeof page.source_revision_hash !== "string" || (revision !== undefined && revision !== page.source_revision_hash)) throw new Error("Context identity or revision changed during pagination.");
      if (page.scope !== binding.scope || (binding.scope === "entity" && (!isRecord(page.target) || page.target.entity_id !== binding.entityId || page.target.entity_kind !== binding.entityKind))) throw new Error("Context does not match the bound Spec scope.");
      revision = page.source_revision_hash; pages.push(page);
      if (page.incomplete === true && (typeof page.next_cursor !== "string" || !page.next_cursor || page.next_cursor === cursor)) throw new Error("Incomplete context has no advancing cursor.");
      cursor = page.incomplete === true ? String(page.next_cursor) : undefined;
      if (cursor && cursors.has(cursor)) throw new Error("Context pagination contains a repeated cursor.");
      if (cursor) cursors.add(cursor);
      if (Buffer.byteLength(JSON.stringify(pages)) > this.options.flows.get(context.executionId, { kind: "host", sessionId: SessionId(binding.sessionId) }).limits.maxRetainedBytes / 2) throw new Error("Required context exceeds the flow data limit.");
    } while (cursor);
    return { pages, source_revision_hash: revision, document_id: binding.documentId };
  }
  private previousCreation(context: FlowOperationContext) {
    const actor = { kind: "host" as const, sessionId: context.sourceSessionId };
    let parent = this.options.flows.get(context.executionId, actor).parentExecutionId;
    const visited = new Set<string>();
    while (parent && !visited.has(parent)) {
      visited.add(parent);
      const execution = this.options.flows.get(parent, actor);
      const destination = execution.nodes.find(node => node.id === "destination" && node.state === "succeeded");
      if (isRecord(destination?.output) && typeof destination.output.request_id === "string") {
        const creation = this.options.creations.get(destination.output.request_id);
        if (creation.sourceRevisionHash && ["created", "reserved", "bound"].includes(creation.status)) return creation;
      }
      parent = execution.parentExecutionId;
    }
    return null;
  }
  /** Explicit designer revision; the prior review and creation receipt remain immutable. */
  async reviseArchitecture(reviewId: string, revision: number, feedback: string, sessionId: string): Promise<FlowView> {
    const { state, flows } = this.options, review = state.architectureReview(reviewId);
    if (!review?.flow_execution_id) throw new Error("This architecture has no flow execution.");
    const parent = flows.get(review.flow_execution_id, { kind: "host", sessionId: SessionId(sessionId) });
    if (parent.status !== "failed" || parent.revision !== revision || !feedback.trim()) throw new Error("Revision requires the observed failed flow and explicit feedback.");
    const deliveryId = "revision:" + parent.id + ":" + revision;
    const old = state.database.prepare("SELECT feedback,target_id FROM flow_revision_outbox WHERE delivery_id=?").get(deliveryId) as { feedback: string; target_id: string | null } | undefined;
    if (old && old.feedback !== feedback) throw new Error("Revision identity was reused with different feedback.");
    if (!old) state.database.prepare("INSERT INTO flow_revision_outbox VALUES(?,?,?,?,NULL)").run(deliveryId, parent.id, revision, feedback);
    const actor = { kind: "host" as const, sessionId: parent.sourceSessionId }, inputs = record(parent.inputs);
    const replacement = await flows.start({ definition: parent.definition, inputs: json({ ...inputs, request: inputs.request + "\nDesigner revision: " + feedback }), actor,
      context: parent.definition.publication!.contexts[0]!, requestId: deliveryId, parentExecutionId: parent.id, parentRevision: revision, deferred: true });
    state.database.prepare("UPDATE flow_revision_outbox SET target_id=? WHERE delivery_id=?").run(replacement.id, deliveryId);
    flows.advance(replacement.id);
    return replacement;
  }
  private registerOperations(): void {
    const { flows, state, owners, creations } = this.options;
    const add = (id: string, inputSchema: JsonSchemaNode, outputSchema: JsonSchemaNode, effect: "read" | "write", execute: (inputs: Record<string, any>, context: FlowOperationContext) => Promise<unknown>, reconcile?: (inputs: Record<string, any>, context: FlowOperationContext) => Promise<unknown | undefined>) => {
      const run = async (input: JsonValue, context: FlowOperationContext): Promise<JsonValue> => { try { return json(await execute(record(input), context)); } catch (error) { return known(error); } };
      this.options.ctx.effect(() => flows.registerOperation({ id: "spec2gds." + id, version: "2.0.0", inputSchema, outputSchema, effect, cancellation: effect === "read" ? "cooperative" : "await-settlement", recovery: effect === "read" ? "repeat" : reconcile ? "receipt" : "manual", execute: run,
        ...(reconcile ? { reconcile: async (input: JsonValue, context: FlowOperationContext) => { const result = await reconcile(record(input), context); return result === undefined ? undefined : json(result); } } : {}) }));
    };
    add("bound_document", shape({}), shape({ session_id: string }), "read", async (_input, context) => { const binding = this.binding(String(context.sourceSessionId)); if (binding.scope !== "document") throw new Error("Component creation requires a document-bound Spec conversation."); return { session_id: binding.sessionId }; });
    add("architecture_context", object, object, "read", async (input, context) => {
      const previous = input.creation ? this.previousCreation(context) : null;
      if (previous) {
        if (!previous.serviceDocumentKey) throw new Error("The confirmed Spec has no service document identity.");
        await context.claimConversation(SessionId(previous.destinationSessionId));
        const binding = state.getBinding(previous.destinationSessionId) ?? { ...previous.reservation?.session, sessionId: previous.destinationSessionId, domain: "spec", scope: "document", status: "active", serviceUrl: previous.serviceBaseUrl, serviceDocumentKey: previous.serviceDocumentKey, documentId: previous.documentId } as SessionBinding;
        return { ...await this.contextPages(binding, context), existing_created_spec: true, destination_session_id: previous.destinationSessionId, service_document_key: previous.serviceDocumentKey };
      }
      if (input.creation) return { new_spec: true, service: this.options.preferredService };
      const source = await this.contextPages(this.binding(String(context.sourceSessionId)), context);
      if (input.proposed_changes && input.proposed_changes.base_source_revision_hash !== source.source_revision_hash) throw new Error("The Spec changed after the edit draft. Start a new flow with fresh context.");
      return { ...source, ...(input.proposed_changes ? { proposed_changes: input.proposed_changes } : {}) };
    });
    const saveArchitecture = async (input: Record<string, any>, context: FlowOperationContext) => {
      const instructions = this.options.instructionsFor(String(context.sourceSessionId));
      if (flows.get(context.executionId, { kind: "host", sessionId: context.sourceSessionId }).definition.id !== "spec2gds.edit_spec" && (input.plan.components.length !== 1 || input.plan.designs.length)) throw new Error("Select one leaf Component for this flow.");
      const command = prepareArchitectureCommand({ id: String(context.sourceSessionId) }, state, owners, () => input.request,
        undefined, instructions, input.creation);
      const output = record(json(await command.execute(input.plan, this.commandContext(context, String(context.sourceSessionId), input.plan))));
      if (!output.architecture_review) throw new Error(String(output.creation_error ?? "Architecture review failed."));
      const saved = output.architecture_review;
      state.storeArchitecture({ ...saved, flow_execution_id: context.executionId,
        ...(input.context.proposed_changes ? { proposed_operations: normalizeSpecFormatting(input.context.proposed_changes.operations, input.context.document_id), approved_operations_digest: artifactDigest(normalizeSpecFormatting(input.context.proposed_changes.operations, input.context.document_id)) } : {}),
        ...(input.context?.existing_created_spec ? { destinationSessionId: input.context.destination_session_id, destinationSourceRevision: input.context.source_revision_hash, destinationServiceDocumentKey: input.context.service_document_key } : {}) });
      return { review_id: saved.reviewId };
    };
    add("record_architecture", object, reviewSchema, "write", saveArchitecture, async (input, context) => {
      return saveArchitecture(input, context);
    });
    add("approved_architecture", object, reviewSchema, "read", async (input, context) => {
      if (input.decision !== "approved") throw new Error(input.decision === "revised" ? "Architecture revision requested." : "Architecture cancelled.");
      state.requireArchitecture(String(context.sourceSessionId), input.review_id); return { review_id: input.review_id };
    });
    const prepare = async (input: Record<string, any>, context: FlowOperationContext) => {
      const previous = this.previousCreation(context);
      if (previous) {
        if (!input.empty) state.requireArchitecture(String(context.sourceSessionId), input.review_id);
        return { request_id: previous.requestId };
      }
      const output = await creations.prepare({ sourceSessionId: String(context.sourceSessionId), callId: context.operationId, flowExecutionId: context.executionId, originalRequest: input.request,
        title: input.title, preferredOwner: (record(flows.get(context.executionId, { kind: "host", sessionId: context.sourceSessionId }).inputs).service_url as string | undefined) ?? state.getBinding(String(context.sourceSessionId))?.serviceUrl ?? this.options.preferredService, preset: this.preset(String(context.sourceSessionId), context.executionId), empty: input.empty,
        ...(input.review_id ? { architectureReviewId: input.review_id } : {}), independent: true });
      const request = creations.get(String(output.requestId));
      const policy = await owners.specPolicy(request.serviceBaseUrl, context.signal);
      if (!policy.creationReceipts || (!input.empty && !policy.submissions)) throw new Error("This flow requires a Spec service with durable creation and submission receipts.");
      state.storeSourceCreation({ ...request, flowExecutionId: context.executionId }); return { request_id: request.requestId };
    };
    add("prepare_creation", object, requestSchema, "write", prepare, async (input, context) => {
      return prepare(input, context);
    });
    const create = async (input: Record<string, any>, context: FlowOperationContext) => {
      const request = creations.get(input.request_id);
      await creations.create(request.requestId, { serviceBaseUrl: request.serviceBaseUrl, documentId: request.documentId, title: request.title }, context.signal);
      return { request_id: request.requestId };
    };
    add("create_spec", requestSchema, requestSchema, "write", create, async (input, context) => {
      const request = creations.get(input.request_id); return request.creationReceipts || ["created", "reserved", "bound"].includes(request.status) ? create(input, context) : undefined;
    });
    const ensure = async (input: Record<string, any>, context: FlowOperationContext) => {
      await creations.restoreReservation(input.request_id);
      const request = creations.get(input.request_id), reservation = request.reservation;
      if (!reservation || !request.sourceRevisionHash) throw new Error("No confirmed creation receipt or conversation reservation.");
      const id = SessionId(request.destinationSessionId); await context.claimConversation(id);
      const native = this.options.ctx;
      if (!native.agents.get(id)) {
        const controller = native.get("sessionController"), registry = native.get("workspaceRegistry");
        if (await native.sessionPersistence.stat(id)) {
          await native.agents.resume({ resumeSessionId: id });
        } else if (controller && registry) {
          const workspace = await registry.create(reservation.workspace.path, reservation.workspace.title);
          await controller.create({ sessionId: id, workspaceId: workspace.id, agentPreset: request.preset });
        } else {
          const source = native.agents.get(context.sourceSessionId);
          await native.agents.create({ sessionId: id, meta: { cwd: reservation.workspace.path, agentPreset: request.preset }, agentOptions: source?.options ?? record(this.options.flows.get(context.executionId, { kind: "host", sessionId: context.sourceSessionId }).modelOptions ?? {}) });
        }
      }
      await this.options.activate(String(id));
      if (!(await native.sessions.flush(native.agents.get(id)!.session))) throw new Error("Destination conversation could not be persisted.");
      creations.markConversationBound(request.requestId);
      return { session_id: String(id), document_id: request.documentId, source_revision_hash: request.sourceRevisionHash, path: request.destination };
    };
    add("ensure_conversation", requestSchema, bindingSchema, "write", ensure, ensure);
    add("edit_context", object, shape({ session_id: string, context: object }), "read", async (_input, context) => {
      const binding = this.binding(String(context.sourceSessionId));
      return { session_id: binding.sessionId, context: { ...await this.contextPages(binding, context), operation_schema: await owners.operationContract(binding, context.signal) } };
    });
    add("validate_edit", object, shape({ session_id: string, context: object, draft: object, architecture_required: { type: "boolean" } }), "read", async (input, context) => {
      const binding = this.binding(String(context.sourceSessionId));
      if (!input.draft.supported) throw new Error(input.draft.unsupported_reason || "The requested edit is unsupported.");
      if (!input.draft.operations.length) throw new Error("The edit draft contains no changes.");
      if (input.draft.operations.some((operation: Record<string, unknown>) => operation.type === "create_entity" && operation.kind !== "design")) throw new Error("Use a dedicated creation flow for new Components.");
      if (input.draft.operations.some((operation: Record<string, unknown>) => operation.type === "create_entity") && binding.scope !== "document") throw new Error("Design creation requires a document-bound Spec conversation.");
      if (input.draft.base_source_revision_hash !== input.context.source_revision_hash) throw new Error("The draft did not preserve the authored source revision.");
      const draft = { ...input.draft, operations: normalizeSpecFormatting(input.draft.operations, binding.documentId) };
      validateServiceOperations(parseServiceOperationContract(input.context.operation_schema), draft.operations);
      return { session_id: binding.sessionId, context: input.context, draft, architecture_required: requiresSpecArchitecture(draft.operations) };
    });
    const submitEdit = async (input: Record<string, any>, context: FlowOperationContext) => {
      const binding = this.binding(input.session_id), contract = parseServiceOperationContract(input.context.operation_schema);
      const args = { ...input.draft, ...(input.review_id ? { architecture_review_id: input.review_id } : {}) };
      const command = submitSpecChangeCommand(binding, state, owners, contract, this.options.instructionsFor(binding.sessionId));
      const output = record(json(await command.execute(args as never, this.commandContext(context, binding.sessionId, args))));
      if (!output.success) throw new FlowOperationError(JSON.stringify(output.error ?? output), output.state === "reconcile");
      return { proposal_id: output.proposal_id, editor_url: `${binding.serviceUrl}/editor?owner_document_key=${encodeURIComponent(binding.serviceDocumentKey ?? "")}&view=activity` };
    };
    add("submit_edit", object, shape({ proposal_id: string, editor_url: string }), "write", submitEdit, async (input, context) => {
      const binding = this.binding(input.session_id), review = state.reviewForCall(input.session_id, context.operationId);
      if (!review) return submitEdit(input, context);
      if (requiresSpecArchitecture(input.draft.operations)) state.requireArchitecture(binding.sessionId, input.review_id, input.context.source_revision_hash);
      const receipt = await recoverSpecSubmission(binding, state, owners, review, context.signal);
      if (!receipt || !isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== review.artifactDigest) return undefined;
      return { proposal_id: review.proposalId, editor_url: `${binding.serviceUrl}/editor?owner_document_key=${encodeURIComponent(binding.serviceDocumentKey ?? "")}&view=activity` };
    });
    add("authoring_context", object, object, "read", async (input, context) => {
      const binding = this.binding(input.session_id), source = await this.contextPages(binding, context);
      const approval = state.requireArchitecture(binding.sessionId, input.review_id, source.source_revision_hash);
      return { ...source, architecture: approval.plan, operation_schema: await owners.operationContract(binding, context.signal) };
    });
    const submit = async (input: Record<string, any>, context: FlowOperationContext) => {
      const binding = this.binding(input.session_id), approval = state.requireArchitecture(binding.sessionId, input.review_id, input.context.source_revision_hash);
      const contract = parseServiceOperationContract(input.context.operation_schema);
      const args = { architecture_review_id: approval.reviewId, supported: true, unsupported_reason: null, base_source_revision_hash: input.context.source_revision_hash,
        title: "Add " + input.draft.name, summary: input.draft.description, rationale: approval.plan.decomposition_rationale, assumptions: approval.plan.assumptions,
        operations: componentFlowOperations(binding.documentId, approval.plan, input.draft, context.operationId) };
      const command = submitSpecChangeCommand(binding, state, owners, contract, this.options.instructionsFor(binding.sessionId));
      const output = record(json(await command.execute(args as never, this.commandContext(context, binding.sessionId, args))));
      if (!output.success) throw new FlowOperationError(JSON.stringify(output.error ?? output), output.state === "reconcile");
      if (!binding.serviceDocumentKey) throw new Error("The Spec binding has no service document identity.");
      return { proposal_id: output.proposal_id, editor_url: `${binding.serviceUrl}/editor?owner_document_key=${encodeURIComponent(binding.serviceDocumentKey)}&view=activity` };
    };
    add("submit_component", object, shape({ proposal_id: string, editor_url: string }), "write", submit, async (input, context) => {
      const review = state.reviewForCall(input.session_id, context.operationId);
      if (!review) return submit(input, context);
      const binding = this.binding(input.session_id);
      state.requireArchitecture(binding.sessionId, input.review_id, input.context.source_revision_hash);
      let receipt: Record<string, unknown> | undefined;
      try { receipt = await recoverSpecSubmission(binding, state, owners, review, context.signal); }
      catch (error) { throw new FlowOperationError(error instanceof Error ? error.message : String(error), error instanceof ServiceError); }
      if (!receipt) return undefined;
      if (!isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== review.artifactDigest) return undefined;
      if (["applied", "pending", "approval_required", "discarded", "rejected", "stale"].includes(String(receipt.state))) return { proposal_id: review.proposalId, editor_url: `${binding.serviceUrl}/editor?owner_document_key=${encodeURIComponent(binding.serviceDocumentKey ?? "")}&view=activity` };
      return undefined;
    });
    add("require_saved", receiptSchema, shape({ proposal_id: string, state: { type: "string", const: "applied" }, source_revision_hash: string }), "read", async (input, context) => {
      const flow = flows.get(context.executionId, { kind: "host", sessionId: context.sourceSessionId });
      const wait = flow.nodes.findLast(node => node.kind === "wait" && isRecord(node.inputs) && node.inputs.kind === "spec-receipt");
      if (!wait || !isRecord(wait.inputs) || wait.inputs.proposal_id !== input.proposal_id) throw new Error("Saved result does not match the submitted proposal.");
      const binding = this.binding(String(wait.inputs.session_id)), proposal = state.getReview(binding.sessionId, input.proposal_id);
      if (!proposal) throw new Error("Submitted proposal is unavailable.");
      const receipt = await owners.specSubmission(binding, proposal.proposalId, context.signal);
      const result = record(json(receipt.service_result ?? receipt.owner_result ?? {}));
      const revision = String(result.source_revision_hash ?? receipt.source_revision_hash ?? "");
      if (receipt.state !== "applied" || !isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== proposal.artifactDigest || !revision || revision !== input.source_revision_hash) {
        throw new Error("The Spec change has no matching applied service receipt; its request remains incomplete.");
      }
      return { proposal_id: proposal.proposalId, state: "applied", source_revision_hash: revision };
    });
  }
  private async changed(flow: FlowView): Promise<void> {
    if (!flow.definition.id.startsWith("spec2gds.")) return;
    const { ctx, state } = this.options;
    const source = ctx.agents.get(flow.sourceSessionId);
    if (flow.parentExecutionId && flow.status === "running") state.database.prepare("UPDATE OR IGNORE flow_goal_claims SET execution_id=? WHERE execution_id=?").run(flow.id, flow.parentExecutionId);
    const old = state.database.prepare("SELECT goal_json FROM flow_goal_claims WHERE execution_id=?").get(flow.id) as { goal_json: string } | undefined;
    if (!old && flow.status === "running") {
      const goal = source ? ctx.goals.get(source) : undefined;
      if (goal?.phase === "active") {
        const paused = ctx.goals.pause(source!, goal);
        state.database.prepare("INSERT INTO flow_goal_claims VALUES(?,?,?)").run(flow.id, flow.sourceSessionId, JSON.stringify({ id: paused.id, revision: paused.revision }));
      }
    } else if (old && flow.status === "cancelled") {
      state.database.prepare("DELETE FROM flow_goal_claims WHERE execution_id=?").run(flow.id);
    } else if (old && flow.status === "succeeded") {
      // Release the guard and record the native Goal delivery in one product
      // transaction. The native session commit is a separate receipt.
      state.database.exec("BEGIN IMMEDIATE");
      try {
        state.database.prepare("INSERT OR IGNORE INTO flow_goal_releases(execution_id,session_id,goal_json) VALUES(?,?,?)").run(flow.id, flow.sourceSessionId, old.goal_json);
        state.database.prepare("DELETE FROM flow_goal_claims WHERE execution_id=?").run(flow.id);
        state.database.exec("COMMIT");
      } catch (error) { state.database.exec("ROLLBACK"); throw error; }
    }
    this.kick();
  }
  kick(): void {
    if (this.closing || this.polling) return;
    this.polling = this.poll().catch(error => this.options.ctx.logger.warn(String(error))).finally(() => { this.polling = undefined; });
  }
  private async poll(): Promise<void> {
    const { state, flows, owners } = this.options;
    const releases = state.database.prepare("SELECT execution_id,session_id,goal_json FROM flow_goal_releases WHERE delivered=0").all() as Array<{ execution_id: string; session_id: string; goal_json: string }>;
    for (const release of releases) {
      const source = this.options.ctx.agents.get(SessionId(release.session_id));
      if (!source || flows.active(source.id)) continue;
      const claim = JSON.parse(release.goal_json), goal = this.options.ctx.goals.get(source);
      if (goal?.phase === "paused" && goal.id === claim.id && goal.revision === claim.revision) this.options.ctx.goals.resume(source, claim);
      if (!(await this.options.ctx.sessions.flush(source.session))) continue;
      state.database.prepare("UPDATE flow_goal_releases SET delivered=1 WHERE execution_id=?").run(release.execution_id);
    }
    const rows = state.database.prepare("SELECT delivery_id,execution_id,value_json FROM flow_decision_outbox WHERE delivered=0").all() as Array<{ delivery_id: string; execution_id: string; value_json: string }>;
    for (const row of rows) {
      const value = JSON.parse(row.value_json), review = state.architectureReview(value.review_id);
      if (!review) continue;
      const actor = { kind: "host" as const, sessionId: SessionId(review.sessionId) }, flow = flows.get(row.execution_id as FlowExecutionId, actor);
      if (!flow.decisions[row.delivery_id]) {
        if (flow.status !== "waiting" || !isRecord(flow.pending?.request) || flow.pending.request.review_id !== value.review_id) continue;
        await flows.answer(flow.id, flow.revision, flow.pending!.id, row.delivery_id, value, actor);
      }
      if (value.decision === "revised") {
        const result = await flows.settled(flow.id);
        if (result.status === "failed") {
          const inputs = record(flow.inputs), request = inputs.request + "\nDesigner revision: " + value.feedback;
          await flows.start({ definition: flow.definition, inputs: json({ ...inputs, request }), actor, context: flow.definition.publication!.contexts[0]!, requestId: "revision:" + row.delivery_id, parentExecutionId: flow.id, parentRevision: result.revision });
        }
      }
      if (value.decision === "cancelled") {
        const current = flows.get(flow.id, actor);
        if (current.status !== "cancelled" && current.allowed_actions.includes("cancel")) await flows.control(current.id, current.revision, "cancel", actor);
      }
      state.database.prepare("UPDATE flow_decision_outbox SET delivered=1 WHERE delivery_id=?").run(row.delivery_id);
    }
    const sessions = new Set([...state.listBindings(true).map(binding => SessionId(binding.sessionId)), ...state.listArchitectureReviews().filter(r => r.flow_execution_id).map(r => SessionId(r.sessionId))]);
    for (const sessionId of sessions) for (const flow of flows.list({ kind: "host", sessionId })) {
      if (flow.status !== "waiting" || !isRecord(flow.pending?.request)) continue;
      if (flow.pending.request.kind === "architecture") {
        const review = state.architectureReview(String(flow.pending.request.review_id));
        if (review && ["approved", "revised", "cancelled"].includes(review.status)) state.database.prepare("INSERT OR IGNORE INTO flow_decision_outbox(delivery_id,execution_id,value_json) VALUES(?,?,?)")
          .run(`architecture:${review.reviewId}:${review.status}`, flow.id, JSON.stringify({ review_id: review.reviewId, decision: review.status, feedback: review.feedback ?? "" }));
        continue;
      }
      if (flow.pending.request.kind !== "spec-receipt") continue;
      const request = flow.pending.request, binding = this.binding(String(request.session_id)), proposal = state.getReview(binding.sessionId, String(request.proposal_id));
      if (!proposal) continue;
      try {
        const receipt = await owners.specSubmission(binding, proposal.proposalId);
        if (!isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== proposal.artifactDigest) {
          await flows.reportWaitDiagnostic(flow.id, flow.revision, flow.pending!.id, "The service receipt does not match this exact proposal artifact.", { kind: "host", sessionId }); continue;
        }
        if (!["applied", "discarded", "rejected", "stale"].includes(String(receipt.state))) {
          await flows.reportWaitDiagnostic(flow.id, flow.revision, flow.pending!.id, undefined, { kind: "host", sessionId }); continue;
        }
        const result = record(json(receipt.service_result ?? receipt.owner_result ?? {}));
        const savedRevision = receipt.state === "applied" ? String(result.source_revision_hash ?? receipt.source_revision_hash ?? "") : "";
        if (receipt.state === "applied" && !savedRevision) throw new Error("Saved receipt has no source revision.");
        if (proposal.state !== receipt.state) state.transitionReview(binding.sessionId, proposal.proposalId, [proposal.state], receipt.state === "applied" ? "applied" : receipt.state === "stale" ? "stale" : receipt.state === "rejected" ? "rejected" : "discarded", { serviceResult: result });
        await flows.answer(flow.id, flow.revision, flow.pending!.id, "receipt:" + proposal.proposalId + ":" + receipt.state,
          { proposal_id: proposal.proposalId, state: String(receipt.state), source_revision_hash: savedRevision }, { kind: "host", sessionId });
      } catch (error) {
        const current = flows.get(flow.id, { kind: "host", sessionId });
        if (current.status === "waiting" && current.pending?.id === flow.pending!.id) await flows.reportWaitDiagnostic(current.id, current.revision, current.pending.id, "Spec receipt remains pending: " + String(error), { kind: "host", sessionId });
      }
    }
  }
}
