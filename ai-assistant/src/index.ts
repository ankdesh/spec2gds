import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import z from "@deepseek-ai/schemastery";
import { SessionId } from "@deepseek-ai/dsh-session";
import { OwnerClients, OwnerError } from "./owner-clients.js";
import { artifactDigest, ProductState } from "./state.js";
import { findProposal, findSpecChange, registerDomainTools } from "./tools.js";
import type { BindingInput, ProposalReview, ServiceConfig, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

export const name = "spec2gds-harness-assistant";
export const inject = ["agents", "sessionPersistence"];
export const Config = z.object({
  provider: z.string().min(1).required(),
  model: z.string().min(1).required(),
  stateRoot: z.string().min(1).required(),
  scratchRoot: z.string().min(1).required(),
  specAllowlist: z.string().min(1).required(),
  circuitAllowlist: z.string().min(1).required(),
  requestTimeoutMs: z.number().min(100).max(300_000).required(),
});

type ProductAgent = {
  id: string;
  ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } };
};
type AppContext = {
  agents: { get(id: unknown): ProductAgent | undefined };
  sessionPersistence: { list(): Promise<Array<{ header: { id: string } }>> };
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
  if (typeof value.serviceBaseUrl !== "string" || !value.serviceBaseUrl.trim()) throw new HttpError(400, "serviceBaseUrl is required.");
  if (typeof value.documentId !== "string" || !value.documentId.trim()) throw new HttpError(400, "documentId is required.");
  const scope = value.domain === "circuit" ? "document" : value.scope === "entity" ? "entity" : "document";
  if (scope === "entity" && (typeof value.entityKind !== "string" || !value.entityKind.trim() || typeof value.entityId !== "string" || !value.entityId.trim())) {
    throw new HttpError(400, "Entity Spec bindings require entityKind and entityId.");
  }
  return {
    domain: value.domain,
    serviceBaseUrl: value.serviceBaseUrl.trim(),
    documentId: value.documentId.trim(),
    scope,
    entityKind: typeof value.entityKind === "string" ? value.entityKind.trim() : undefined,
    entityId: typeof value.entityId === "string" ? value.entityId.trim() : undefined,
    title: typeof value.title === "string" ? value.title.trim() : undefined,
  };
}

function publicReview(review: ProposalReview): Omit<ProposalReview, "artifactDigest"> {
  const { artifactDigest: _digest, ...value } = review;
  return value;
}

/**
 * Enter DSH through its one-time browser token while retaining product launch
 * data across the token exchange's deliberate redirect to a clean root URL.
 * A relative target prevents an untrusted Host header from receiving the
 * process credential; URL fragments are browser-local and survive the 303.
 */
export function authenticatedLaunchLocation(
  connection: { authenticatedUrl(baseUrl: string): string },
  sessionId: string,
  cwd: string,
): string {
  const authenticated = new URL(connection.authenticatedUrl("http://127.0.0.1"));
  const launch = new URLSearchParams({ spec2gds_session: sessionId, spec2gds_cwd: cwd });
  return `${authenticated.pathname}${authenticated.search}#${launch}`;
}

