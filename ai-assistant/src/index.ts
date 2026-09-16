import { randomUUID } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import z from "@deepseek-ai/schemastery";
import { createUserMessage } from "@deepseek-ai/dsh-llm";
import { SessionId } from "@deepseek-ai/dsh-session";
import { OwnerClients, OwnerError } from "./owner-clients.js";
import { artifactDigest, ProductState } from "./state.js";
import { findProposal, findSpecChange, registerDomainTools } from "./tools.js";
import type { BindingInput, ProposalReview, ServiceConfig, SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

export const name = "spec2gds-harness-assistant";
export const inject = ["webServer", "agentLoop", "agents", "sessions", "sessionPersistence", "tools"];
export const Config = z.object({
  provider: z.string().min(1).required(),
  model: z.string().min(1).required(),
  stateRoot: z.string().min(1).required(),
  specAllowlist: z.string().min(1).required(),
  circuitAllowlist: z.string().min(1).required(),
  requestTimeoutMs: z.number().min(100).max(300_000).required(),
  maxActiveSessions: z.number().min(1).max(100).required(),
  eventPageSize: z.number().min(10).max(2_000).required(),
});

type AgentHandle = { agent: { session: { id: string }; followup(message: unknown): void; whenIdle(): Promise<void>; cancel(reason: unknown): void }; dispose(): Promise<void> };
type AppContext = {
  agents: { create(options: unknown): Promise<AgentHandle>; resume(options: unknown): Promise<AgentHandle> };
  sessions: { flush(session: unknown): Promise<void> };
  sessionPersistence: {
    list(): Promise<Array<{ header: { id: string; createdAt?: string } }>>;
    flush(): Promise<void>;
    open(id: unknown, access: "read"): Promise<{ read(offset?: number, length?: number): Promise<{ events: unknown[] }>; close(): Promise<void> }>;
  };
  webServer: { register(route: unknown): () => void };
  on(event: string, listener: (...args: any[]) => void): void;
  effect(effect: () => void | (() => void)): void;
};

interface LiveHandle { handle: AgentHandle; touched: number }
interface StreamResponse { write(value: string): boolean; end(): void; destroy(): void; on(event: string, listener: () => void): void; pending?: unknown[] | null }

function splitAllowlist(value: string): string[] {
  return value.split(",").map(item => item.trim()).filter(Boolean);
}

function project(event: unknown): Record<string, unknown> | null {
  if (!isRecord(event) || typeof event.type !== "string" || typeof event.seq !== "number" || !isRecord(event.data)) return null;
  const { type, seq, data } = event;
  if (type === "user/message") {
    const content = Array.isArray(data.content) ? data.content : [];
    return { type, seq, text: content.filter(isRecord).filter(item => item.type === "text").map(item => item.text).join("\n") };
  }
  if (type === "assistant/message" && isRecord(data.message)) {
    const content = Array.isArray(data.message.content) ? data.message.content : [];
    return { type, seq, text: content.filter(isRecord).filter(item => item.type === "text").map(item => item.text).join("\n"), interrupted: Boolean(data.interrupted) };
  }
  if (type === "tool/call") return { type, seq, callId: data.callId, name: data.name, arguments: data.arguments };
  if (type === "tool/result") return { type, seq, message: data.message };
  if (type === "turn/end") return { type, seq, data };
  return null;
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
  let value: unknown;
  try { value = JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw new HttpError(400, "Request body is not valid JSON."); }
  if (!isRecord(value)) throw new HttpError(400, "Request body must be an object.");
  return value;
}

class HttpError extends Error {
  constructor(readonly status: number, message: string, readonly detail?: unknown) { super(message); }
}

function bindingInput(value: Record<string, unknown>): BindingInput {
  const domain = value.domain;
  if (domain !== "spec" && domain !== "circuit") throw new HttpError(400, "domain must be spec or circuit.");
  if (typeof value.serviceBaseUrl !== "string" || !value.serviceBaseUrl.trim() || typeof value.documentId !== "string" || !value.documentId.trim()) {
    throw new HttpError(400, "serviceBaseUrl and documentId are required.");
  }
  const scope = value.scope === "entity" ? "entity" : "document";
  if (domain === "spec" && scope === "entity" && (typeof value.entityKind !== "string" || !value.entityKind.trim() || typeof value.entityId !== "string" || !value.entityId.trim())) {
    throw new HttpError(400, "Entity Spec bindings require entityKind and entityId.");
  }
  return {
    domain, serviceBaseUrl: value.serviceBaseUrl.trim(), documentId: value.documentId.trim(), scope,
    entityKind: typeof value.entityKind === "string" ? value.entityKind.trim() : undefined,
    entityId: typeof value.entityId === "string" ? value.entityId.trim() : undefined,
    title: typeof value.title === "string" ? value.title : undefined,
  };
}

function sameOrigin(request: any): boolean {
  const origin = request.headers.origin;
  if (!origin) return true;
  const host = request.headers.host;
  return origin === `http://${host}` || origin === `https://${host}`;
}

export function apply(ctx: AppContext, rawConfig: Record<string, unknown>): void {
  const config: ServiceConfig = {
    provider: String(rawConfig.provider), model: String(rawConfig.model), stateRoot: resolve(String(rawConfig.stateRoot)),
    specAllowlist: splitAllowlist(String(rawConfig.specAllowlist)),
    circuitAllowlist: splitAllowlist(String(rawConfig.circuitAllowlist)),
    requestTimeoutMs: Number(rawConfig.requestTimeoutMs), maxActiveSessions: Number(rawConfig.maxActiveSessions),
    eventPageSize: Number(rawConfig.eventPageSize),
  };
  const state = new ProductState(resolve(config.stateRoot, "assistant.sqlite3"));
  const owners = new OwnerClients(config.specAllowlist, config.circuitAllowlist, config.requestTimeoutMs);
  const handles = new Map<string, LiveHandle>();
  const pending = new Map<string, Promise<AgentHandle>>();
  const running = new Map<string, Promise<void>>();
  const subscribers = new Map<string, Set<StreamResponse>>();
  let closing = false;

  const ready = (async () => {
    const stored = new Set((await ctx.sessionPersistence.list()).map(item => String(item.header.id)));
    for (const binding of state.listCreatingBindings()) {
      if (stored.has(binding.sessionId)) state.activateBinding(binding.sessionId);
      else state.deleteBinding(binding.sessionId);
    }
    state.recoverInterruptedReviews();
  })();

  const setup = (binding: SessionBinding) => (agentContext: any): void => {
    registerDomainTools(agentContext, binding, state, owners);
  };

  async function evictIdle(): Promise<void> {
    if (handles.size + pending.size < config.maxActiveSessions) return;
    const candidate = [...handles.entries()]
      .filter(([id]) => !running.has(id))
      .sort((left, right) => left[1].touched - right[1].touched)[0];
    if (!candidate) throw new HttpError(503, "All active conversation slots are busy.");
    handles.delete(candidate[0]);
    await candidate[1].handle.dispose();
  }

  async function getHandle(id: string, create = false): Promise<AgentHandle> {
    await ready;
    if (closing) throw new HttpError(503, "Assistant is shutting down.");
    const live = handles.get(id);
    if (live) { live.touched = Date.now(); return live.handle; }
    const existing = pending.get(id);
    if (existing) return existing;
    const binding = state.getBinding(id);
    if (!binding || (create ? binding.status !== "creating" : binding.status !== "active")) {
      throw new HttpError(404, "Unknown assistant session.");
    }
    owners.assertStoredBinding(binding);
    await evictIdle();
    const task = (create
      ? ctx.agents.create({ sessionId: SessionId(id), meta: { domain: binding.domain, documentId: binding.documentId }, agentOptions: { provider: config.provider, model: config.model }, setup: setup(binding) })
      : ctx.agents.resume({ resumeSessionId: SessionId(id), agentOptions: { provider: config.provider, model: config.model }, setup: setup(binding) }))
      .then(handle => { handles.set(id, { handle, touched: Date.now() }); return handle; });
    pending.set(id, task);
    try { return await task; }
    finally { pending.delete(id); }
  }

  async function createSession(input: BindingInput): Promise<SessionBinding> {
    await ready;
    let validated: Awaited<ReturnType<OwnerClients["validateBinding"]>>;
    try { validated = await owners.validateBinding(input); }
    catch (error) {
      if (error instanceof OwnerError) throw error;
      throw new HttpError(400, error instanceof Error ? error.message : String(error));
    }
    const id = randomUUID();
    state.createBinding(id, { ...input, ownerUrl: validated.ownerUrl });
    try {
      await getHandle(id, true);
      await ctx.sessionPersistence.flush();
      return state.activateBinding(id);
    } catch (error) {
      state.deleteBinding(id);
      const live = handles.get(id);
      handles.delete(id);
      if (live) await live.handle.dispose();
      throw error;
    }
  }

  async function snapshot(handle: AgentHandle, offset: number, limit: number): Promise<Record<string, unknown>> {
    await ctx.sessions.flush(handle.agent.session);
    const reader = await ctx.sessionPersistence.open(handle.agent.session.id, "read");
    try {
      const raw = (await reader.read(offset, limit)).events;
      return {
        events: raw.map(project).filter(Boolean), nextOffset: offset + raw.length,
        hasMore: raw.length === limit,
      };
    } finally { await reader.close(); }
  }

  function publish(id: string, packet: Record<string, unknown>): void {
    for (const response of subscribers.get(id) ?? []) {
      if (response.pending) response.pending.push(packet);
      else if (!response.write(`data: ${JSON.stringify(packet)}\n\n`)) response.destroy();
    }
  }

  ctx.on("session/event", (session: { id: string }, event: unknown) => {
    const value = project(event);
    if (value) publish(String(session.id), { kind: "event", event: value });
  });
  ctx.on("agent/assistant-stream", ({ agent, frame }: any) => {
    const id = String(agent.session.id);
    if (frame.type === "start") publish(id, { kind: "stream-start" });
    if (frame.type === "chunk" && frame.chunk.type === "text-delta") publish(id, { kind: "delta", text: frame.chunk.text });
  });

  async function reviewAction(binding: SessionBinding, review: ProposalReview, action: string): Promise<ProposalReview> {
    if (artifactDigest(review.artifact) !== review.artifactDigest) {
      throw new HttpError(409, "Stored proposal content failed its integrity check.");
    }
    if (action === "discard") {
      return state.transitionReview(binding.sessionId, review.proposalId, ["ready", "rejected", "stale", "reconcile"], "discarded");
    }
    if (binding.domain === "spec" && action === "apply") {
      if (review.state === "reconcile") {
        try {
          const found = findSpecChange(await owners.specChanges(binding), review.proposalId);
          if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "applied", { ownerResult: found });
        } catch { /* The idempotent owner apply below is still safe to retry. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.source_revision_hash !== review.baseRevision) {
          return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", { diagnostics: "The Spec source revision changed." });
        }
        const result = await owners.applySpec(binding, review.artifact);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "applied", { ownerResult: result });
      } catch (error) {
        if (error instanceof OwnerError && error.uncertain) {
          try {
            const found = findSpecChange(await owners.specChanges(binding), review.proposalId);
            if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "applied", { ownerResult: found });
          } catch { /* Preserve uncertain state. */ }
          return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "reconcile", { diagnostics: error.detail });
        }
        const next = error instanceof OwnerError && error.status === 409 ? "stale" : "rejected";
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], next, {
          diagnostics: error instanceof OwnerError ? error.detail : String(error),
        });
      }
    }
    if (binding.domain === "circuit" && action === "send") {
      if (review.state === "reconcile") {
        try {
          const found = findProposal(await owners.circuitProposals(binding), review.proposalId);
          if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["reconcile"], "sent", { ownerResult: found });
        } catch { /* Continue with the same persisted proposal identity. */ }
      }
      state.transitionReview(binding.sessionId, review.proposalId, ["ready", "reconcile"], "applying");
      try {
        const current = await owners.context(binding);
        if (current.revision !== review.baseRevision) {
          return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "stale", { diagnostics: "The Circuit revision changed." });
        }
        const result = await owners.sendCircuit(binding, review.artifact);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { ownerResult: result });
      } catch (error) {
        try {
          const found = findProposal(await owners.circuitProposals(binding), review.proposalId);
          if (found) return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], "sent", { ownerResult: found });
        } catch { /* Preserve the original result below. */ }
        const uncertain = error instanceof OwnerError && (error.uncertain || error.status === 409);
        return state.transitionReview(binding.sessionId, review.proposalId, ["applying"], uncertain ? "reconcile" : "rejected", {
          diagnostics: error instanceof OwnerError ? error.detail : String(error),
        });
      }
    }
    throw new HttpError(400, "Action does not match this review domain.");
  }

  ctx.effect(() => ctx.webServer.register({ kind: "prefix", path: "/api", handler: async (request: any, response: any) => {
    try {
      await ready;
      if (!sameOrigin(request)) throw new HttpError(403, "Origin refused.");
      const url = new URL(request.url ?? "/", "http://localhost");
      const path = url.pathname;
      if (path === "/api/config" && request.method === "GET") {
        return writeJson(response, 200, { model: config.model, provider: config.provider, existingDocumentsOnly: true });
      }
      if (path === "/api/capabilities" && request.method === "GET") {
        return writeJson(response, 200, { assistant: { ready: true, modelConfigured: Boolean(process.env.OPENAI_API_KEY) }, owners: await owners.capabilities() });
      }
      if (path === "/api/sessions" && request.method === "GET") {
        return writeJson(response, 200, { sessions: state.listBindings(url.searchParams.get("archived") === "true") });
      }
      if (path === "/api/sessions" && request.method === "POST") {
        const binding = await createSession(bindingInput(await readBody(request)));
        return writeJson(response, 201, { session: binding });
      }
      const match = path.match(/^\/api\/sessions\/([a-f0-9-]{36})(?:\/(events|messages|cancel|reviews|manage))?(?:\/([^/]+))?(?:\/(actions))?$/);
      if (!match) throw new HttpError(404, "Unknown endpoint.");
      const [, id, resource, proposalId, actionResource] = match;
      const binding = state.getBinding(id!);
      if (!binding || binding.status !== "active") throw new HttpError(404, "Unknown assistant session.");
      owners.assertStoredBinding(binding);
      if (binding.archived && (resource === "messages" || resource === "cancel" || (resource === "reviews" && actionResource === "actions"))) {
        throw new HttpError(409, "Unarchive this conversation before changing it.");
      }
      if (!resource && request.method === "GET") {
        const handle = await getHandle(id!);
        const offset = Math.max(0, Number(url.searchParams.get("offset") ?? 0));
        return writeJson(response, 200, { session: binding, ...(await snapshot(handle, offset, config.eventPageSize)), running: running.has(id!), reviews: state.listReviews(id!) });
      }
      if (resource === "manage" && request.method === "POST") {
        const body = await readBody(request);
        const action = String(body.action ?? "");
        if (action === "rename") {
          if (typeof body.title !== "string" || !body.title.trim() || body.title.length > 120) throw new HttpError(400, "Title must contain 1 to 120 characters.");
          return writeJson(response, 200, { session: state.updateBinding(id!, { title: body.title }) });
        }
        if (action === "archive" || action === "unarchive") {
          if (running.has(id!)) throw new HttpError(409, "Wait for the active turn before changing archive state.");
          const updated = state.updateBinding(id!, { archived: action === "archive" });
          if (action === "archive") {
            const live = handles.get(id!);
            handles.delete(id!);
            if (live) await live.handle.dispose();
          }
          return writeJson(response, 200, { session: updated });
        }
        throw new HttpError(400, "Unknown conversation action.");
      }
      if (resource === "events" && request.method === "GET") {
        const handle = await getHandle(id!);
        const offset = Math.max(0, Number(url.searchParams.get("offset") ?? 0));
        response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store", Connection: "keep-alive", "X-Accel-Buffering": "no" });
        const clients = subscribers.get(id!) ?? new Set<StreamResponse>();
        subscribers.set(id!, clients); clients.add(response); response.pending = [];
        response.write(`data: ${JSON.stringify({ kind: "snapshot", ...(await snapshot(handle, offset, config.eventPageSize)), running: running.has(id!), reviews: state.listReviews(id!) })}\n\n`);
        const queued = response.pending; response.pending = null;
        for (const packet of queued ?? []) response.write(`data: ${JSON.stringify(packet)}\n\n`);
        const heartbeat = setInterval(() => response.write(": keepalive\n\n"), 15_000);
        response.on("close", () => { clearInterval(heartbeat); clients.delete(response); if (!clients.size) subscribers.delete(id!); });
        return;
      }
      if (resource === "messages" && request.method === "POST") {
        const body = await readBody(request);
        if (typeof body.text !== "string" || !body.text.trim() || body.text.length > 24_000) throw new HttpError(400, "Message must contain 1 to 24,000 characters.");
        if (running.has(id!)) throw new HttpError(409, "This conversation already has an active turn.");
        const handle = await getHandle(id!);
        const task = Promise.resolve().then(async () => {
          publish(id!, { kind: "status", running: true });
          handle.agent.followup(createUserMessage({ content: [{ type: "text", text: body.text as string }], source: { kind: "user" } }));
          await handle.agent.whenIdle(); await ctx.sessionPersistence.flush(); state.touchBinding(id!);
        }).catch(error => publish(id!, { kind: "error", error: error instanceof Error ? error.message : String(error) }))
          .finally(() => { running.delete(id!); publish(id!, { kind: "status", running: false, reviews: state.listReviews(id!) }); });
        running.set(id!, task);
        return writeJson(response, 202, { accepted: true });
      }
      if (resource === "cancel" && request.method === "POST") {
        await readBody(request); const handle = await getHandle(id!); handle.agent.cancel({ kind: "user" }); await running.get(id!);
        return writeJson(response, 200, { cancelled: true });
      }
      if (resource === "reviews" && !proposalId && request.method === "GET") {
        return writeJson(response, 200, { reviews: state.listReviews(id!) });
      }
      if (resource === "reviews" && proposalId && actionResource === "actions" && request.method === "POST") {
        const review = state.getReview(id!, proposalId);
        if (!review) throw new HttpError(404, "Unknown proposal review.");
        const body = await readBody(request);
        const updated = await reviewAction(binding, review, String(body.action ?? ""));
        publish(id!, { kind: "reviews", reviews: state.listReviews(id!) });
        return writeJson(response, 200, { review: updated });
      }
      throw new HttpError(405, "Method not allowed.");
    } catch (error) {
      if (response.headersSent) return response.destroy();
      if (error instanceof HttpError) return writeJson(response, error.status, { error: error.message, detail: error.detail });
      if (error instanceof OwnerError) return writeJson(response, error.status, { error: error.message, detail: error.detail });
      return writeJson(response, 500, { error: error instanceof Error ? error.message : String(error) });
    }
  } }));

  for (const route of ["/launch/spec", "/launch/spec-document", "/launch/circuit"]) {
    ctx.effect(() => ctx.webServer.register({ kind: "exact", path: route, handler: async (request: any, response: any) => {
      try {
        const url = new URL(request.url ?? route, "http://localhost");
        const domain = route === "/launch/circuit" ? "circuit" : "spec";
        const input: BindingInput = {
          domain,
          serviceBaseUrl: url.searchParams.get("service_base_url") ?? "",
          documentId: url.searchParams.get("document_id") ?? "",
          scope: route === "/launch/spec" ? "entity" : "document",
          entityKind: url.searchParams.get("entity_kind") ?? undefined,
          entityId: url.searchParams.get("entity_id") ?? undefined,
        };
        const binding = await createSession(input);
        response.writeHead(303, { Location: `/?session=${encodeURIComponent(binding.sessionId)}`, "Cache-Control": "no-store" }); response.end();
      } catch (error) {
        const status = error instanceof OwnerError ? error.status : error instanceof HttpError ? error.status : 400;
        writeJson(response, status, { error: error instanceof Error ? error.message : String(error), detail: error instanceof OwnerError ? error.detail : undefined });
      }
    } }));
  }

  ctx.effect(() => ctx.webServer.register({ kind: "exact", path: "/healthz", handler: (_request: any, response: any) => writeJson(response, 200, { status: "ok" }) }));
  ctx.effect(() => ctx.webServer.register({ kind: "exact", path: "/readyz", handler: async (_request: any, response: any) => {
    try { await ready; writeJson(response, 200, { status: "ready", modelConfigured: Boolean(process.env.OPENAI_API_KEY) }); }
    catch (error) { writeJson(response, 503, { status: "not_ready", error: error instanceof Error ? error.message : String(error) }); }
  } }));

  const webRoot = fileURLToPath(new URL("../web/dist/", import.meta.url));
  const serve = (path: string, mime: string) => async (_request: any, response: any): Promise<void> => {
    const content = await readFile(path);
    response.writeHead(200, {
      "Content-Type": `${mime}; charset=utf-8`, "Cache-Control": mime === "text/html" ? "no-cache" : "public, max-age=31536000, immutable",
      "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
    }); response.end(content);
  };
  ctx.effect(() => ctx.webServer.register({ kind: "exact", path: "/", handler: serve(resolve(webRoot, "index.html"), "text/html") }));
  ctx.effect(() => ctx.webServer.register({ kind: "prefix", path: "/assets", handler: async (request: any, response: any) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
      const file = resolve(webRoot, `.${pathname}`);
      if (!file.startsWith(`${resolve(webRoot, "assets")}${sep}`)) throw new Error("Invalid asset path.");
      const mime = file.endsWith(".css") ? "text/css" : file.endsWith(".js") ? "text/javascript" : "application/octet-stream";
      await serve(file, mime)(request, response);
    } catch { writeJson(response, 404, { error: "Asset not found." }); }
  } }));

  ctx.on("dispose", async () => {
    closing = true;
    for (const clients of subscribers.values()) for (const response of clients) response.end();
    subscribers.clear();
    await Promise.allSettled(pending.values());
    await Promise.allSettled(running.values());
    await Promise.allSettled([...handles.values()].map(value => value.handle.dispose()));
    handles.clear(); state.close();
  });
}
