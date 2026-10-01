import type { Agent } from "@deepseek-ai/dsh-agent";
import type EventSystemService from "@deepseek-ai/dsh-event-system";
import type { EventSystemSnapshot } from "@deepseek-ai/dsh-event-system";
import type HttpSourceService from "@deepseek-ai/dsh-event-system-http";
import type { HttpSourceInput, HttpSourceId } from "@deepseek-ai/dsh-event-system-http";
import type { GoalService } from "@deepseek-ai/dsh-goal";
import { executionLimits, proposalExecutionDenial } from "./execution-policy.js";
import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import z from "@deepseek-ai/schemastery";
import { SessionId } from "@deepseek-ai/dsh-session";
import { OwnerClients, OwnerError } from "./owner-clients.js";
import { errorFromException, logProposalFailure, proposalError, publicReview } from "./proposal-presentation.js";
import { artifactDigest, ProductState } from "./state.js";
import { findProposal, findSpecChange, registerDomainTools } from "./tools.js";
import type { BindingInput, ProposalReview, ServiceConfig, SessionBinding, WorkspaceDescriptor } from "./types.js";
import { parseOwnerOperationContract } from "./owner-operation-schema.js";
import { isRecord } from "./types.js";
import { workspaceDescriptor } from "./workspaces.js";
import { registerSourceCreationTool, SOURCE_CREATION_PROMPT, SourceCreations, SourceCreationError, specDestination } from "./source-creation.js";

export const name = "spec2gds-harness-assistant";
export const inject = ["agents", "sessionPersistence", "promptCatalog", "promptCatalogYaml", "eventSystems", "eventSystemsYaml", "eventHttpSources", "goals"];
export const Config = z.object({
  provider: z.string().min(1).required(),
  model: z.string().min(1).required(),
  stateRoot: z.string().min(1).required(),
  scratchRoot: z.string().min(1).required(),
  specDocumentRoot: z.string().min(1).required(),
  specAllowlist: z.string().min(1).required(),
  circuitAllowlist: z.string().min(1).required(),
  requestTimeoutMs: z.number().min(100).max(300_000).required(),
  maxStepsPerTurn: z.number().step(1).min(1).max(20).required(),
  maxOutputTokens: z.number().step(1).min(128).max(32_768).required(),
  interactiveForms: z.boolean().required(),
  execution: z.object({ goal: z.any().required(), orchestrated: z.any().required() }).required(),
});

type ProductAgent = {
  id: string;
  session?: { header: { agentPreset?: string; parentSession?: string; delegationDepth?: number } };
  ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } };
};
type PromptCatalogService = {
  get(ref: { id: string; version: string }): unknown;
  bind(ref: { id: string; version: string }, variables: Readonly<Record<string, string>>): {
    sections: readonly { id: string; order: number; text: string }[];
  };
  seal(): void;
};
type AppContext = {
  agents: { get(id: unknown): ProductAgent | undefined };
  sessionPersistence: { list(): Promise<Array<{ header: { id: string } }>> };
  promptCatalog: PromptCatalogService;
  eventSystems: EventSystemService;
  goals: GoalService;
  eventHttpSources: HttpSourceService;
  on(event: string, listener: (...args: any[]) => unknown): () => void;
  effect(effect: () => void | (() => void)): void;
  inject(dependencies: string[], callback: (ctx: AppContext & {
    webServer: { register(route: unknown): () => void };
    connection: { authenticatedUrl(baseUrl: string): string };
  }) => void): void;
};

class HttpError extends Error {
  constructor(readonly status: number, message: string, readonly detail?: unknown) { super(message); }
}

function splitAllowlist(value: string): string[] {
  return value.split(",").map(item => item.trim()).filter(Boolean);
}

function sameOrigin(request: any): boolean {
  const origin = request.headers.origin;
  if (!origin) return true;
  return origin === `http://${request.headers.host}` || origin === `https://${request.headers.host}`;
}

function writeJson(response: any, status: number, value: unknown): void {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  response.end(JSON.stringify(value));
}

async function readBody(request: any, limit = 65_536): Promise<Record<string, unknown>> {
  if (!request.headers["content-type"]?.startsWith("application/json")) throw new HttpError(415, "Expected application/json.");
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > limit) throw new HttpError(413, "Request body is too large.");
    chunks.push(chunk);
  }
  try {
    const value: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!isRecord(value)) throw new Error();
    return value;
  } catch {
    throw new HttpError(400, "Request body must be a JSON object.");
  }
}

function bindingInput(value: Record<string, unknown>): BindingInput {
  if (value.domain !== "spec" && value.domain !== "circuit") throw new HttpError(400, "domain must be spec or circuit.");
  if (value.preset !== undefined && value.preset !== "focused" && value.preset !== "goal" && value.preset !== "orchestrated") {
    throw new HttpError(400, "preset must be focused, goal, or orchestrated.");
  }
  if (typeof value.serviceBaseUrl !== "string" || !value.serviceBaseUrl.trim()) throw new HttpError(400, "serviceBaseUrl is required.");
  if (typeof value.documentId !== "string" || !value.documentId.trim()) throw new HttpError(400, "documentId is required.");
  const scope = value.domain === "circuit" ? "document" : value.scope === "entity" ? "entity" : "document";
  if (scope === "entity" && (typeof value.entityKind !== "string" || !value.entityKind.trim() || typeof value.entityId !== "string" || !value.entityId.trim())) {
    throw new HttpError(400, "Entity Spec bindings require entityKind and entityId.");
  }
  return {
    domain: value.domain,
    preset: value.preset ?? "focused",
    serviceBaseUrl: value.serviceBaseUrl.trim(),
    documentId: value.documentId.trim(),
    ownerDocumentKey: typeof value.ownerDocumentKey === "string" ? value.ownerDocumentKey : undefined,
    scope,
    entityKind: typeof value.entityKind === "string" ? value.entityKind.trim() : undefined,
    entityId: typeof value.entityId === "string" ? value.entityId.trim() : undefined,
    title: typeof value.title === "string" ? value.title.trim() : undefined,
  };
}

