import { assistantActions, integrationMetadata, matchesAssistantAction } from "./assistant-integration";
/** HTTP composition for Circuit operations, leases and source synchronization.
 * Generic operation preview validates Circuit semantics; source preview/commit
 * additionally call the authoritative owner. A source-bound proposal Accept
 * must enter the client's private draft rather than bypass Save to Spec. */
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import {
  CircuitBackendError,
  humanNameKey,
  assistantCircuitOperationSchema,
  createEmptyCircuitDocument,
  isCircuitSourceBindingV1,
  validateContractDefinition,
  type CircuitChangeResult,
  type CircuitDesignerBackend,
  type CircuitDocument,
  type CircuitOperationBatch,
  type CircuitProposalCreateRequest,
  type CircuitSourceSyncResponse,
  type ServiceError,
  type ServiceEvent,
} from "@spec2gds/circuit-core";
import { HttpCallbackProvider, validateCallbackUrl } from "./provider";
import { EphemeralCircuitSessionBackend } from "./session-backend";
import type { PublicServiceDirectory } from "./service-registry";
import { StructuredLogger, loadObservabilityConfig } from "@spec2gds/observability/node";
import { createHash, randomUUID } from "node:crypto";
import { CircuitPreferencesStore } from "./preferences-store";
import { resolve } from "node:path";
import {
  HttpSourceDesignProvider,
  type SourceBindingRegistration,
  type SourceCommitBody,
  type StoredSourceBinding,
} from "./source-provider";

type MutableProviderBackend = CircuitDesignerBackend & Pick<EphemeralCircuitSessionBackend, "registerProvider" | "resolveProposal">;

export interface CircuitServiceOptions {
  backend?: MutableProviderBackend;
  providerAllowlist?: string[];
  now?: () => Date;
  serviceDirectory?: PublicServiceDirectory;
  logger?: StructuredLogger;
  preferencesPath?: string;
}

interface RouteContext {
  documentId?: string;
  tail: string[];
}

export class CircuitDesignerService {
  readonly server: Server;
  private readonly backend: MutableProviderBackend;
  private eventSequence = 0;
  private readonly subscribers = new Map<string, Set<ServerResponse>>();
  private readonly allowlist: Set<string>;
  private readonly now: () => Date;
  private readonly serviceDirectory?: PublicServiceDirectory;
  private readonly logger: StructuredLogger;
  private readonly preferences: CircuitPreferencesStore;
  private readonly sourceBindings = new Map<string, StoredSourceBinding>();
  private readonly pendingSourceBindings = new Map<string, StoredSourceBinding>();
  private readonly sourceResults = new Map<string, CircuitSourceSyncResponse>();
  private readonly documentWrites = new Map<string, Promise<void>>();

  constructor(options: CircuitServiceOptions = {}) {
    this.backend = options.backend ?? new EphemeralCircuitSessionBackend();
    this.now = options.now ?? (() => new Date());
    this.serviceDirectory = options.serviceDirectory;
    this.allowlist = new Set([
      ...(this.serviceDirectory
        ? [new URL(this.serviceDirectory.services.spec_editor.service_url).hostname]
        : []),
      ...(options.providerAllowlist ?? []),
    ]);
    this.logger = options.logger ?? new StructuredLogger("circuit-designer", loadObservabilityConfig());
    this.preferences = new CircuitPreferencesStore(options.preferencesPath
      ?? resolve(process.env.CIRCUIT_DESIGNER_PREFERENCES_FILE ?? ".circuit-designer/preferences.json"));
    this.server = createServer((request, response) => void this.handle(request, response));
  }

  listen(port = 0, host = "0.0.0.0"): Promise<number> {
    return new Promise((resolve, reject) => {
      this.server.once("error", reject);
      this.server.listen(port, host, () => {
        const address = this.server.address();
        resolve(typeof address === "object" && address ? address.port : port);
      });
    });
  }

  close(): Promise<void> {
    for (const clients of this.subscribers.values()) for (const response of clients) response.end();
    return new Promise((resolve, reject) => this.server.close((error) => error ? reject(error) : resolve()));
  }