export function apply(ctx: AppContext, rawConfig: Record<string, unknown>): void {
  const config: ServiceConfig = {
    provider: String(rawConfig.provider), model: String(rawConfig.model), stateRoot: resolve(String(rawConfig.stateRoot)),
    scratchRoot: resolve(String(rawConfig.scratchRoot)), specAllowlist: splitAllowlist(String(rawConfig.specAllowlist)),
    circuitAllowlist: splitAllowlist(String(rawConfig.circuitAllowlist)), requestTimeoutMs: Number(rawConfig.requestTimeoutMs),
  };
  const state = new ProductState(resolve(config.stateRoot, "assistant.sqlite3"));
  const owners = new OwnerClients(config.specAllowlist, config.circuitAllowlist, config.requestTimeoutMs);
  const attached = new Set<string>();
  const ready = (async () => {
    await mkdir(config.scratchRoot, { recursive: true, mode: 0o700 });
    const stored = new Set((await ctx.sessionPersistence.list()).map(item => String(item.header.id)));
    for (const binding of state.listCreatingBindings()) stored.has(binding.sessionId) ? state.activateBinding(binding.sessionId) : state.deleteBinding(binding.sessionId);
    state.recoverInterruptedReviews();
  })();

  const attach = (agent: ProductAgent, binding: SessionBinding): void => {
    if (attached.has(agent.id)) return;
    owners.assertStoredBinding(binding);
    registerDomainTools(agent.ctx, binding, state, owners);
    attached.add(agent.id);
  };

  ctx.on("agent/created", async ({ agent }: { agent: ProductAgent }) => {
    await ready;
    let binding = state.getBinding(String(agent.id));
    const serialized = process.env.SPEC2GDS_BINDING_JSON;
    if (!binding && serialized) {
      let input: BindingInput;
      try { input = bindingInput(JSON.parse(serialized) as Record<string, unknown>); }
      catch (error) { throw new Error(`Invalid SPEC2GDS_BINDING_JSON: ${error instanceof Error ? error.message : String(error)}`); }
      const validated = await owners.validateBinding(input);
      state.createBinding(String(agent.id), { ...input, ownerUrl: validated.ownerUrl });
      binding = state.activateBinding(String(agent.id));
    }
    if (binding) attach(agent, binding);
  });
  ctx.on("agent/disposed", ({ agent }: { agent: ProductAgent }) => { attached.delete(String(agent.id)); });

  async function reserve(input: BindingInput, requestedId?: string): Promise<{ binding: SessionBinding; cwd: string }> {
    await ready;
    let validated: Awaited<ReturnType<OwnerClients["validateBinding"]>>;
    try { validated = await owners.validateBinding(input); }
    catch (error) {
      if (error instanceof OwnerError) throw error;
      throw new HttpError(400, error instanceof Error ? error.message : String(error));
    }
    const sessionId = requestedId?.trim() || randomUUID();
    if (state.getBinding(sessionId)) throw new HttpError(409, "This session already has a document binding.");
    const binding = state.createBinding(sessionId, { ...input, ownerUrl: validated.ownerUrl });
    const cwd = resolve(config.scratchRoot, sessionId);
    await mkdir(cwd, { recursive: true, mode: 0o700 });
    return { binding, cwd };
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
        try { const found = findSpecChange(await owners.specChanges(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "applied", { ownerResult: found }); }
        catch { /* Retry the idempotent apply below. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.source_revision_hash !== review.baseRevision) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", { diagnostics: "The Spec source revision changed." });
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "applied", { ownerResult: await owners.applySpec(binding, review.artifact) });
      } catch (error) {
        if (error instanceof OwnerError && error.uncertain) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "reconcile", { diagnostics: error.detail });
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], error instanceof OwnerError && error.status === 409 ? "stale" : "rejected", { diagnostics: error instanceof OwnerError ? error.detail : String(error) });
      }
    }
    if (binding.domain === "circuit" && action === "send") {
      if (review.state === "reconcile") {
        try { const found = findProposal(await owners.circuitProposals(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "sent", { ownerResult: found }); }
        catch { /* Retry with the persisted identity below. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.revision !== review.baseRevision) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", { diagnostics: "The Circuit revision changed." });
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { ownerResult: await owners.sendCircuit(binding, review.artifact) });
      } catch (error) {
        try { const found = findProposal(await owners.circuitProposals(binding), review.proposalId); if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { ownerResult: found }); }
        catch { /* Preserve the original outcome. */ }
        const uncertain = error instanceof OwnerError && (error.uncertain || error.status === 409);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], uncertain ? "reconcile" : "rejected", { diagnostics: error instanceof OwnerError ? error.detail : String(error) });
      }
    }
    throw new HttpError(400, "Action does not match this review domain.");
  }

  ctx.inject(["webServer", "connection"], (webCtx) => {
    webCtx.effect(() => webCtx.webServer.register({ kind: "prefix", path: "/spec2gds-api", handler: async (request: any, response: any) => {
      try {
        await ready;
        if (!sameOrigin(request)) throw new HttpError(403, "Origin refused.");
        const path = new URL(request.url ?? "/", "http://localhost").pathname;
        if (path === "/spec2gds-api/capabilities" && request.method === "GET") return writeJson(response, 200, { model: config.model, provider: config.provider, owners: await owners.capabilities() });
        if (path === "/spec2gds-api/bindings/reserve" && request.method === "POST") {
          const body = await readBody(request);
          const result = await reserve(bindingInput(body), typeof body.sessionId === "string" ? body.sessionId : undefined);
          return writeJson(response, 201, { session: result.binding, cwd: result.cwd });
        }
        const bindingMatch = path.match(/^\/spec2gds-api\/bindings\/([^/]+)(?:\/(activate|abandon|reviews))?$/);
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
        }
        const reviewMatch = path.match(/^\/spec2gds-api\/reviews\/([^/]+)\/actions$/);
        if (reviewMatch && request.method === "POST") {
          const proposalId = decodeURIComponent(reviewMatch[1]!);
          const binding = state.listBindings(true).find(item => state.getReview(item.sessionId, proposalId));
          if (!binding) throw new HttpError(404, "Unknown proposal review.");
          const updated = await reviewAction(binding, state.getReview(binding.sessionId, proposalId)!, String((await readBody(request)).action ?? ""));
          return writeJson(response, 200, { review: publicReview(updated) });
        }
        throw new HttpError(404, "Unknown spec2gds endpoint.");
      } catch (error) {
        if (response.headersSent) return response.destroy();
        if (error instanceof HttpError || error instanceof OwnerError) return writeJson(response, error.status, { error: error.message, detail: error.detail });
        return writeJson(response, 500, { error: error instanceof Error ? error.message : String(error) });
      }
    } }));

    for (const route of ["/launch/spec", "/launch/spec-document", "/launch/circuit"]) {
      webCtx.effect(() => webCtx.webServer.register({ kind: "exact", path: route, handler: async (request: any, response: any) => {
        try {
          const url = new URL(request.url ?? route, "http://localhost");
          const result = await reserve({ domain: route === "/launch/circuit" ? "circuit" : "spec", serviceBaseUrl: url.searchParams.get("service_base_url") ?? "", documentId: url.searchParams.get("document_id") ?? "", scope: route === "/launch/spec" ? "entity" : "document", entityKind: url.searchParams.get("entity_kind") ?? undefined, entityId: url.searchParams.get("entity_id") ?? undefined });
          response.writeHead(303, {
            Location: authenticatedLaunchLocation(webCtx.connection, result.binding.sessionId, result.cwd),
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