/**
 * Enter DSH through its one-time browser token while retaining product launch
 * data across the token exchange's deliberate redirect to a clean root URL.
 * A relative target prevents an untrusted Host header from receiving the
 * process credential; URL fragments are browser-local and survive the 303.
 */
export function authenticatedLaunchLocation(
  connection: { authenticatedUrl(baseUrl: string): string },
  sessionId?: string,
  unbound = false,
): string {
  const authenticated = new URL(connection.authenticatedUrl("http://127.0.0.1"));
  if (sessionId === undefined) {
    return `${authenticated.pathname}${authenticated.search}${unbound ? "#spec2gds_unbound=1" : ""}`;
  }
  const launch = new URLSearchParams({ spec2gds_session: sessionId });
  return `${authenticated.pathname}${authenticated.search}#${launch}`;
}

export function maxModelStepsForTurn(
  preset: "focused" | "goal" | "orchestrated",
  focusedBase: number,
  clarified: boolean,
): number {
  return preset === "focused" ? focusedBase + (clarified ? 1 : 0) : 8;
}

export const UNBOUND_SOURCE_PROMPT = `This conversation is not bound to a design source.
Do not answer questions about an existing document, component, design, or requested edit without a binding. Do not claim that work was completed and do not create a goal.
If prepare_spec_document_creation is available and the user requests a new specification document, use it to show the creation card. No existing package or context read is needed. Otherwise tell the user to start a new conversation and choose a Spec Editor document or entity, or a Circuit Designer document.`;