  private async handle(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const path = new URL(request.url ?? "/", "http://localhost").pathname;
    const documentId = /^\/api\/circuit-designer\/v1\/documents\/([^/]+)/.exec(path)?.[1];
    if (!documentId || request.method === "GET" || request.method === "OPTIONS") return this.handleUnlocked(request, response);
    // Source callbacks can yield. Serialize lease changes, source writes and
    // rebinding so a displaced client cannot finish a save after takeover.
    const previous = this.documentWrites.get(documentId) ?? Promise.resolve();
    let release!: () => void;
    const current = new Promise<void>(resolve => { release = resolve; });
    this.documentWrites.set(documentId, current);
    await previous;
    try { await this.handleUnlocked(request, response); }
    finally {
      release();
      if (this.documentWrites.get(documentId) === current) this.documentWrites.delete(documentId);
    }
  }

  private async handleUnlocked(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const correlationId = String(request.headers["x-request-id"] ?? randomUUID().replaceAll("-", ""));
    const started = performance.now();
    let failure: unknown;
    response.setHeader("X-Request-ID", correlationId);
    response.once("finish", () => {
      if (request.url?.includes("/logs/events")) return;
      const status = response.statusCode;
      this.logger.event({
        component: "http", event: "request_completed",
        message: `${request.method ?? "GET"} ${request.url ?? "/"} returned ${status}`,
        severity: status >= 500 ? "error" : status >= 400 ? "warning" : "info",
        correlationId, durationMs: performance.now() - started, status,
        details: {
          method: request.method, url: request.url,
          ...(failure instanceof Error ? { error: { name: failure.name, message: failure.message, stack: failure.stack } } : {}),
        },
      });
    });
    try {
      const url = new URL(request.url ?? "/", "http://localhost");
      const prefix = "/api/circuit-designer/v1";
      if (!url.pathname.startsWith(prefix)) return this.error(response, 404, "not_found", "Unknown endpoint.");
      const parts = url.pathname.slice(prefix.length).split("/").filter(Boolean).map(decodeURIComponent);
      const context = this.routeContext(parts);
      const method = request.method ?? "GET";

      if (method === "GET" && url.pathname === `${prefix}/assistant/integration-metadata`) {
        return this.jsonResponse(response, 200, integrationMetadata());
      }
      if (matchesAssistantAction("health", method, url.pathname.slice(prefix.length))) {
        return this.jsonResponse(response, 200, { status: "ok", service: "circuit_designer" });
      }
      if (matchesAssistantAction("capabilities", method, url.pathname.slice(prefix.length))) {
        return this.jsonResponse(response, 200, {
          schema_version: 1,
          service: "circuit_designer",
          api_version: "v1",
          capabilities: [
            "canonical-documents", "edit-leases", "operations", "proposals",
            "component-providers", "source-bindings", "preferences", "events", "exports",
          ],
          integrations: {
            service_directory: Boolean(this.serviceDirectory),
            callback_provider_allowlist: [...this.allowlist].sort(),
          },
        });
      }
      if (matchesAssistantAction("operation_schema", method, url.pathname.slice(prefix.length))) {
        if (url.searchParams.get("scope") !== "document" || !url.searchParams.get("document_id")) {
          throw new CircuitBackendError("validation_failed", "Circuit schema requires document_id and scope=document.");
        }
        await this.backend.get(url.searchParams.get("document_id")!);
        const operation_schema = assistantCircuitOperationSchema();
        const canonical = JSON.stringify(operation_schema, (_key, value: unknown) => value && typeof value === "object" && !Array.isArray(value)
          ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))
          : value);
        const digest = `sha256:${createHash("sha256").update(canonical).digest("hex")}`;
        return this.jsonResponse(response, 200, { schema_version: 1, digest, operation_schema });
      }
      if (method === "GET" && parts[0] === "services" && parts.length === 1) {
        if (!this.serviceDirectory) {
          return this.error(response, 404, "not_found", "No legacy service directory was configured. Use /capabilities for portable discovery.");
        }
        return this.jsonResponse(response, 200, this.serviceDirectory);
      }
      if (method === "GET" && parts[0] === "preferences" && parts.length === 1) {
        return this.jsonResponse(response, 200, await this.preferences.get());
      }
      if (method === "PUT" && parts[0] === "preferences" && parts.length === 1) {
        const body = await this.json(request, 262_144);
        return this.jsonResponse(response, 200, { preferences: await this.preferences.put(body), persisted: true });
      }
      if (method === "POST" && parts[0] === "logs" && parts[1] === "events" && parts.length === 2) {
        const body = await this.json(request) as { session_id?: string; events?: unknown[] };
        if (JSON.stringify(body).length > 262_144 || !Array.isArray(body.events) || body.events.length > 100) {
          return this.error(response, 422, "validation_failed", "Browser log batch is invalid.");
        }
        for (const value of body.events) {
          if (!value || typeof value !== "object") continue;
          const event = value as Record<string, unknown>;
          const severity = ["debug", "info", "warning", "error"].includes(String(event.severity))
            ? String(event.severity) as "debug" | "info" | "warning" | "error" : "warning";
          this.logger.event({
            component: String(event.component ?? "ui"), event: String(event.event ?? "browser_event"),
            message: String(event.message ?? "Browser event"), severity, origin: "browser",
            details: event.details, correlationId: typeof event.correlation_id === "string" ? event.correlation_id : undefined,
            sessionId: String(body.session_id ?? "unknown"), timestamp: typeof event.timestamp === "string" ? event.timestamp : undefined,
          });
        }
        response.statusCode = 204; response.end(); return;
      }

