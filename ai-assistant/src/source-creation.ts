import { defaultInstructions, InstructionSnapshots } from "./instructions.js";
/** Recoverable Spec package creation and separate binding conversation reservation.
 * Persist exact request inputs/progress before service calls. Package creation and
 * native conversation creation are separate side effects; uncertainty needs receipt
 * reconciliation using stable identities rather than a second package request. */
import { randomUUID } from "node:crypto";
import { dirname, relative, resolve, sep } from "node:path";
import { type InstructionBundle } from "./instructions.js";
import { normalizeSpecUrl, ServiceClients, ServiceError } from "./service-clients.js";
import { ProductState } from "./state.js";
import type { AssistantPreset, BindingInput, SourceCreationRequest, SessionBinding, WorkspaceDescriptor } from "./types.js";
import { filenameStem } from "./naming.js";

type Reservation = { session: SessionBinding; workspace: WorkspaceDescriptor };
type Reserve = (input: BindingInput, sessionId?: string, sourceSessionId?: string) => Promise<{ binding: SessionBinding; workspace: WorkspaceDescriptor }>;

export class SourceCreationError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

export function specDestination(root: string, documentId: string, title?: string): string {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(documentId)) {
    throw new SourceCreationError(400, "Document ID must start with a letter or number and contain only letters, numbers, underscores, or hyphens (at most 128 characters).");
  }
  const destination = resolve(root, `${title ? filenameStem(title) : documentId}.spec`);
  if (dirname(destination) !== resolve(root)) throw new SourceCreationError(400, "Document path escaped the configured root.");
  return destination;
}



/** Owns package creation receipts separately from immutable design bindings. */
export class SourceCreations {
  readonly root: string;
  private readonly reserving = new Set<string>();

  constructor(readonly state: ProductState, readonly owners: ServiceClients, root: string, private readonly reserve: Reserve, private readonly snapshots?: InstructionSnapshots) {
    this.root = resolve(root);
  }

  get(requestId: string): SourceCreationRequest {
    const request = this.state.getSourceCreation(requestId);
    if (!request) throw new SourceCreationError(404, "Unknown specification creation request.");
    if (!request.flowExecutionId) throw new SourceCreationError(410, "Spec creation requires a flow execution.");
    return request;
  }

  /** Restore a passive binding lost before native conversation creation, without creating a second file. */
  async restoreReservation(requestId: string): Promise<void> {
    const request = this.get(requestId);
    if (this.state.getBinding(request.destinationSessionId)) return;
    if (!request.sourceRevisionHash || !["created", "reserved", "bound"].includes(request.status)) throw new SourceCreationError(409, "No saved creation receipt is available.");
    this.state.storeSourceCreation({ ...request, status: "created", reservation: null });
    await this.create(requestId, { serviceBaseUrl: request.serviceBaseUrl, documentId: request.documentId, title: request.title });
  }

  async present(request: SourceCreationRequest): Promise<Record<string, unknown>> {
    const capabilities = await this.owners.capabilities();
    return { ...request, specDocumentRoot: this.root, pathSeparator: sep, services: capabilities.spec };
  }