export function apply(ctx: AppContext, rawConfig: Record<string, unknown>): void {
  const config: ServiceConfig = {
    provider: String(rawConfig.provider), model: String(rawConfig.model), stateRoot: resolve(String(rawConfig.stateRoot)),
    scratchRoot: resolve(String(rawConfig.scratchRoot)), specAllowlist: splitAllowlist(String(rawConfig.specAllowlist)),
    specDocumentRoot: resolve(String(rawConfig.specDocumentRoot)),
    circuitAllowlist: splitAllowlist(String(rawConfig.circuitAllowlist)), requestTimeoutMs: Number(rawConfig.requestTimeoutMs),
    maxStepsPerTurn: Number(rawConfig.maxStepsPerTurn), maxOutputTokens: Number(rawConfig.maxOutputTokens),
    interactiveForms: Boolean(rawConfig.interactiveForms),
  };
  const state = new ProductState(resolve(config.stateRoot, "assistant.sqlite3"));
  const owners = new OwnerClients(config.specAllowlist, config.circuitAllowlist, config.requestTimeoutMs);
  const creations = new SourceCreations(state, owners, config.specDocumentRoot, reserve);
  const attached = new Set<string>();
  const legacyExecutions = new Set<string>();
  const unboundGuards = new Map<string, () => void>();
  const executionConfig = rawConfig.execution;
  if (!isRecord(executionConfig)) throw new Error("execution configuration is required.");
  const limits = { goal: executionLimits("goal", executionConfig.goal, config.maxOutputTokens),
    orchestrated: executionLimits("orchestrated", executionConfig.orchestrated, config.maxOutputTokens) };
  const clarifiedTurns = new Map<string, number>();
  const latestUserRequests = new Map<string, string>();
  const ready = (async () => {
    await mkdir(config.scratchRoot, { recursive: true, mode: 0o700 });
    await mkdir(config.specDocumentRoot, { recursive: true, mode: 0o700 });
    const stored = new Set((await ctx.sessionPersistence.list()).map(item => String(item.header.id)));
    for (const binding of state.listCreatingBindings()) stored.has(binding.sessionId) ? state.activateBinding(binding.sessionId) : state.deleteBinding(binding.sessionId);
    state.recoverInterruptedReviews();
    state.recoverInterruptedSourceCreations();
    for (const domain of ["spec", "circuit"] as const) {
      ctx.promptCatalog.get({ id: `spec2gds.${domain}`, version: "1.0.0" });
      for (const preset of ["goal", "orchestrated"] as const) {
        ctx.eventSystems.definition(`spec2gds.${domain}.${preset}`, "1.0.0");
      }
    }
    ctx.promptCatalog.seal();
    await ctx.eventSystems.ready;
    await ctx.eventHttpSources.ready;
    for (const binding of state.listBindings(true)) {
      if (binding.preset !== "focused" && stored.has(binding.sessionId) && !ctx.eventSystems.get(SessionId(binding.sessionId))) legacyExecutions.add(binding.sessionId);
    }
    ctx.eventSystems.seal();
  })();

  const attach = async (agent: ProductAgent, binding: SessionBinding): Promise<void> => {
    if (attached.has(agent.id)) return;
    if (legacyExecutions.has(String(agent.id))) {
      agent.ctx.systemPrompt?.section({ name: "spec2gds:legacy-execution", order: 150, complete: true,
        text: "This conversation is retained as readable history. Start a new bound conversation to use the updated preset." });
      attached.add(agent.id);
      return;
    }
    unboundGuards.get(agent.id)?.();
    unboundGuards.delete(agent.id);
    owners.assertStoredBinding(binding);
    let operationContract;
    let schemaError;
    try {
      if (binding.domain === "spec") {
        const policy = await owners.specPolicy(binding.ownerUrl);
        agent.ctx.systemPrompt?.section({ name: "spec2gds:approval-policy", order: 205,
          text: policy.approval_policy === "automatic"
            ? "The Spec owner currently allows automatic validated submissions. Await its saved receipt and report the resulting revision. Record defaults as assumptions; clarify genuinely missing inputs."
            : "The Spec owner currently requires human approval. Keep submissions pending until an explicit stored-proposal decision." });
      }
      if (binding.domain === "spec" && !binding.ownerDocumentKey) {
        const context = await owners.context(binding);
        if (typeof context.owner_document_key === "string") {
          state.pinOwnerDocument(binding.sessionId, context.owner_document_key);
          binding.ownerDocumentKey = context.owner_document_key;
        }
      }
      operationContract = parseOwnerOperationContract(await owners.operationContract(binding));
    } catch (error) {
      schemaError = error instanceof Error ? error.message : String(error);
    }
    const membership = ctx.eventSystems.membership(SessionId(agent.id));
    const specialist = membership !== undefined && !membership.primary;
    registerDomainTools(agent.ctx, binding, state, owners, ctx.promptCatalog,
      review => publishPreparedReview(binding, review),
      () => latestUserRequests.get(binding.sessionId) ?? "", config.interactiveForms && !specialist,
      operationContract, schemaError, undefined, specialist);
    if (binding.preset !== "focused" && !specialist) {
      await ctx.eventSystems.attach(agent as unknown as Agent, binding.preset,
        ctx.eventSystems.definition(`spec2gds.${binding.domain}.${binding.preset}`, "1.0.0"), limits[binding.preset]);
    }
    if (binding.preset !== "focused") {
      const native = agent as unknown as Agent;
      native.ctx.tools.guard(exec => {
        const member = ctx.eventSystems.membership(native.id);
        const execution = member && ctx.eventSystems.get(member.conversationId);
        if (exec.name.startsWith("prepare_") && exec.name.endsWith("_proposal")) {
          return execution && member ? proposalExecutionDenial(execution, member.member) : "Execution membership is missing.";
        }
        if (exec.name === "update_goal" && isRecord(exec.arguments)
          && ["complete", "edit"].includes(String(exec.arguments.action))
          && state.listReviews(binding.sessionId).some(review => ["previewing", "ready", "applying", "reconcile"].includes(review.state))) {
          return "Resolve the pending owner proposal before completing or editing this goal.";
        }
        return undefined;
      });
    }
    attached.add(agent.id);
  };

  const guardUnbound = (agent: ProductAgent): void => {
    if (unboundGuards.has(agent.id) || !agent.ctx.systemPrompt) return;
    unboundGuards.set(agent.id, agent.ctx.systemPrompt.section({
      name: "spec2gds:unbound-session",
      order: 150,
      complete: true,
      text: UNBOUND_SOURCE_PROMPT + (config.interactiveForms ? `\n\n${SOURCE_CREATION_PROMPT}` : ""),
    }));
  };

  const agentPreset = (agent: ProductAgent): "focused" | "goal" | "orchestrated" => {
    const selected = agent.session?.header.agentPreset;
    return selected === "goal" || selected === "orchestrated" ? selected : "focused";
  };

  // DSH deliberately leaves turn budgeting to product policy. Spec work is
  // narrow: one context read and one proposal call normally settle in two or
  // three model steps. A visible user-question call earns exactly
  // one additional focused step so context -> question -> proposal -> final
  // can finish without weakening the ordinary runaway-tool boundary.
  ctx.on("agent/pre-step", async (
    { agent, turn, step }: { agent: ProductAgent; turn: number; step: number },
    next: () => Promise<unknown>,
  ) => {
    await ready;
    if (legacyExecutions.has(String(agent.id))) return { kind: "reject" };
    if (!state.getBinding(String(agent.id)) && !ctx.eventSystems.membership(SessionId(agent.id)) && agentPreset(agent) === "goal" && step === 1) {
      const goal = ctx.goals.get(agent as unknown as Agent);
      if (goal?.phase === "active") ctx.goals.pause(agent as unknown as Agent, goal);
    }
    const limit = maxModelStepsForTurn(
      agentPreset(agent),
      config.maxStepsPerTurn,
      clarifiedTurns.get(String(agent.id)) === turn,
    );
    return step > limit
      ? { kind: "reject" }
      : next();
  });
  ctx.on("agent/request", async (
    _payload: { agent: ProductAgent; turn: number; step: number },
    next: () => Promise<Record<string, unknown>>,
  ) => ({ ...await next(), maxTokens: config.maxOutputTokens }));

  ctx.on("agent/created", async ({ agent }: { agent: ProductAgent }) => {
    await ready;
    let binding = state.getBinding(String(agent.id));
    const parentSession = agent.session?.header.parentSession;
    const membership = ctx.eventSystems.membership(SessionId(agent.id));
    if (!binding && membership && !membership.primary) {
      const parentBinding = state.getBinding(String(membership.conversationId));
      if (!parentBinding) throw new Error("Event agent has no immutable owner binding.");
      await attach(agent, parentBinding);
      return;
    }
    if (!binding && parentSession) throw new Error("One-shot delegated agents are unavailable; use the event-system roster.");
    const serialized = process.env.SPEC2GDS_BINDING_JSON;
    if (!binding && serialized) {
      let input: BindingInput;
      try { input = bindingInput(JSON.parse(serialized) as Record<string, unknown>); }
      catch (error) { throw new Error(`Invalid SPEC2GDS_BINDING_JSON: ${error instanceof Error ? error.message : String(error)}`); }
      const validated = await owners.validateBinding(input);
      const temporary = {
        sessionId: String(agent.id), status: "creating" as const, preset: input.preset ?? "focused", domain: input.domain, ownerUrl: validated.ownerUrl,
        documentId: input.documentId, scope: input.domain === "circuit" ? "document" as const : input.scope ?? "document",
        entityKind: input.entityKind ?? null, entityId: input.entityId ?? null, title: input.title ?? input.documentId,
        workspaceKey: "", workspaceTitle: "", workspacePath: "", archived: false, createdAt: "", updatedAt: "",
        workspaceDomain: input.domain, workspaceOwnerUrl: validated.ownerUrl, workspaceDocumentId: input.documentId,
      };
      const workspace = workspaceDescriptor(config.scratchRoot, input, validated.ownerUrl, validated.context,
        await owners.circuitSourceBinding(temporary));
      await mkdir(workspace.path, { recursive: true, mode: 0o700 });
      state.createBinding(String(agent.id), { ...input, ownerUrl: validated.ownerUrl,
        workspaceKey: workspace.key, workspaceTitle: workspace.title, workspacePath: workspace.path,
        workspaceDomain: workspace.domain, workspaceOwnerUrl: workspace.ownerUrl, workspaceDocumentId: workspace.documentId });
      binding = state.activateBinding(String(agent.id));
    }
    if (!binding) (agent as unknown as Agent).ctx.tools.guard(exec =>
      ["create_goal", "update_goal"].includes(exec.name) && !state.getBinding(String(agent.id))
        ? "Bind this conversation to a design before using goal controls." : undefined);
    if (binding) await attach(agent, binding);
    else guardUnbound(agent);
    if (config.interactiveForms && !parentSession) {
      registerSourceCreationTool(agent, creations, () => ({
        sourceSessionId: String(agent.id), originalRequest: latestUserRequests.get(String(agent.id)) ?? "",
        preset: binding?.preset ?? agentPreset(agent), preferredOwner: binding?.domain === "spec" ? binding.ownerUrl : undefined,
      }));
    }
  });
  ctx.on("session/event", (session: { id: unknown }, event: { type: string; data?: any }) => {
    if (event.type === "tool/call" && event.data?.name === "ask_user_question"
      && Number.isSafeInteger(event.data?.turn)) {
      clarifiedTurns.set(String(session.id), Number(event.data.turn));
    }
  });
  ctx.on("session/event", (session: { id: unknown }, event: { type: string; data?: any }) => {
    if (event.type !== "user/message" || event.data?.source?.kind !== "user") return;
    const objective = Array.isArray(event.data.content)
      ? event.data.content.filter((item: unknown) => isRecord(item) && item.type === "text" && typeof item.text === "string")
        .map((item: Record<string, unknown>) => String(item.text)).join("\n").trim()
      : "";
    if (objective) latestUserRequests.set(String(session.id), objective);
  });

  ctx.on("agent/disposed", ({ agent }: { agent: ProductAgent }) => {
    attached.delete(String(agent.id));
    clarifiedTurns.delete(String(agent.id));
    latestUserRequests.delete(String(agent.id));
    unboundGuards.get(String(agent.id))?.();
    unboundGuards.delete(String(agent.id));
  });

  async function reserve(input: BindingInput, requestedId?: string): Promise<{ binding: SessionBinding; workspace: WorkspaceDescriptor }> {
    await ready;
    let validated: Awaited<ReturnType<OwnerClients["validateBinding"]>>;
    try { validated = await owners.validateBinding(input); }
    catch (error) {
      if (error instanceof OwnerError) throw error;
      throw new HttpError(400, error instanceof Error ? error.message : String(error));
    }
    const sessionId = requestedId?.trim() || randomUUID();
    if (state.getBinding(sessionId)) throw new HttpError(409, "This session already has a document binding.");
    const temporary = {
      sessionId, status: "creating" as const, preset: input.preset ?? "focused", domain: input.domain, ownerUrl: validated.ownerUrl,
      documentId: input.documentId, scope: input.domain === "circuit" ? "document" as const : input.scope ?? "document",
      entityKind: input.entityKind ?? null, entityId: input.entityId ?? null, title: input.title ?? input.documentId,
      workspaceKey: "", workspaceTitle: "", workspacePath: "", archived: false, createdAt: "", updatedAt: "",
      workspaceDomain: input.domain, workspaceOwnerUrl: validated.ownerUrl, workspaceDocumentId: input.documentId,
    };
    const workspace = workspaceDescriptor(config.scratchRoot, input, validated.ownerUrl, validated.context,
      await owners.circuitSourceBinding(temporary));
    await mkdir(workspace.path, { recursive: true, mode: 0o700 });
    const binding = state.createBinding(sessionId, { ...input, ownerUrl: validated.ownerUrl,
      ownerDocumentKey: typeof validated.context.owner_document_key === "string" ? validated.context.owner_document_key : input.ownerDocumentKey,
      workspaceKey: workspace.key, workspaceTitle: workspace.title, workspacePath: workspace.path,
      workspaceDomain: workspace.domain, workspaceOwnerUrl: workspace.ownerUrl, workspaceDocumentId: workspace.documentId });
    return { binding, workspace };
  }

  async function activate(sessionId: string): Promise<SessionBinding> {
    const binding = state.getBinding(sessionId);
    if (!binding) throw new HttpError(404, "Unknown reserved binding.");
    const active = binding.status === "active" ? binding : state.activateBinding(sessionId);
    const agent = ctx.agents.get(SessionId(sessionId));
    if (agent) await attach(agent, active);
    return active;
  }

  async function createSource(body: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (typeof body.serviceBaseUrl !== "string" || typeof body.documentId !== "string" || typeof body.title !== "string") {
      throw new HttpError(400, "serviceBaseUrl, documentId, and title are required.");
    }
    if (body.creationRequestId !== undefined) {
      if (body.domain !== "spec" || typeof body.creationRequestId !== "string") throw new HttpError(400, "A creation request must target a Spec document.");
      return creations.create(body.creationRequestId, { serviceBaseUrl: body.serviceBaseUrl, documentId: body.documentId, title: body.title });
    }
    const input = bindingInput({ ...body, scope: "document" });
    const documentId = input.documentId;
    const title = body.title.trim();
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(documentId) || !title) throw new HttpError(400, "Document ID or title is invalid.");
    owners.normalize(input);
    if (input.domain === "spec") {
      const snapshot = await owners.createSpec(input.serviceBaseUrl, specDestination(config.specDocumentRoot, documentId), documentId, title);
      if (typeof snapshot.owner_document_key === "string") input.ownerDocumentKey = snapshot.owner_document_key;
    }
    else await owners.createCircuit(input.serviceBaseUrl, documentId, title);
    const result = await reserve({ ...input, title });
    return { session: result.binding, workspace: result.workspace };
  }

  async function reviewAction(binding: SessionBinding, review: ProposalReview, action: string): Promise<ProposalReview> {
    if (artifactDigest(review.artifact) !== review.artifactDigest) throw new HttpError(409, "Stored proposal content failed its integrity check.");
    if (action === "discard") {
      if (binding.domain === "spec" && (await owners.specPolicy(binding.ownerUrl)).submissions) {
        try { await owners.rejectSpec(binding, review.proposalId); }
        catch (error) { if (!(error instanceof OwnerError && error.status === 404)) throw error; }
      }
      return state.transitionReview(binding.sessionId, review.proposalId, ["ready", "rejected", "stale", "reconcile"], "discarded");
    }
    if (binding.domain === "spec" && action === "apply") {
      if (review.state === "reconcile") {
        try {
          const policy = await owners.specPolicy(binding.ownerUrl);
          if (policy.submissions) {
            const receipt = await owners.specSubmission(binding, review.proposalId);
            if (isRecord(receipt.artifact) && artifactDigest(receipt.artifact) === review.artifactDigest
                && receipt.state === "applied" && isRecord(receipt.owner_result)) {
              return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "applied", { error: null, ownerResult: receipt.owner_result });
            }
          } else {
            const found = findSpecChange(await owners.specChanges(binding), review.proposalId);
            if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "applied", {
              error: null, ownerResult: { ...found, source_revision_hash: found.result_source_revision_hash, application_mode: "review" },
            });
          }
        }
        catch { /* Retry the idempotent apply below. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const policy = await owners.specPolicy(binding.ownerUrl);
        if (!policy.submissions) {
          const current = await owners.context(binding);
          if (current.source_revision_hash !== review.baseRevision) {
            const detail = "The Spec source revision changed.";
            const normalized = proposalError(binding, review.proposalId, "STALE_REVISION", detail, true);
            logProposalFailure(binding, normalized, review.proposalId);
            return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", {
              diagnostics: detail, error: normalized,
            });
          }
        }
        let result;
        if (policy.submissions) {
          await owners.stageSpec(binding, review.artifact);
          result = await owners.approveSpec(binding, review.proposalId);
        } else result = await owners.applySpec(binding, review.artifact);
        if (result.status !== "applied") throw new OwnerError(502, "The owner did not confirm a saved change.", true);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "applied", { error: null, ownerResult: result });
      } catch (error) {
        const normalized = errorFromException(binding, review.proposalId, error);
        logProposalFailure(binding, normalized, review.proposalId);
        if (error instanceof OwnerError && error.uncertain) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "reconcile", { diagnostics: error.detail, error: normalized });
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], normalized.error_code === "STALE_REVISION" ? "stale" : "rejected", { diagnostics: normalized.owner_diagnostics, error: normalized });
      }
    }
    if (binding.domain === "circuit" && action === "send") {
      if (review.state === "reconcile") {
        try { const found = findProposal(await owners.circuitProposals(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "sent", { error: null, ownerResult: found }); }
        catch { /* Retry with the persisted identity below. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.revision !== review.baseRevision) {
          const detail = "The Circuit revision changed.";
          const normalized = proposalError(binding, review.proposalId, "STALE_REVISION", detail, true);
          logProposalFailure(binding, normalized, review.proposalId);
          return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", {
            diagnostics: detail, error: normalized,
          });
        }
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { error: null, ownerResult: await owners.sendCircuit(binding, review.artifact) });
      } catch (error) {
        try { const found = findProposal(await owners.circuitProposals(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { error: null, ownerResult: found }); }
        catch { /* Preserve the original outcome. */ }
        const uncertain = error instanceof OwnerError && (error.uncertain || error.status === 409);
        const normalized = errorFromException(binding, review.proposalId, error);
        logProposalFailure(binding, normalized, review.proposalId);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], uncertain ? "reconcile" : "rejected", { diagnostics: normalized.owner_diagnostics, error: normalized });
      }
    }
    throw new HttpError(400, "Action does not match this review domain.");
  }

  async function publishPreparedReview(binding: SessionBinding, review: ProposalReview): Promise<void> {
    if (binding.preset === "focused") return;
    const id = SessionId(binding.sessionId);
    const execution = ctx.eventSystems.get(id);
    if (!execution) throw new Error("Proposal has no execution system.");
    const prepared = execution.events.find(event => event.type === "review.prepared"
      && isRecord(event.payload) && event.payload.proposal_id === review.proposalId);
    const cause = execution.events.findLast(event => event.type === "review.ready");
    try {
      if (!prepared) await ctx.eventSystems.publishHost(id, { type: "review.prepared", payload: { proposal_id: review.proposalId },
        producer: "owner", dedupeKey: `prepared:${review.proposalId}`, ...(cause ? { causation: cause.id } : {}) });
    } finally {
      if (binding.preset === "goal" && review.state === "ready") {
        const agent = ctx.agents.get(id);
        if (agent && !ctx.eventSystems.get(id)?.waits?.some(wait => wait.state === "waiting" && wait.kind === "review" && wait.matchValue === review.proposalId)) {
          await ctx.eventSystems.wait(agent as unknown as Agent, { kind: "review", reason: "Owner review pending",
            eventType: "review.applied", matchKey: "proposal_id", matchValue: review.proposalId });
        }
      }
    }
    if (review.state === "applied") await settleReviewedExecution(binding, review);
  }

  async function settleReviewedExecution(binding: SessionBinding, review: ProposalReview): Promise<void> {
    if (binding.preset === "focused" || !["applied", "sent", "discarded"].includes(review.state)) return;
    const prepared = ctx.eventSystems.get(SessionId(binding.sessionId))?.events.findLast(event => event.type === "review.prepared"
      && isRecord(event.payload) && event.payload.proposal_id === review.proposalId);
    await ctx.eventSystems.publishHost(SessionId(binding.sessionId), {
      ...(prepared ? { causation: prepared.id } : {}),
      type: review.state === "discarded" ? "review.discarded" : "review.applied",
      payload: { proposal_id: review.proposalId }, producer: "owner", dedupeKey: `${review.state}:${review.proposalId}`,
    });
  }

  function executionFor(sessionId: string): EventSystemSnapshot {
    const execution = ctx.eventSystems.get(SessionId(sessionId));
    if (!execution) throw new HttpError(404, "This conversation has no execution system.");
    return execution;
  }

  ctx.inject(["webServer", "connection"], (webCtx) => {
    webCtx.effect(() => webCtx.webServer.register({ kind: "prefix", path: "/spec2gds-api", handler: async (request: any, response: any) => {
      try {
        await ready;
        if (!sameOrigin(request)) throw new HttpError(403, "Origin refused.");
        const requestUrl = new URL(request.url ?? "/", "http://localhost");
        const path = requestUrl.pathname;
        if (path === "/spec2gds-api/capabilities" && request.method === "GET") return writeJson(response, 200, { model: config.model, provider: config.provider, owners: await owners.capabilities() });
        const sourceRequestMatch = path.match(/^\/spec2gds-api\/source-requests\/([^/]+)(?:\/(cancel|continued))?$/);
        if (sourceRequestMatch) {
          const requestId = decodeURIComponent(sourceRequestMatch[1]!);
          if (!sourceRequestMatch[2] && request.method === "GET") return writeJson(response, 200, { creation_request: await creations.present(creations.get(requestId)) });
          if (request.method === "POST" && sourceRequestMatch[2]) {
            await readBody(request);
            const updated = sourceRequestMatch[2] === "cancel" ? creations.cancel(requestId) : creations.continued(requestId);
            return writeJson(response, 200, { creation_request: await creations.present(updated) });
          }
        }
        const proposalInputMatch = path.match(/^\/spec2gds-api\/proposal-inputs\/([^/]+)\/confirm$/);
        if (proposalInputMatch && request.method === "POST") {
          const body = await readBody(request);
          if (!body.values || typeof body.values !== "object" || Array.isArray(body.values)) throw new HttpError(400, "values must be an object.");
          try { state.confirmProposalInput(decodeURIComponent(proposalInputMatch[1]!), body.values as Record<string, string>); }
          catch (error) { throw new HttpError(422, error instanceof Error ? error.message : String(error)); }
          return writeJson(response, 200, { confirmed: true });
        }
        if (path === "/spec2gds-api/services/connect" && request.method === "POST") {
          const body = await readBody(request);
          if (body.domain !== "spec" && body.domain !== "circuit") throw new HttpError(400, "domain must be spec or circuit.");
          if (typeof body.serviceBaseUrl !== "string") throw new HttpError(400, "serviceBaseUrl is required.");
          return writeJson(response, 200, { service: await owners.connect(body.domain, body.serviceBaseUrl) });
        }
        if (path === "/spec2gds-api/targets" && request.method === "GET") {
          const domain = requestUrl.searchParams.get("domain");
          const serviceBaseUrl = requestUrl.searchParams.get("service_base_url") ?? "";
          if (domain !== "spec" && domain !== "circuit") throw new HttpError(400, "domain must be spec or circuit.");
          return writeJson(response, 200, await owners.targets(domain, serviceBaseUrl));
        }
        if (path === "/spec2gds-api/sources/create" && request.method === "POST") {
          const body = await readBody(request);
          return writeJson(response, 201, await createSource(body));
        }
        if (path === "/spec2gds-api/workspaces" && request.method === "GET") {
          const workspaces = [...new Map(state.listBindings().map(binding => [binding.workspaceKey, {
            key: binding.workspaceKey, title: binding.workspaceTitle, path: binding.workspacePath,
            domain: binding.workspaceDomain, ownerUrl: binding.workspaceOwnerUrl, documentId: binding.workspaceDocumentId,
          }])).values()];
          return writeJson(response, 200, { workspaces });
        }
        if (path === "/spec2gds-api/bindings/reserve" && request.method === "POST") {
          const body = await readBody(request);
          const result = await reserve(bindingInput(body), typeof body.sessionId === "string" ? body.sessionId : undefined);
          return writeJson(response, 201, { session: result.binding, workspace: result.workspace });
        }
        const bindingMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)(?:\/(activate|abandon|reviews|execution))?$/);
        if (bindingMatch) {
          const sessionId = decodeURIComponent(bindingMatch[1]!);
          const resource = bindingMatch[2];
          if (!resource && request.method === "GET") {
            const binding = state.getBinding(sessionId);
            if (!binding) throw new HttpError(404, "Unknown binding.");
            return writeJson(response, 200, { session: binding });
          }
          if (resource === "activate" && request.method === "POST") return writeJson(response, 200, { session: await activate(sessionId) });
          if (resource === "abandon" && request.method === "POST") { if (state.getBinding(sessionId)?.status === "creating") state.deleteBinding(sessionId); return writeJson(response, 200, { abandoned: true }); }
          if (resource === "reviews" && request.method === "GET") {
            const binding = state.getBinding(sessionId);
            if (binding?.domain === "spec") {
              for (const review of state.listReviews(sessionId).filter(item => ["ready", "reconcile"].includes(item.state))) {
                try {
                  const receipt = await owners.specSubmission(binding, review.proposalId);
                  if (!isRecord(receipt.artifact) || artifactDigest(receipt.artifact) !== review.artifactDigest) continue;
                  if (receipt.state === "applied" && isRecord(receipt.owner_result)) {
                    const updated = state.transitionReview(sessionId, review.proposalId, [review.state], "applied", { error: null, ownerResult: receipt.owner_result });
                    await settleReviewedExecution(binding, updated);
                  } else if (receipt.state === "discarded") {
                    const updated = state.transitionReview(sessionId, review.proposalId, [review.state], "discarded");
                    await settleReviewedExecution(binding, updated);
                  }
                } catch { /* Keep uncertain results visible while the bound owner is offline. */ }
              }
            }
            return writeJson(response, 200, { reviews: state.listReviews(sessionId).map(publicReview) });
          }
          if (resource === "execution" && request.method === "GET") {
            const binding = state.getBinding(sessionId);
            if (!binding) throw new HttpError(404, "Unknown binding.");
            return writeJson(response, 200, { execution: ctx.eventSystems.get(SessionId(sessionId)) ?? null,
              legacy: legacyExecutions.has(sessionId), monitorSuggestion: {
                url: binding.domain === "spec" ? `${binding.ownerUrl}/assistant/context/document?${new URLSearchParams({ document_id: binding.documentId, ...(binding.ownerDocumentKey ? { owner_document_key: binding.ownerDocumentKey } : {}) })}` : `${binding.ownerUrl}/documents/${encodeURIComponent(binding.documentId)}`,
                pointer: binding.domain === "spec" ? "/source_revision_hash" : "/revision" }, sources: ctx.eventHttpSources.list(SessionId(sessionId)),
              goal: ctx.agents.get(SessionId(sessionId)) ? ctx.goals.get(ctx.agents.get(SessionId(sessionId)) as unknown as Agent) : null });
          }
        }
        const sourceMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)\/execution\/(sources|answers)$/);
        if (sourceMatch && request.method === "POST") {
          const id = decodeURIComponent(sourceMatch[1]!);
          const binding = state.getBinding(id);
          if (!binding || binding.preset === "focused") throw new HttpError(404, "This binding has no event execution.");
          const body = await readBody(request);
          try {
            if (sourceMatch[2] === "answers") {
              if (!Number.isSafeInteger(body.revision) || typeof body.waitId !== "string" || typeof body.answer !== "string") throw new Error("Answer requires revision, waitId, and answer.");
              await ctx.eventSystems.answerWait(SessionId(id), Number(body.revision), body.waitId as Parameters<EventSystemService["answerWait"]>[2], body.answer);
            } else if (body.action === "add") {
              if (!isRecord(body.definition) || typeof body.definition.url !== "string" || body.definition.eventType !== "source.changed") throw new Error("Source definition must use the approved source.changed event.");
              const url = new URL(body.definition.url), owner = new URL(binding.ownerUrl);
              const prefix = owner.pathname.replace(/\/$/, "");
              if (url.origin !== owner.origin || (prefix && url.pathname !== prefix && !url.pathname.startsWith(`${prefix}/`))) throw new Error("HTTP source must monitor this conversation's bound owner service.");
              await ctx.eventHttpSources.add(SessionId(id), body.definition as unknown as HttpSourceInput);
            } else if (body.action === "enable" || body.action === "disable") {
              if (typeof body.sourceId !== "string" || !Number.isSafeInteger(body.revision)) throw new Error("Source controls require sourceId and observed revision.");
              await ctx.eventHttpSources.control(SessionId(id), body.sourceId as HttpSourceId, Number(body.revision), body.action === "enable");
            } else throw new Error("Unknown HTTP source action.");
            return writeJson(response, 200, { execution: executionFor(id), sources: ctx.eventHttpSources.list(SessionId(id)) });
          } catch (error) { throw new HttpError(409, error instanceof Error ? error.message : String(error)); }
        }
        const executionActionMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)\/execution\/actions$/);
        if (executionActionMatch && request.method === "POST") {
          const sessionId = decodeURIComponent(executionActionMatch[1]!);
          const binding = state.getBinding(sessionId);
          if (!binding || binding.preset === "focused") throw new HttpError(404, "This binding has no execution controls.");
          const body = await readBody(request);
          if (!Number.isSafeInteger(body.revision)) throw new HttpError(400, "revision must identify the observed execution state.");
          const action = body.action;
          if (action !== "pause" && action !== "resume" && action !== "stop" && action !== "retry") throw new HttpError(400, "Unknown execution action.");
          if (action === "resume" && state.listReviews(sessionId).some(review => ["previewing", "ready", "applying", "reconcile"].includes(review.state))) {
            throw new HttpError(409, "Resolve pending owner review before resuming work.");
          }
          try {
            const next = action === "retry"
              ? await ctx.eventSystems.retry(SessionId(sessionId), Number(body.revision), String(body.deliveryId) as Parameters<EventSystemService["retry"]>[2], body.acknowledgeUncertainty === true)
              : await ctx.eventSystems.control(SessionId(sessionId), Number(body.revision), action);
            const agent = ctx.agents.get(SessionId(sessionId));
            const goal = agent && binding.preset === "goal" ? ctx.goals.get(agent as unknown as Agent) : undefined;
            if (agent && goal && goal.phase !== "complete") {
              if (action === "resume" && !(goal.phase === "active" && goal.activation === "armed")
                && !next.waits?.some(wait => wait.member === next.definition.primary && wait.state === "waiting")) ctx.goals.resume(agent as unknown as Agent, goal);
              else if (action !== "retry" && goal.phase === "active") ctx.goals.pause(agent as unknown as Agent, goal);
            }
            return writeJson(response, 200, { execution: next });
          } catch (error) { throw new HttpError(409, error instanceof Error ? error.message : String(error)); }
        }
        const reviewMatch = path.match(/^\/spec2gds-api\/reviews\/([^/]+)\/actions$/);
        if (reviewMatch && request.method === "POST") {
          const proposalId = decodeURIComponent(reviewMatch[1]!);
          const binding = state.listBindings(true).find(item => state.getReview(item.sessionId, proposalId));
          if (!binding) throw new HttpError(404, "Unknown proposal review.");
          const action = String((await readBody(request)).action ?? "");
          if (binding.preset !== "focused" && (action === "apply" || action === "send")) {
            const execution = executionFor(binding.sessionId);
            if (execution.status !== "active" && !(execution.status === "paused" && execution.reason === "Owner review pending")) {
              throw new HttpError(409, `Execution status ${execution.status} does not permit owner mutation.`);
            }
          }
          const updated = await reviewAction(binding, state.getReview(binding.sessionId, proposalId)!, action);
          await settleReviewedExecution(binding, updated);
          return writeJson(response, 200, { review: publicReview(updated) });
        }
        throw new HttpError(404, "Unknown spec2gds endpoint.");
      } catch (error) {
        if (response.headersSent) return response.destroy();
        if (error instanceof SourceCreationError) return writeJson(response, error.status, { error: error.message });
        if (error instanceof HttpError || error instanceof OwnerError) return writeJson(response, error.status, { error: error.message, detail: error.detail });
        return writeJson(response, 500, { error: error instanceof Error ? error.message : String(error) });
      }
    } }));

    webCtx.effect(() => webCtx.webServer.register({ kind: "exact", path: "/launch", handler: (_request: any, response: any) => {
      response.writeHead(303, {
        Location: authenticatedLaunchLocation(webCtx.connection, undefined, true),
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
      });
      response.end();
    } }));
    for (const route of ["/launch/spec", "/launch/spec-document", "/launch/circuit"]) {
      webCtx.effect(() => webCtx.webServer.register({ kind: "exact", path: route, handler: async (request: any, response: any) => {
        try {
          const url = new URL(request.url ?? route, "http://localhost");
          const result = await reserve({ domain: route === "/launch/circuit" ? "circuit" : "spec", serviceBaseUrl: url.searchParams.get("service_base_url") ?? "", documentId: url.searchParams.get("document_id") ?? "", ownerDocumentKey: url.searchParams.get("owner_document_key") ?? undefined, scope: route === "/launch/spec" ? "entity" : "document", entityKind: url.searchParams.get("entity_kind") ?? undefined, entityId: url.searchParams.get("entity_id") ?? undefined });
          response.writeHead(303, {
            Location: authenticatedLaunchLocation(webCtx.connection, result.binding.sessionId),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
          });
          response.end();
        } catch (error) {
          const status = error instanceof OwnerError || error instanceof HttpError ? error.status : 400;
          writeJson(response, status, { error: error instanceof Error ? error.message : String(error) });
        }
      } }));
    }
    webCtx.effect(() => webCtx.webServer.register({ kind: "exact", path: "/healthz", handler: (_request: any, response: any) => writeJson(response, 200, { status: "ok" }) }));
    webCtx.effect(() => webCtx.webServer.register({ kind: "exact", path: "/readyz", handler: async (_request: any, response: any) => {
      try { await ready; writeJson(response, 200, { status: "ready", modelConfigured: Boolean(process.env.OPENAI_API_KEY) }); }
      catch (error) { writeJson(response, 503, { status: "not_ready", error: error instanceof Error ? error.message : String(error) }); }
    } }));
  });
  ctx.on("dispose", () => { state.close(); });
}