      if (method === "POST" && parts[0] === "documents" && parts.length === 1) {
        const body = await this.json(request) as { request_id: string; document: CircuitDocument };
        return this.change(response, await this.backend.create(body.document, body.request_id), body.document.document_id);
      }
      if (matchesAssistantAction("list_documents", method, url.pathname.slice(prefix.length))) {
        const documents = await this.backend.listDocuments();
        return this.jsonResponse(response, 200, { documents });
      }
      if (matchesAssistantAction("resolve_document", method, url.pathname.slice(prefix.length))) {
        const name = url.searchParams.get("name");
        if (!name) return this.error(response, 422, "invalid_name", "Select a document name.");
        const documents = await this.backend.listDocuments();
        const matches = documents.filter(item => humanNameKey(item.label) === humanNameKey(name));
        if (matches.length !== 1) return this.error(response, 422, "ambiguous_name", `Unknown or ambiguous document “${name}”. Choose: ${documents.map(item => item.label).join(", ")}.`);
        return this.jsonResponse(response, 200, matches[0]);
      }
      if (matchesAssistantAction("create_document", method, url.pathname.slice(prefix.length))) {
        const body = await this.json(request) as { document_id?: string; label?: string; request_id?: string };
        if (!body.document_id?.trim() || !body.label?.trim()) {
          return this.error(response, 422, "validation_failed", "document_id and label are required.");
        }
        const document = createEmptyCircuitDocument(body.document_id.trim(), body.label.trim());
        return this.change(response, await this.backend.create(
          document,
          body.request_id?.trim() || `create-empty:${body.document_id.trim()}`,
        ), document.document_id);
      }
      if (method === "POST" && parts[0] === "constructions" && parts[1] === "validate") {
        const body = await this.json(request);
        this.requireDefinition("CircuitConstruction", body);
        return this.change(response, await this.backend.validateConstruction(body as never));
      }
      if (!context.documentId) return this.error(response, 404, "not_found", "Unknown endpoint.");
      const documentId = context.documentId;
      const tail = context.tail;