  async prepare(input: { sourceSessionId: string; callId: string; originalRequest: string; preset: AssistantPreset;
    flowExecutionId: string; title?: string; documentId?: string; preferredOwner?: string; architectureReviewId?: string; empty?: boolean; independent?: boolean }): Promise<Record<string, unknown>> {
    const existing = this.state.sourceCreationForCall(input.sourceSessionId, input.callId);
    if (existing) return this.present(existing);
    const architecture = input.empty === true ? null : this.state.requireArchitecture(input.sourceSessionId, input.architectureReviewId);
    if (architecture) {
      const associated = this.state.sourceCreationForArchitecture(architecture.reviewId);
      if (associated) return this.present(associated);
      const binding = this.state.getBinding(input.sourceSessionId);
      if (binding && !input.independent) {
        const context = await this.owners.context(binding);
        if (typeof context.source_revision_hash !== "string" || context.document_id !== binding.documentId) throw new SourceCreationError(409, "Reread the source specification before architecture-based creation.");
        this.state.requireArchitecture(input.sourceSessionId, input.architectureReviewId, context.source_revision_hash);
      }
    }
    if (!input.originalRequest.trim()) throw new SourceCreationError(400, "The original designer request is unavailable. Submit the request again in this conversation.");
    let destinationDirectory = this.root;
    let bound = this.state.getBinding(input.sourceSessionId);
    if (bound?.domain === "circuit") {
      const source = await this.owners.circuitSourceBinding(bound);
      if (source && typeof source.source_owner_document_key === "string" && typeof source.source_document_id === "string" && typeof source.source_service_url === "string") {
        bound = { ...bound, domain: "spec", scope: "document", serviceUrl: source.source_service_url,
          serviceDocumentKey: source.source_owner_document_key, documentId: source.source_document_id };
      }
    }
    if (bound?.domain === "spec") {
      const snapshot = await this.owners.specSnapshot(bound);
      if (typeof snapshot.source_path !== "string") throw new SourceCreationError(502, "The bound Spec path is unavailable.");
      destinationDirectory = dirname(resolve(snapshot.source_path));
      const within = relative(this.root, destinationDirectory);
      if (within === ".." || within.startsWith(`..${sep}`) || resolve(this.root, within) !== destinationDirectory) throw new SourceCreationError(400, "The bound Spec is outside the configured Spec root.");
    }
    if (input.documentId !== undefined) specDestination(destinationDirectory, input.documentId.trim());
    const capabilities = await this.owners.capabilities();
    const services = capabilities.spec as Array<{ url: string; available: boolean }>;
    const selected = input.preferredOwner ? services.find(item => item.url === input.preferredOwner) : services.find(item => item.available) ?? services[0];
    if (input.independent && !selected?.available) throw new SourceCreationError(503, "The selected Spec service is unavailable; select another service explicitly.");
    if (!selected?.available) throw new SourceCreationError(503, "The selected Spec service is unavailable.");
    const policy = await this.owners.specPolicy(selected.url);
    if (!policy.creationReceipts) throw new SourceCreationError(422, "Spec flows require durable creation receipts.");
    const suggested = input.documentId?.trim();
    const documentId = suggested || `spec_${randomUUID().replaceAll("-", "").slice(0, 32)}`;
    const request: SourceCreationRequest = {
      requestId: randomUUID(), flowExecutionId: input.flowExecutionId, sourceSessionId: input.sourceSessionId, callId: input.callId,
      originalRequest: architecture?.originalRequest || input.originalRequest, preset: input.preset, status: "pending",
      ...(architecture ? { architectureReviewId: architecture.reviewId, acceptedArchitecture: architecture.plan } : {}),
      documentId, title: input.title?.trim() || "Untitled specification", serviceBaseUrl: selected?.url ?? "",
      destinationDirectory, destination: specDestination(destinationDirectory, documentId, input.title?.trim() || "Untitled specification"), destinationSessionId: randomUUID(),
      sourceRevisionHash: null, error: null, reservation: null,
      automatic: policy.approval_policy === "automatic",
      creationReceipts: policy.creationReceipts === true,
    };
    // Capabilities/policy reads can overlap retries with a new native tool-call ID.
    // One approved architecture continues its existing package creation receipt.
    const associated = architecture ? this.state.sourceCreationForArchitecture(architecture.reviewId) : null;
    if (associated) return this.present(associated);
    this.state.storeSourceCreation(request);
    return { ...request, specDocumentRoot: this.root, pathSeparator: sep, services };
  }

  markConversationBound(requestId: string): SourceCreationRequest {
    const request = this.get(requestId);
    if (request.status === "bound") return request;
    if (request.status !== "reserved" || this.state.getBinding(request.destinationSessionId)?.status !== "active") {
      throw new SourceCreationError(409, "Activate the Spec conversation before acknowledging its binding.");
    }
    const bound = { ...request, status: "bound" as const, error: null };
    this.state.storeSourceCreation(bound);
    return bound;
  }

