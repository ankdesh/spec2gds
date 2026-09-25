import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import z from "@deepseek-ai/schemastery";
import { SessionId } from "@deepseek-ai/dsh-session";
import { OwnerClients, OwnerError } from "./owner-clients.js";
import { errorFromException, logProposalFailure, proposalError, publicReview } from "./proposal-presentation.js";
import { artifactDigest, ProductState } from "./state.js";
import { findProposal, findSpecChange, registerDomainTools } from "./tools.js";
import type { BindingInput, ProposalReview, ServiceConfig, SessionBinding, WorkspaceDescriptor } from "./types.js";
import { isRecord } from "./types.js";
import { workspaceDescriptor } from "./workspaces.js";

export const name = "spec2gds-harness-assistant";
export const inject = ["agents", "sessionPersistence", "promptCatalog", "promptCatalogYaml", "sWorkflow", "sWorkflowYaml"];
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
type SWorkflowService = {
  catalog(service?: string, preset?: "focused" | "goal" | "orchestrated"): {
    definitions: readonly { value: { metadata: { id: string; version: string } } }[];
    adapters: readonly { value: { metadata: { id: string; version: string } } }[];
  };
  get(agent: ProductAgent): null | {
    runId: string;
    revision: number;
    status: string;
    preset: "focused" | "goal" | "orchestrated";
    budget: { maxChildren: number; maxConcurrency: number; maxDelegationDepth: number };
    draft?: unknown;
  };
  start(agent: ProductAgent, request: Record<string, unknown>): unknown;
  checkpoint(
    agent: ProductAgent,
    ref: { runId: string; revision: number },
    stepId: string,
    note: string,
    usage?: { children?: number },
  ): unknown;
  updateDraft(agent: ProductAgent, ref: { runId: string; revision: number }, draft: unknown, summary: string): unknown;
  requestCompletion(agent: ProductAgent, ref: { runId: string; revision: number }, prompt: string): unknown;
  answerInput(agent: ProductAgent, ref: { runId: string; revision: number }, answer: string): unknown;
  approveCompletion(agent: ProductAgent, ref: { runId: string; revision: number }): unknown;
  pause(agent: ProductAgent, ref: { runId: string; revision: number }): unknown;
  resume(agent: ProductAgent, ref: { runId: string; revision: number }): unknown;
  cancel(agent: ProductAgent, ref: { runId: string; revision: number }): unknown;
  raiseBudgets(agent: ProductAgent, ref: { runId: string; revision: number }, patch: Record<string, number>): unknown;
  seal(): void;
};
type AppContext = {
  agents: { get(id: unknown): ProductAgent | undefined };
  sessionPersistence: { list(): Promise<Array<{ header: { id: string } }>> };
  promptCatalog: PromptCatalogService;
  sWorkflow: SWorkflowService;
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
  const attached = new Set<string>();
  const unboundGuards = new Map<string, () => void>();
  const delegatedParents = new Map<string, string>();
  const activeDelegations = new Map<string, Set<string>>();
  const clarifiedTurns = new Map<string, number>();
  const latestUserRequests = new Map<string, string>();
  const ready = (async () => {
    await mkdir(config.scratchRoot, { recursive: true, mode: 0o700 });
    await mkdir(config.specDocumentRoot, { recursive: true, mode: 0o700 });
    const stored = new Set((await ctx.sessionPersistence.list()).map(item => String(item.header.id)));
    for (const binding of state.listCreatingBindings()) stored.has(binding.sessionId) ? state.activateBinding(binding.sessionId) : state.deleteBinding(binding.sessionId);
    state.recoverInterruptedReviews();
    for (const domain of ["spec", "circuit"] as const) {
      ctx.promptCatalog.get({ id: `spec2gds.${domain}`, version: "1.0.0" });
      const catalog = ctx.sWorkflow.catalog(domain);
      if (!catalog.definitions.some(entry => entry.value.metadata.id === "prepare-reviewed-change" && entry.value.metadata.version === "1.0.0")) {
        throw new Error(`Missing workflow prepare-reviewed-change@1.0.0 for ${domain}.`);
      }
      if (!catalog.adapters.some(entry => entry.value.metadata.id === `${domain}-editor` && entry.value.metadata.version === "1.0.0")) {
        throw new Error(`Missing service adapter ${domain}-editor@1.0.0.`);
      }
    }
    ctx.promptCatalog.seal();
    ctx.sWorkflow.seal();
  })();

  const attach = (agent: ProductAgent, binding: SessionBinding): void => {
    if (attached.has(agent.id)) return;
    unboundGuards.get(agent.id)?.();
    unboundGuards.delete(agent.id);
    owners.assertStoredBinding(binding);
    registerDomainTools(agent.ctx, binding, state, owners, ctx.promptCatalog, (review) => {
      if (binding.preset === "focused") return;
      try {
        const workflow = ctx.sWorkflow.get(agent);
        if (!workflow || workflow.status !== "active") return;
        const summary = typeof review.artifact.summary === "string" && review.artifact.summary.trim()
          ? review.artifact.summary
          : `Prepared ${review.domain} proposal ${review.proposalId}.`;
        ctx.sWorkflow.updateDraft(
          agent,
          { runId: workflow.runId, revision: workflow.revision },
          review.artifact,
          summary,
        );
      } catch (error) {
        console.error("Failed to synchronize the owner-previewed proposal into workflow draft state:", error);
      }
    }, () => latestUserRequests.get(binding.sessionId) ?? "", config.interactiveForms);
    attached.add(agent.id);
  };

  const guardUnbound = (agent: ProductAgent): void => {
    if (unboundGuards.has(agent.id) || !agent.ctx.systemPrompt) return;
    unboundGuards.set(agent.id, agent.ctx.systemPrompt.section({
      name: "spec2gds:unbound-session",
      order: 150,
      complete: true,
      text: `This conversation is not bound to a Spec Editor design source.
Do not answer questions about a document, component, design, or requested edit. Do not claim that work was completed and do not create a goal.
Tell the user to start a new conversation and choose a Spec Editor document or entity.`,
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
    if (!binding && parentSession) {
      const parentBinding = state.getBinding(String(parentSession));
      const parent = ctx.agents.get(SessionId(String(parentSession)));
      if (!parentBinding || !parent) throw new Error("Delegated assistant child has no live bound parent.");
      const workflow = ctx.sWorkflow.get(parent);
      const depth = agent.session?.header.delegationDepth ?? 0;
      if (!workflow || workflow.status !== "active" || workflow.preset !== "orchestrated") {
        throw new Error("Delegation requires an active orchestrated workflow.");
      }
      if (depth < 1 || depth > workflow.budget.maxDelegationDepth) {
        throw new Error("Delegation depth exceeds the workflow budget.");
      }
      const active = activeDelegations.get(String(parentSession)) ?? new Set<string>();
      if (active.size >= workflow.budget.maxConcurrency) {
        throw new Error("Workflow delegation concurrency budget is exhausted.");
      }
      ctx.sWorkflow.checkpoint(
        parent,
        { runId: workflow.runId, revision: workflow.revision },
        "delegation",
        `Started read-only delegated analysis ${String(agent.id)}.`,
        { children: 1 },
      );
      active.add(String(agent.id));
      activeDelegations.set(String(parentSession), active);
      delegatedParents.set(String(agent.id), String(parentSession));
      attach(agent, parentBinding);
      return;
    }
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
    if (binding) attach(agent, binding);
    else guardUnbound(agent);
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
    const binding = state.getBinding(String(session.id));
    if (!binding || binding.preset === "focused") return;
    if (!objective) return;
    queueMicrotask(() => { void (async () => {
      await ready;
      const agent = ctx.agents.get(session.id);
      if (!agent) return;
      const current = ctx.sWorkflow.get(agent);
      if (current?.status === "awaiting-user-input") {
        ctx.sWorkflow.answerInput(agent, { runId: current.runId, revision: current.revision }, objective);
        return;
      }
      if (current !== null) return;
      ctx.sWorkflow.start(agent, {
        definition: { id: "prepare-reviewed-change", version: "1.0.0" },
        adapter: { id: `${binding.domain}-editor`, version: "1.0.0" },
        preset: binding.preset,
        objective,
        contract: {
          binding: {
            domain: binding.domain,
            ownerUrl: binding.ownerUrl,
            documentId: binding.documentId,
            scope: binding.scope,
            ...(binding.entityKind ? { entityKind: binding.entityKind } : {}),
            ...(binding.entityId ? { entityId: binding.entityId } : {}),
          },
          review: {
            kind: binding.domain === "spec" ? "spec-proposal" : "circuit-proposal",
            mutationBoundary: "explicit-review-card-action",
          },
        },
      });
    })().catch(error => console.error("Failed to start bound workflow:", error)); });
  });
  ctx.on("agent/disposed", ({ agent }: { agent: ProductAgent }) => {
    const parentSession = delegatedParents.get(String(agent.id));
    if (parentSession) {
      const active = activeDelegations.get(parentSession);
      active?.delete(String(agent.id));
      if (active?.size === 0) activeDelegations.delete(parentSession);
      delegatedParents.delete(String(agent.id));
    }
    attached.delete(String(agent.id));
    clarifiedTurns.delete(String(agent.id));
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
      workspaceKey: workspace.key, workspaceTitle: workspace.title, workspacePath: workspace.path,
      workspaceDomain: workspace.domain, workspaceOwnerUrl: workspace.ownerUrl, workspaceDocumentId: workspace.documentId });
    return { binding, workspace };
  }

  async function activate(sessionId: string): Promise<SessionBinding> {
    const binding = state.getBinding(sessionId);
    if (!binding) throw new HttpError(404, "Unknown reserved binding.");
    const active = binding.status === "active" ? binding : state.activateBinding(sessionId);
    const agent = ctx.agents.get(SessionId(sessionId));
    if (agent) attach(agent, active);
    return active;
  }

  async function reviewAction(binding: SessionBinding, review: ProposalReview, action: string): Promise<ProposalReview> {
    if (artifactDigest(review.artifact) !== review.artifactDigest) throw new HttpError(409, "Stored proposal content failed its integrity check.");
    if (action === "discard") return state.transitionReview(binding.sessionId, review.proposalId, ["ready", "rejected", "stale", "reconcile"], "discarded");
    if (binding.domain === "spec" && action === "apply") {
      if (review.state === "reconcile") {
        try { const found = findSpecChange(await owners.specChanges(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "applied", { error: null, ownerResult: found }); }
        catch { /* Retry the idempotent apply below. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.source_revision_hash !== review.baseRevision) {
          const detail = "The Spec source revision changed.";
          const normalized = proposalError(binding, review.proposalId, "STALE_REVISION", detail, true);
          logProposalFailure(binding, normalized, review.proposalId);
          return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", {
            diagnostics: detail, error: normalized,
          });
        }
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "applied", { error: null, ownerResult: await owners.applySpec(binding, review.artifact) });
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

  function workflowFor(sessionId: string): { agent: ProductAgent; workflow: NonNullable<ReturnType<SWorkflowService["get"]>> } {
    const agent = ctx.agents.get(SessionId(sessionId));
    if (!agent) throw new HttpError(409, "The workflow session is not currently active.");
    const workflow = ctx.sWorkflow.get(agent);
    if (!workflow) throw new HttpError(404, "This session has no workflow.");
    return { agent, workflow };
  }

  function exactWorkflowRef(workflow: NonNullable<ReturnType<SWorkflowService["get"]>>, body: Record<string, unknown>) {
    if (body.runId !== workflow.runId || body.revision !== workflow.revision) {
      throw new HttpError(409, "The workflow changed; reload its exact run ID and revision.");
    }
    return { runId: workflow.runId, revision: workflow.revision };
  }

  function settleReviewedWorkflow(binding: SessionBinding, review: ProposalReview): void {
    if (binding.preset === "focused") return;
    const agent = ctx.agents.get(SessionId(binding.sessionId));
    if (!agent) return;
    let workflow = ctx.sWorkflow.get(agent);
    if (!workflow || ["complete", "cancelled"].includes(workflow.status)) return;
    if (review.state === "discarded") {
      ctx.sWorkflow.cancel(agent, { runId: workflow.runId, revision: workflow.revision });
      return;
    }
    if (review.state !== "applied" && review.state !== "sent") return;
    if (workflow.status === "active") {
      if (workflow.draft === undefined) {
        const summary = typeof review.artifact.summary === "string" && review.artifact.summary.trim()
          ? review.artifact.summary
          : `Prepared ${review.domain} proposal ${review.proposalId}.`;
        ctx.sWorkflow.updateDraft(
          agent,
          { runId: workflow.runId, revision: workflow.revision },
          review.artifact,
          summary,
        );
        workflow = ctx.sWorkflow.get(agent)!;
      }
      ctx.sWorkflow.requestCompletion(
        agent,
        { runId: workflow.runId, revision: workflow.revision },
        "The owner-backed proposal is ready for explicit approval.",
      );
      workflow = ctx.sWorkflow.get(agent)!;
    }
    if (workflow.status === "awaiting-user-completion") {
      ctx.sWorkflow.approveCompletion(agent, { runId: workflow.runId, revision: workflow.revision });
    }
  }

  ctx.inject(["webServer", "connection"], (webCtx) => {
    webCtx.effect(() => webCtx.webServer.register({ kind: "prefix", path: "/spec2gds-api", handler: async (request: any, response: any) => {
      try {
        await ready;
        if (!sameOrigin(request)) throw new HttpError(403, "Origin refused.");
        const requestUrl = new URL(request.url ?? "/", "http://localhost");
        const path = requestUrl.pathname;
        if (path === "/spec2gds-api/capabilities" && request.method === "GET") return writeJson(response, 200, { model: config.model, provider: config.provider, owners: await owners.capabilities() });
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
          if (body.domain !== "spec" && body.domain !== "circuit") throw new HttpError(400, "domain must be spec or circuit.");
          if (typeof body.serviceBaseUrl !== "string" || typeof body.documentId !== "string" || typeof body.title !== "string") {
            throw new HttpError(400, "serviceBaseUrl, documentId, and title are required.");
          }
          const documentId = body.documentId.trim();
          const title = body.title.trim();
          if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(documentId) || !title) throw new HttpError(400, "Document ID or title is invalid.");
          if (body.domain === "spec") {
            const destination = resolve(config.specDocumentRoot, `${documentId}.spec`);
            if (dirname(destination) !== config.specDocumentRoot) throw new HttpError(400, "Document path escaped the configured root.");
            await owners.createSpec(body.serviceBaseUrl, destination, documentId, title);
          } else await owners.createCircuit(body.serviceBaseUrl, documentId, title);
          const result = await reserve(bindingInput({ domain: body.domain, serviceBaseUrl: body.serviceBaseUrl,
            documentId, scope: "document", title, preset: body.preset }));
          return writeJson(response, 201, { session: result.binding, workspace: result.workspace });
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
        const bindingMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)(?:\/(activate|abandon|reviews|workflow))?$/);
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
          if (resource === "reviews" && request.method === "GET") return writeJson(response, 200, { reviews: state.listReviews(sessionId).map(publicReview) });
          if (resource === "workflow" && request.method === "GET") {
            const binding = state.getBinding(sessionId);
            if (!binding) throw new HttpError(404, "Unknown binding.");
            const agent = ctx.agents.get(SessionId(sessionId));
            return writeJson(response, 200, { workflow: agent ? ctx.sWorkflow.get(agent) : null });
          }
        }
        const workflowActionMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)\/workflow\/actions$/);
        if (workflowActionMatch && request.method === "POST") {
          const sessionId = decodeURIComponent(workflowActionMatch[1]!);
          const binding = state.getBinding(sessionId);
          if (!binding || binding.preset === "focused") throw new HttpError(404, "This binding has no long-running workflow controls.");
          const body = await readBody(request);
          const { agent, workflow } = workflowFor(sessionId);
          const ref = exactWorkflowRef(workflow, body);
          const action = String(body.action ?? "");
          let next: unknown;
          if (action === "pause") next = ctx.sWorkflow.pause(agent, ref);
          else if (action === "resume") next = ctx.sWorkflow.resume(agent, ref);
          else if (action === "cancel") next = ctx.sWorkflow.cancel(agent, ref);
          else if (action === "answer") {
            if (typeof body.answer !== "string") throw new HttpError(400, "answer is required.");
            next = ctx.sWorkflow.answerInput(agent, ref, body.answer);
          } else if (action === "approve") next = ctx.sWorkflow.approveCompletion(agent, ref);
          else if (action === "raise-budgets") {
            if (!isRecord(body.budget)) throw new HttpError(400, "budget must be an object.");
            const allowed = new Set(["maxRounds", "maxRequests", "maxTokens", "maxActiveMinutes", "maxChildren", "maxConcurrency", "maxDelegationDepth"]);
            const budget = Object.fromEntries(Object.entries(body.budget).map(([key, value]) => {
              if (!allowed.has(key)) throw new HttpError(400, `Unknown budget field ${key}.`);
              if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new HttpError(400, `budget.${key} must be an integer.`);
              return [key, value];
            }));
            next = ctx.sWorkflow.raiseBudgets(agent, ref, budget);
          } else throw new HttpError(400, "Unknown workflow action.");
          return writeJson(response, 200, { workflow: next });
        }
        const reviewMatch = path.match(/^\/spec2gds-api\/reviews\/([^/]+)\/actions$/);
        if (reviewMatch && request.method === "POST") {
          const proposalId = decodeURIComponent(reviewMatch[1]!);
          const binding = state.listBindings(true).find(item => state.getReview(item.sessionId, proposalId));
          if (!binding) throw new HttpError(404, "Unknown proposal review.");
          const action = String((await readBody(request)).action ?? "");
          if (binding.preset !== "focused" && (action === "apply" || action === "send")) {
            const { workflow } = workflowFor(binding.sessionId);
            if (workflow.status !== "active" && workflow.status !== "awaiting-user-completion") {
              throw new HttpError(409, `Workflow status ${workflow.status} does not permit owner mutation.`);
            }
          }
          const updated = await reviewAction(binding, state.getReview(binding.sessionId, proposalId)!, action);
          settleReviewedWorkflow(binding, updated);
          return writeJson(response, 200, { review: publicReview(updated) });
        }
        throw new HttpError(404, "Unknown spec2gds endpoint.");
      } catch (error) {
        if (response.headersSent) return response.destroy();
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
          const result = await reserve({ domain: route === "/launch/circuit" ? "circuit" : "spec", serviceBaseUrl: url.searchParams.get("service_base_url") ?? "", documentId: url.searchParams.get("document_id") ?? "", scope: route === "/launch/spec" ? "entity" : "document", entityKind: url.searchParams.get("entity_kind") ?? undefined, entityId: url.searchParams.get("entity_id") ?? undefined });
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