      if (matchesAssistantAction("context_document", method, url.pathname.slice(prefix.length))) return this.jsonResponse(response, 200, await this.backend.get(documentId));
      if (method === "PUT" && tail.length === 0) {
        this.requireIndependent(documentId);
        const body = await this.json(request) as { request_id: string; expected_revision: string; document: CircuitDocument };
        return this.change(response, await this.backend.replace(
          documentId, body.document, body.expected_revision, body.request_id,
        ), documentId);
      }
      if (matchesAssistantAction("preview_proposal", method, url.pathname.slice(prefix.length))) {
        const batch = await this.json(request);
        this.requireDefinition("CircuitOperationBatch", batch);
        return this.change(response, await this.backend.preview(documentId, batch as CircuitOperationBatch));
      }
      if (method === "POST" && tail[0] === "operations" && tail[1] === "commit") {
        this.requireIndependent(documentId);
        const body = await this.json(request) as { batch: CircuitOperationBatch; lease_id?: string };
        this.requireDefinition("CircuitOperationBatch", body.batch);
        return this.change(response, await this.backend.commit(documentId, body.batch, body.lease_id), documentId);
      }
      if (tail[0] === "lock") return await this.lockRoute(request, response, documentId, tail);
      if (method === "GET" && tail[0] === "summary") {
        return this.jsonResponse(response, 200, await this.backend.summary(documentId));
      }
      if (method === "GET" && tail[0] === "components" && tail.length === 1) {
        const origin = url.searchParams.get("origin") as "local" | "builtin" | "provider" | null;
        return this.jsonResponse(response, 200, {
          components: await this.backend.lookupComponents(documentId, {
            ...(url.searchParams.get("text") ? { text: url.searchParams.get("text")! } : {}),
            ...(origin ? { origin } : {}),
          }),
        });
      }
      if (method === "POST" && tail[0] === "components" && tail[2] === "resolve") {
        const result = await this.backend.resolveComponentDesign(documentId, tail[1]);
        this.emit(documentId, "provider.requested");
        return this.jsonResponse(response, 200, result);
      }
      if (method === "POST" && tail[0] === "components" && tail[2] === "commit") {
        const body = await this.json(request);
        this.requireDefinition("ProviderCommitRequest", body);
        const result = await this.backend.commitComponentDesign(documentId, tail[1], body as never);
        this.emit(documentId, "provider.requested");
        return this.jsonResponse(response, result.accepted ? 200 : 409, result);
      }
      if (tail[0] === assistantActions.source_binding.path.split("/").at(-1)) {
        if (method === "GET" && tail.length === 1) {
          const stored = this.sourceBindings.get(documentId);
          if (!stored) return this.error(response, 404, "not_found", "Document has no source binding.");
          return this.jsonResponse(response, 200, stored.binding);
        }
        if (method === "PUT" && tail.length === 1) {
          const body = await this.json(request) as SourceBindingRegistration;
          let callback: URL;
          try {
            callback = validateCallbackUrl(body.callback_url, this.allowlist, body.allow_non_loopback);
          } catch (reason) {
            throw new CircuitBackendError("validation_failed", reason instanceof Error ? reason.message : String(reason));
          }
          if (!isCircuitSourceBindingV1(body.binding) || !body.token) {
            throw new CircuitBackendError("validation_failed", "Source binding registration is invalid.");
          }
          await this.backend.get(documentId);
          const stored = {
            binding: structuredClone(body.binding),
            provider: new HttpSourceDesignProvider(callback, body.token),
          };
          const lease = await this.backend.getLease(documentId);
          const active = this.sourceBindings.get(documentId)?.binding;
          if ((lease || body.recovery) && active && (active.source_document_id !== stored.binding.source_document_id
            || active.editable_design_id !== stored.binding.editable_design_id)) {
            throw new CircuitBackendError("validation_failed", "A locked Circuit cannot be rebound to a different source.");
          }
          if (body.recovery) {
            const recovered = await this.recoverSource(documentId, body.recovery, stored);
            return this.jsonResponse(response, 200, recovered);
          }
          if (lease) {
            // Keep a replacement callback separate from the active draft's
            // binding. Recovery can use it after a Spec service restart without
            // exposing callback credentials or requiring cross-origin requests.
            this.pendingSourceBindings.set(documentId, stored);
            throw new CircuitBackendError("lock_conflict", "This Circuit has an active draft. Open it to review or take over editing.", [], { document_id: documentId, lease });
          }
          this.sourceBindings.set(documentId, stored);
          this.pendingSourceBindings.delete(documentId);
          return this.jsonResponse(response, 200, body.binding);
        }
      }
      if (method === "POST" && tail[0] === "source" && tail[1] === "preview") {
        return await this.sourcePreview(response, documentId, await this.json(request) as SourceCommitBody);
      }
      if (method === "POST" && tail[0] === "source" && tail[1] === "commit") {
        return await this.sourceCommit(response, documentId, await this.json(request) as SourceCommitBody);
      }
      if (method === "POST" && tail[0] === "source" && tail[1] === "reload") {
        return await this.sourceReload(response, documentId);
      }
      if (method === "POST" && tail[0] === "source" && tail[1] === "recover") {
        return this.jsonResponse(response, 200, await this.recoverSource(documentId, await this.json(request) as { expected_lease_id: string; owner_id: string }));
      }
      if (method === "POST" && tail[0] === "queries" && tail[1] === "subgraph") {
        return this.jsonResponse(response, 200, await this.backend.subgraph(documentId, await this.json(request) as never));
      }
      if (matchesAssistantAction("export_svg", method, url.pathname.slice(prefix.length))) {
        const exportOptions = await this.json(request) as { format: "json" | "svg" | "png"; selection?: string[] };
        const exported = await this.backend.export(documentId, exportOptions);
        response.statusCode = 200;
        response.setHeader("Content-Type", exported.media_type);
        response.setHeader("Content-Disposition", `attachment; filename="${exported.filename}"`);
        response.end(exported.data);
        return;
      }
      if (tail[0] === assistantActions.send_proposal.path.split("/").at(-1)) return await this.proposalRoute(request, response, documentId, tail);
      if (method === "PUT" && tail[0] === "provider") {
        const body = await this.json(request) as { callback_url: string; allow_non_loopback?: boolean };
        let callback: URL;
        try {
          callback = validateCallbackUrl(body.callback_url, this.allowlist, body.allow_non_loopback);
        } catch (reason) {
          throw new CircuitBackendError(
            "validation_failed",
            reason instanceof Error ? reason.message : String(reason),
          );
        }
        this.backend.registerProvider(new HttpCallbackProvider(callback), documentId);
        response.statusCode = 204;
        response.end();
        return;
      }
      if (method === "GET" && tail[0] === "events") return this.subscribe(request, response, documentId);
      return this.error(response, 404, "not_found", "Unknown endpoint.");
    } catch (reason) {
      failure = reason;
      this.handleError(response, reason);
    }
  }

  private routeContext(parts: string[]): RouteContext {
    if (parts[0] !== "documents" || !parts[1]) return { tail: parts };
    return { documentId: parts[1], tail: parts.slice(2) };
  }

  private sourceBinding(documentId: string): StoredSourceBinding {
    const stored = this.sourceBindings.get(documentId);
    if (!stored) throw new CircuitBackendError("not_found", "Document has no source binding.");
    return stored;
  }

  // Ordinary writes to accepted document state must cross this guard. Source
  // projections have another owner and can change only via its save protocol.
  private requireIndependent(documentId: string): void {
    if (this.sourceBindings.has(documentId)) {
      throw new CircuitBackendError("validation_failed", "Source-bound documents must use Save to Spec.");
    }
  }

  // A Circuit-valid candidate is only the first validation layer. Source
  // preview/commit below can still reject its translation into owner semantics.
  private async sourceCandidate(documentId: string, body: SourceCommitBody) {
    const stored = this.sourceBinding(documentId);
    if (!stored.binding.writable) throw new CircuitBackendError("validation_failed", stored.binding.message ?? "Source projection is read-only.");
    const lease = await this.backend.getLease(documentId);
    if (!lease || lease.lease_id !== body.lease_id) throw new CircuitBackendError("lock_conflict", "The edit lease is missing or expired.");
    const preview = await this.backend.preview(documentId, body.batch);
    if (preview.status !== "accepted" || !preview.candidate) {
      return { stored, preview, candidate: undefined };
    }
    return { stored, preview, candidate: preview.candidate };
  }

  private async sourcePreview(response: ServerResponse, documentId: string, body: SourceCommitBody): Promise<void> {
    this.requireDefinition("CircuitOperationBatch", body.batch);
    const { stored, preview, candidate } = await this.sourceCandidate(documentId, body);
    if (!candidate) {
      return this.jsonResponse(response, 200, {
        accepted: false,
        source_revision_hash: stored.binding.base_source_revision_hash,
        diagnostics: preview.diagnostics,
      });
    }
    const result = await stored.provider.preview(stored.binding, body.batch.request_id, candidate);
    return this.jsonResponse(response, 200, result);
  }

  private async recoverSource(documentId: string, request: { expected_lease_id: string; owner_id: string }, replacement?: StoredSourceBinding) {
    const current = await this.backend.getLease(documentId);
    if (!request.expected_lease_id || current?.lease_id !== request.expected_lease_id) {
      throw new CircuitBackendError("lock_conflict", "The editing lease changed. Review the current lock before taking over.", [], { document_id: documentId, lease: current });
    }
    const stored = replacement ?? this.pendingSourceBindings.get(documentId) ?? this.sourceBinding(documentId);
    if (!stored.binding.writable) throw new CircuitBackendError("validation_failed", "This Circuit is read-only.");
    const resolved = await stored.provider.resolve(stored.binding);
    if (!resolved.accepted || !resolved.document) throw new CircuitBackendError("provider_failed", "Could not refresh the saved source. The existing draft lock is unchanged. Reopen this Circuit from Spec Editor to refresh its source binding.", resolved.diagnostics);
    const lease = await this.backend.takeOverLease(documentId, request.expected_lease_id, request.owner_id, 900, resolved.document);
    stored.binding = { ...stored.binding, base_source_revision_hash: resolved.source_revision_hash };
    this.sourceBindings.set(documentId, stored);
    this.pendingSourceBindings.delete(documentId);
    const snapshot = await this.backend.get(documentId);
    this.emit(documentId, "lock.changed");
    this.emit(documentId, "document.changed", snapshot.revision);
    return { lease, snapshot, binding: stored.binding };
  }

  private async sourceCommit(response: ServerResponse, documentId: string, body: SourceCommitBody): Promise<void> {
    this.requireDefinition("CircuitOperationBatch", body.batch);
    const registered = this.sourceBinding(documentId);
    // This receipt cache lasts only for this service process. Request IDs name
    // retries of the same save; callers must not reuse one for different content.
    const replayKey = `${registered.binding.binding_id}:${body.batch.request_id}`;
    const replay = this.sourceResults.get(replayKey);
    if (replay) return this.jsonResponse(response, 200, replay);
    if (body.proposal_id) {
      const proposal = (await this.backend.listProposals(documentId)).find(item => item.proposal_id === body.proposal_id);
      if (!proposal || !proposal.batch || proposal.base_revision !== body.batch.expected_revision) {
        throw new CircuitBackendError("proposal_stale", "The staged proposal is missing or stale.");
      }
    }
    const { stored, preview, candidate } = await this.sourceCandidate(documentId, body);
    if (!candidate) {
      return this.jsonResponse(response, 200, {
        accepted: false,
        source_revision_hash: stored.binding.base_source_revision_hash,
        diagnostics: preview.diagnostics,
      });
    }
    const sourcePreview = await stored.provider.preview(stored.binding, body.batch.request_id, candidate);
    if (!sourcePreview.accepted) return this.jsonResponse(response, 200, sourcePreview);
    const result = await stored.provider.commit(stored.binding, body.batch.request_id, candidate);
    if (!result.accepted || !result.document) return this.jsonResponse(response, 200, result);
    if (result.document.document_id !== documentId) {
      throw new CircuitBackendError("provider_failed", "Source provider returned a mismatched document ID.");
    }
    // The owner has saved before the ephemeral Circuit session is replaced.
    // Refresh can fail after that save; this is not a transaction across stores.
    // Reopen from the owner before treating a lost response as an unsaved source.
    const before = await this.backend.get(documentId);
    // A long source callback may outlast the lease. The per-document gate
    // prevents another writer from acquiring it before reconciliation finishes.
    if ((await this.backend.getLease(documentId))?.lease_id === body.lease_id) await this.backend.releaseLease(documentId, body.lease_id);
    const replaced = await this.backend.replace(documentId, result.document, before.revision, `source:${body.batch.request_id}`);
    if (replaced.status !== "accepted" || !replaced.snapshot) {
      throw new CircuitBackendError("provider_failed", "Specification saved, but the Circuit session could not refresh.", replaced.diagnostics);
    }
    stored.binding = { ...stored.binding, base_source_revision_hash: result.source_revision_hash };
    // Staging/preview never resolves an owner proposal. Resolve only after both
    // source acceptance and the refreshed Circuit snapshot are confirmed.
    if (body.proposal_id) await this.backend.resolveProposal(documentId, body.proposal_id);
    this.emit(documentId, "document.changed", replaced.snapshot.revision);
    this.emit(documentId, "lock.changed");
    if (body.proposal_id) this.emit(documentId, "proposal.changed");
    const responseBody = { ...result, binding: stored.binding, snapshot: replaced.snapshot };
    this.sourceResults.set(replayKey, responseBody);
    return this.jsonResponse(response, 200, responseBody);
  }

  private async sourceReload(response: ServerResponse, documentId: string): Promise<void> {
    const stored = this.sourceBinding(documentId);
    if (await this.backend.getLease(documentId)) throw new CircuitBackendError("lock_conflict", "Cancel the active draft before reopening the latest source.");
    const result = await stored.provider.resolve(stored.binding);
    if (!result.accepted || !result.document) return this.jsonResponse(response, 200, result);
    const before = await this.backend.get(documentId);
    // A no-op reload preserves pending proposal identity. Replacing an unchanged
    // projection would advance its revision and needlessly invalidate staging.
    if (result.source_revision_hash === stored.binding.base_source_revision_hash
      && JSON.stringify(result.document) === JSON.stringify(before.document)) {
      return this.jsonResponse(response, 200, { ...result, binding: stored.binding, snapshot: before });
    }
    const replaced = await this.backend.replace(documentId, result.document, before.revision, `source-reload:${result.source_revision_hash}`);
    if (replaced.status !== "accepted" || !replaced.snapshot) {
      throw new CircuitBackendError("provider_failed", "Could not refresh the Circuit session.", replaced.diagnostics);
    }
    stored.binding = { ...stored.binding, base_source_revision_hash: result.source_revision_hash };
    return this.jsonResponse(response, 200, { ...result, binding: stored.binding, snapshot: replaced.snapshot });
  }

  private async lockRoute(
    request: IncomingMessage,
    response: ServerResponse,
    documentId: string,
    tail: string[],
  ): Promise<void> {
    if (request.method === "POST" && tail.length === 2 && tail[1] === "takeover") {
      this.requireIndependent(documentId);
      const body = await this.json(request) as { expected_lease_id: string; owner_id: string; ttl_seconds?: number };
      const lease = await this.backend.takeOverLease(documentId, body.expected_lease_id, body.owner_id, body.ttl_seconds);
      this.emit(documentId, "lock.changed");
      return this.jsonResponse(response, 200, lease);
    }
    if (request.method === "GET" && tail.length === 1) {
      return this.jsonResponse(response, 200, { lease: await this.backend.getLease(documentId) });
    }
    if (request.method === "POST" && tail.length === 1) {
      const body = await this.json(request) as { owner_id: string; ttl_seconds?: number };
      const lease = await this.backend.acquireLease(documentId, body.owner_id, body.ttl_seconds);
      this.emit(documentId, "lock.changed");
      return this.jsonResponse(response, 201, lease);
    }
    if (request.method === "PUT" && tail[1]) {
      const body = await this.json(request) as { ttl_seconds?: number };
      const lease = await this.backend.renewLease(documentId, tail[1], body.ttl_seconds);
      this.emit(documentId, "lock.changed");
      return this.jsonResponse(response, 200, lease);
    }
    if (request.method === "DELETE" && tail[1]) {
      await this.backend.releaseLease(documentId, tail[1]);
      this.emit(documentId, "lock.changed");
      response.statusCode = 204;
      response.end();
      return;
    }
    this.error(response, 404, "not_found", "Unknown lock endpoint.");
  }

  private async proposalRoute(
    request: IncomingMessage,
    response: ServerResponse,
    documentId: string,
    tail: string[],
  ): Promise<void> {
    if (request.method === "GET" && tail.length === 1) {
      return this.jsonResponse(response, 200, { proposals: await this.backend.listProposals(documentId) });
    }
    if (request.method === "POST" && tail.length === 1) {
      const input = await this.json(request) as Record<string, unknown>;
      const proposal = {
        proposal_id: input.proposal_id,
        document_id: input.document_id,
        base_revision: input.base_revision,
        title: input.title,
        summary: input.summary,
        ...(input.rationale !== undefined ? { rationale: input.rationale } : {}),
        ...(input.assumptions !== undefined ? { assumptions: input.assumptions } : {}),
        ...(input.construction !== undefined ? { construction: input.construction } : {}),
        ...(input.batch !== undefined ? { batch: input.batch } : {}),
      };
      this.requireDefinition("CircuitProposalCreateRequest", proposal);
      if (this.sourceBindings.has(documentId) && proposal.construction !== undefined) {
        throw new CircuitBackendError("validation_failed", "Source-bound proposals must contain an operation batch.");
      }
      const saved = await this.backend.submitProposal(proposal as CircuitProposalCreateRequest);
      this.emit(documentId, "proposal.changed");
      return this.jsonResponse(response, 201, saved);
    }
    if (request.method === "POST" && tail[1] && tail[2] === "decision") {
      const body = await this.json(request) as { decision: "accept" | "reject" };
      // The source-bound UI stages Accept locally; this direct endpoint cannot
      // accept it into the projection and bypass the authoritative source save.
      if (body.decision === "accept") this.requireIndependent(documentId);
      const result = await this.backend.decideProposal(documentId, tail[1], body.decision);
      this.emit(documentId, "proposal.changed");
      if (!result) {
        response.statusCode = 204;
        response.end();
      } else this.change(response, result, documentId);
      return;
    }
    this.error(response, 404, "not_found", "Unknown proposal endpoint.");
  }

  private subscribe(request: IncomingMessage, response: ServerResponse, documentId: string): void {
    response.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });
    response.write(": connected\n\n");
    const clients = this.subscribers.get(documentId) ?? new Set<ServerResponse>();
    clients.add(response);
    this.subscribers.set(documentId, clients);
    request.on("close", () => clients.delete(response));
  }

  private emit(documentId: string, kind: ServiceEvent["kind"], revision?: string): void {
    const event: ServiceEvent = {
      event_id: `event_${++this.eventSequence}`,
      kind,
      document_id: documentId,
      ...(revision ? { revision } : {}),
      timestamp: this.now().toISOString(),
    };
    for (const response of this.subscribers.get(documentId) ?? []) {
      response.write(`id: ${event.event_id}\ndata: ${JSON.stringify(event)}\n\n`);
    }
  }

  private change(response: ServerResponse, result: CircuitChangeResult, documentId?: string): void {
    const status = result.status === "conflict" ? 409
      : result.status === "locked" ? 423
        : result.status === "provider_failed" ? 502
          : result.status === "rejected" ? 400
            : 200;
    if (status === 200 && documentId) this.emit(documentId, "document.changed", result.snapshot?.revision);
    this.logger.event({
      component: "documents", event: "change_completed",
      message: `Circuit change ${result.status}${documentId ? ` for ${documentId}` : ""}`,
      severity: status >= 400 ? "warning" : "info", status, details: result,
    });
    this.jsonResponse(response, status, result);
  }

  private async json(request: IncomingMessage, maximumBytes?: number): Promise<unknown> {
    const chunks: Buffer[] = [];
    let bytes = 0;
    for await (const chunk of request) {
      const buffer = Buffer.from(chunk);
      bytes += buffer.length;
      if (maximumBytes !== undefined && bytes > maximumBytes) {
        throw new CircuitBackendError("validation_failed", "Circuit Designer preferences exceed 256 KiB.");
      }
      chunks.push(buffer);
    }
    if (!chunks.length) return {};
    try {
      return JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      throw new CircuitBackendError("validation_failed", "Request body is not valid JSON.");
    }
  }

  private requireDefinition(name: string, value: unknown): void {
    const checked = validateContractDefinition(name, value);
    if (!checked.valid) {
      throw new CircuitBackendError("validation_failed", `Request is not a valid ${name}.`);
    }
  }

  private handleError(response: ServerResponse, reason: unknown): void {
    if (reason instanceof CircuitBackendError) {
      const status = reason.code === "not_found" ? 404
        : reason.code === "lock_conflict" ? 423
          : reason.code === "revision_conflict" || reason.code === "proposal_stale" ? 409
            : reason.code === "provider_failed" ? 502
              : 400;
      return this.error(response, status, reason.code, reason.message, reason.diagnostics, reason.details);
    }
    this.error(response, 500, "internal_error", reason instanceof Error ? reason.message : String(reason));
  }

  private error(
    response: ServerResponse,
    status: number,
    code: string,
    message: string,
    diagnostics?: ServiceError["diagnostics"],
    details?: Record<string, unknown>,
  ): void {
    this.jsonResponse(response, status, { code, message, ...(diagnostics?.length ? { diagnostics } : {}), ...(details ? { details } : {}) });
  }

  private jsonResponse(response: ServerResponse, status: number, body: unknown): void {
    response.statusCode = status;
    response.setHeader("Content-Type", "application/json");
    response.end(JSON.stringify(body));
  }
}