  async create(requestId: string, values: { documentId: string; title: string; serviceBaseUrl: string }, signal?: AbortSignal): Promise<Record<string, unknown>> {
    signal?.throwIfAborted();
    let request = this.get(requestId);
    if (request.architectureReviewId) {
      const architecture = this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId);
      const source = this.state.getBinding(request.sourceSessionId);
      if (source && architecture.sourceRevision) {
        const context = await this.owners.context(source, signal);
        if (typeof context.source_revision_hash !== "string" || context.document_id !== source.documentId) throw new SourceCreationError(409, "Dependent creation requires fresh source context.");
        this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId, context.source_revision_hash);
      }
    }
    if (request.status === "uncertain" && request.creationReceipts) {
      if (values.documentId.trim() !== request.documentId || values.title.trim() !== request.title
          || values.serviceBaseUrl.replace(/\/$/, "") !== request.serviceBaseUrl) {
        throw new SourceCreationError(409, "Retry uncertain creation with exactly the saved request details.");
      }
      if (!(await this.owners.specPolicy(request.serviceBaseUrl)).creationReceipts) {
        throw new SourceCreationError(409, "The Spec service cannot replay this creation receipt safely.");
      }
      if (!this.state.retrySourceCreation(request)) throw new SourceCreationError(409, "Creation retry is already in progress. Refresh flow progress.");
      request = this.get(requestId);
    }
    if (["cancelled", "uncertain", "creating"].includes(request.status)) {
      throw new SourceCreationError(409, request.error ?? `This creation request is ${request.status}. Refresh flow progress to see its current state.`);
    }
    if (request.status === "pending") {
      const documentId = values.documentId.trim();
      const title = values.title.trim();
      if (!title) throw new SourceCreationError(400, "Spec title is required.");
      const destination = specDestination(request.destinationDirectory || this.root, documentId, title);
      let serviceBaseUrl: string;
      try { serviceBaseUrl = normalizeSpecUrl(values.serviceBaseUrl, this.owners.specAllowlist); }
      catch (error) { throw new SourceCreationError(400, error instanceof Error ? error.message : String(error)); }
      const capabilities = await this.owners.capabilities();
      const available = (capabilities.spec as Array<{ url: string; available: boolean }>).find(item => item.url === serviceBaseUrl);
      if (!available?.available) throw new SourceCreationError(503, "The selected Spec service is offline. Start it and retry the flow.");
      const policy = await this.owners.specPolicy(serviceBaseUrl);
      if (!policy.creationReceipts) throw new SourceCreationError(422, "Spec flows require durable creation receipts.");
      request = { ...request, documentId, title, destination, serviceBaseUrl, error: null,
        creationReceipts: policy.creationReceipts === true };
      if (!this.state.claimSourceCreation(request)) throw new SourceCreationError(409, "This creation request changed concurrently. Refresh flow progress.");
      request = { ...request, status: "creating" };
      try {
        const snapshot = await this.owners.createSpec(serviceBaseUrl, destination, documentId, title, request.requestId, signal);
        if (snapshot.document_id !== documentId || typeof snapshot.source_revision_hash !== "string" || !snapshot.source_revision_hash
          || typeof snapshot.owner_document_key !== "string" || !snapshot.owner_document_key
          || typeof snapshot.source_path !== "string" || !snapshot.source_path || dirname(resolve(snapshot.source_path)) !== (request.destinationDirectory || this.root)) {
          throw new ServiceError(502, "The creation receipt must identify the requested Spec, saved path, service document key and source revision.", true);
        }
        request = { ...request, status: "created", sourceRevisionHash: snapshot.source_revision_hash,
          destination: snapshot.source_path,
          serviceDocumentKey: snapshot.owner_document_key,
          editContextId: typeof (snapshot.edit_access as Record<string, unknown> | undefined)?.context_id === "string" ? (snapshot.edit_access as Record<string, unknown>).context_id as string : undefined };
        this.state.storeSourceCreation(request);
      } catch (error) {
        const uncertain = !(error instanceof ServiceError) || error.uncertain;
        const details = error instanceof Error ? error.message : String(error);
        this.state.storeSourceCreation({ ...request, status: uncertain ? "uncertain" : "pending",
          error: uncertain ? (request.creationReceipts
            ? `${details} Creation may have succeeded. Retry the same request to recover its durable receipt.`
            : `${details} Creation may have succeeded. Check ${destination} in the Spec Editor; this request will not be repeated automatically.`) : details });
        throw error;
      }
    } else if (values.documentId.trim() !== request.documentId || values.title.trim() !== request.title
      || values.serviceBaseUrl.replace(/\/$/, "") !== request.serviceBaseUrl) {
      throw new SourceCreationError(409, "The package is already saved. Resume with the saved details recorded in the flow.");
    }

    if (request.status === "created") {
      if (this.reserving.has(requestId)) throw new SourceCreationError(409, "Conversation setup is already in progress. Refresh flow progress shortly.");
      this.reserving.add(requestId);
      try {
        const stored = this.state.getBinding(request.destinationSessionId);
        let reservation: Reservation;
        if (stored) {
          if (stored.domain !== "spec" || stored.documentId !== request.documentId || stored.serviceUrl !== request.serviceBaseUrl) {
            throw new SourceCreationError(409, "The reserved conversation does not match the created specification.");
          }
          reservation = { session: stored, workspace: {
            key: stored.workspaceKey, title: stored.workspaceTitle, path: stored.workspacePath,
            domain: stored.workspaceDomain, serviceUrl: stored.workspaceServiceUrl, documentId: stored.workspaceDocumentId,
          } };
        } else {
          this.snapshots?.pin(request.destinationSessionId, request.sourceSessionId);
          const result = await this.reserve({ domain: "spec", serviceBaseUrl: request.serviceBaseUrl,
            documentId: request.documentId, serviceDocumentKey: request.serviceDocumentKey, editContextId: request.editContextId, title: request.title, scope: "document", preset: request.preset }, request.destinationSessionId, request.sourceSessionId);
          reservation = { session: result.binding, workspace: result.workspace };
        }
        if (request.architectureReviewId) {
          const architecture = this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId);
          this.state.storeArchitecture({ ...architecture, destinationSessionId: request.destinationSessionId,
            destinationSourceRevision: request.sourceRevisionHash, destinationServiceDocumentKey: request.serviceDocumentKey ?? null,
            destinationDocumentId: request.documentId });
        }
        request = { ...request, status: "reserved", reservation, error: null };
        this.state.storeSourceCreation(request);
      } catch (error) {
        this.state.storeSourceCreation({ ...request, error: `The package was saved at ${request.destination}, but conversation setup failed: ${error instanceof Error ? error.message : String(error)}. Reopen that package in the Spec Editor if necessary, then retry the flow.` });
        throw error;
      } finally { this.reserving.delete(requestId); }
    }
    return { ...request.reservation, creation_request: await this.present(request),
 };
  }
}
