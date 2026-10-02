/** Recoverable Spec package creation and separate continuation-chat reservation.
 * Persist exact request inputs/progress before owner calls. Package creation and
 * native chat creation are separate side effects; uncertainty needs receipt
 * reconciliation using stable identities rather than a second package request. */
import { randomUUID } from "node:crypto";
import { dirname, resolve, sep } from "node:path";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { snapshotJsonValue, type JsonValue } from "@deepseek-ai/dsh-util-values";
import { normalizeSpecUrl, OwnerClients, OwnerError } from "./owner-clients.js";
import { ProductState } from "./state.js";
import type { AssistantPreset, BindingInput, SourceCreationRequest, SessionBinding, WorkspaceDescriptor } from "./types.js";

type Reservation = { session: SessionBinding; workspace: WorkspaceDescriptor };
type Reserve = (input: BindingInput, sessionId?: string) => Promise<{ binding: SessionBinding; workspace: WorkspaceDescriptor }>;

export class SourceCreationError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

export function specDestination(root: string, documentId: string): string {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(documentId)) {
    throw new SourceCreationError(400, "Document ID must start with a letter or number and contain only letters, numbers, underscores, or hyphens (at most 128 characters).");
  }
  const destination = resolve(root, `${documentId}.spec`);
  if (dirname(destination) !== resolve(root)) throw new SourceCreationError(400, "Document path escaped the configured root.");
  return destination;
}

export function creationContinuation(request: SourceCreationRequest): string {
  return `The specification package has already been created and this chat is bound to it.\n`
    + `Document: ${request.documentId}\nTitle: ${request.title}\nSaved at: ${request.destination}\n\n`
    + `Original user request:\n${request.originalRequest}\n\n`
    + (request.architectureReviewId ? `Approved architecture_review_id: ${request.architectureReviewId}\nAccepted architecture:\n${JSON.stringify(request.acceptedArchitecture)}\nUse this review ID in the initial content proposal.\n\n` : "")
    + `Continue by fulfilling the requested contents in the already-created bound document. Do not create another package or call prepare_spec_document_creation for this request. Read get_bound_context and submit contents according to the owner approval policy. If the request only asked for an empty specification, confirm that it is ready without preparing a content proposal.`;
}

/** Owns package creation receipts separately from immutable design bindings. */
export class SourceCreations {
  readonly root: string;
  private readonly reserving = new Set<string>();

  constructor(readonly state: ProductState, readonly owners: OwnerClients, root: string, private readonly reserve: Reserve) {
    this.root = resolve(root);
  }

  get(requestId: string): SourceCreationRequest {
    const request = this.state.getSourceCreation(requestId);
    if (!request) throw new SourceCreationError(404, "Unknown specification creation request.");
    return request;
  }

  async present(request: SourceCreationRequest): Promise<Record<string, unknown>> {
    const capabilities = await this.owners.capabilities();
    return { ...request, specDocumentRoot: this.root, pathSeparator: sep, services: capabilities.spec,
      ...(request.reservation ? { continuation: { requestId: request.continuationRequestId,
        message: creationContinuation(request), sent: request.status === "continued" } } : {}) };
  }

  async prepare(input: { sourceSessionId: string; callId: string; originalRequest: string; preset: AssistantPreset;
    title?: string; documentId?: string; preferredOwner?: string; architectureReviewId?: string; empty?: boolean }): Promise<Record<string, unknown>> {
    const existing = this.state.sourceCreationForCall(input.sourceSessionId, input.callId);
    if (existing) return this.present(existing);
    const architecture = input.empty === true ? null : this.state.requireArchitecture(input.sourceSessionId, input.architectureReviewId);
    if (architecture) {
      const associated = this.state.sourceCreationForArchitecture(architecture.reviewId);
      if (associated) return this.present(associated);
      const binding = this.state.getBinding(input.sourceSessionId);
      if (binding) {
        const context = await this.owners.context(binding);
        if (typeof context.source_revision_hash !== "string" || context.document_id !== binding.documentId) throw new SourceCreationError(409, "Reread the source specification before architecture-based creation.");
        this.state.requireArchitecture(input.sourceSessionId, input.architectureReviewId, context.source_revision_hash);
      }
    }
    if (!input.originalRequest.trim()) throw new SourceCreationError(400, "The original user request is unavailable. Submit the request again in this chat.");
    const capabilities = await this.owners.capabilities();
    const services = capabilities.spec as Array<{ url: string; available: boolean }>;
    const selected = services.find(item => item.url === input.preferredOwner && item.available)
      ?? services.find(item => item.available) ?? services[0];
    const policy = selected ? await this.owners.specPolicy(selected.url) : { approval_policy: "review", creationReceipts: false };
    const suggested = input.documentId?.trim();
    const documentId = suggested && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(suggested)
      ? suggested : `spec_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
    const request: SourceCreationRequest = {
      requestId: randomUUID(), sourceSessionId: input.sourceSessionId, callId: input.callId,
      originalRequest: architecture?.originalRequest || input.originalRequest, preset: input.preset, status: "pending",
      ...(architecture ? { architectureReviewId: architecture.reviewId, acceptedArchitecture: architecture.plan } : {}),
      documentId, title: input.title?.trim() || "Untitled specification", serviceBaseUrl: selected?.url ?? "",
      destination: specDestination(this.root, documentId), destinationSessionId: randomUUID(),
      continuationRequestId: randomUUID(), sourceRevisionHash: null, error: null, reservation: null,
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

  cancel(requestId: string): SourceCreationRequest {
    const request = this.get(requestId);
    if (request.status === "cancelled") return request;
    if (request.status !== "pending") throw new SourceCreationError(409, "Creation has already started. A saved package cannot be cancelled from this card.");
    if (!this.state.cancelSourceCreation(request)) throw new SourceCreationError(409, "Creation started while cancelling. Reload the card to see its current state.");
    return this.get(requestId);
  }

  continued(requestId: string): SourceCreationRequest {
    const request = this.get(requestId);
    if (request.status === "continued") return request;
    if (request.status !== "reserved" || this.state.getBinding(request.destinationSessionId)?.status !== "active") {
      throw new SourceCreationError(409, "Activate the specification chat before acknowledging its continuation.");
    }
    const continued = { ...request, status: "continued" as const, error: null };
    this.state.storeSourceCreation(continued);
    return continued;
  }

  async create(requestId: string, values: { documentId: string; title: string; serviceBaseUrl: string }): Promise<Record<string, unknown>> {
    let request = this.get(requestId);
    if (request.architectureReviewId) {
      this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId);
      const source = this.state.getBinding(request.sourceSessionId);
      if (request.status === "pending" && source) {
        const context = await this.owners.context(source);
        if (context.document_id !== source.documentId || typeof context.source_revision_hash !== "string") throw new SourceCreationError(409, "The architecture's source context is unavailable or incomplete.");
        this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId, context.source_revision_hash);
      }
    }
    if (request.status === "uncertain" && request.creationReceipts) {
      if (values.documentId.trim() !== request.documentId || values.title.trim() !== request.title
          || values.serviceBaseUrl.replace(/\/$/, "") !== request.serviceBaseUrl) {
        throw new SourceCreationError(409, "Retry uncertain creation with exactly the saved request details.");
      }
      if (!(await this.owners.specPolicy(request.serviceBaseUrl)).creationReceipts) {
        throw new SourceCreationError(409, "The owner cannot replay this creation receipt safely.");
      }
      if (!this.state.retrySourceCreation(request)) throw new SourceCreationError(409, "Creation retry is already in progress. Reload the card.");
      request = this.get(requestId);
    }
    if (["cancelled", "uncertain", "creating"].includes(request.status)) {
      throw new SourceCreationError(409, request.error ?? `This creation request is ${request.status}. Reload the card to see its current state.`);
    }
    if (request.status === "pending") {
      const documentId = values.documentId.trim();
      const title = values.title.trim();
      if (!title) throw new SourceCreationError(400, "Specification title is required.");
      const destination = specDestination(this.root, documentId);
      let serviceBaseUrl: string;
      try { serviceBaseUrl = normalizeSpecUrl(values.serviceBaseUrl, this.owners.specAllowlist); }
      catch (error) { throw new SourceCreationError(400, error instanceof Error ? error.message : String(error)); }
      const capabilities = await this.owners.capabilities();
      const available = (capabilities.spec as Array<{ url: string; available: boolean }>).find(item => item.url === serviceBaseUrl);
      if (!available?.available) throw new SourceCreationError(503, "The selected Spec service is offline. Start it and retry this card.");
      const policy = await this.owners.specPolicy(serviceBaseUrl);
      request = { ...request, documentId, title, destination, serviceBaseUrl, error: null,
        creationReceipts: policy.creationReceipts === true };
      if (!this.state.claimSourceCreation(request)) throw new SourceCreationError(409, "This creation request changed concurrently. Reload the card.");
      request = { ...request, status: "creating" };
      try {
        const snapshot = await this.owners.createSpec(serviceBaseUrl, destination, documentId, title, request.requestId);
        if (snapshot.document_id !== documentId || typeof snapshot.source_revision_hash !== "string") {
          throw new OwnerError(502, "The owner creation response did not identify the requested specification.", true);
        }
        request = { ...request, status: "created", sourceRevisionHash: snapshot.source_revision_hash,
          ownerDocumentKey: typeof snapshot.owner_document_key === "string" ? snapshot.owner_document_key : undefined };
        this.state.storeSourceCreation(request);
      } catch (error) {
        const uncertain = !(error instanceof OwnerError) || error.uncertain;
        const details = error instanceof Error ? error.message : String(error);
        this.state.storeSourceCreation({ ...request, status: uncertain ? "uncertain" : "pending",
          error: uncertain ? (request.creationReceipts
            ? `${details} Creation may have succeeded. Retry the same request to recover its durable receipt.`
            : `${details} Creation may have succeeded. Check ${destination} in the Spec Editor; this request will not be repeated automatically.`) : details });
        throw error;
      }
    } else if (values.documentId.trim() !== request.documentId || values.title.trim() !== request.title
      || values.serviceBaseUrl.replace(/\/$/, "") !== request.serviceBaseUrl) {
      throw new SourceCreationError(409, "The package is already saved. Resume with the saved details shown in the card.");
    }

    if (request.status === "created") {
      if (this.reserving.has(requestId)) throw new SourceCreationError(409, "Chat setup is already in progress. Reload the card shortly.");
      this.reserving.add(requestId);
      try {
        const stored = this.state.getBinding(request.destinationSessionId);
        let reservation: Reservation;
        if (stored) {
          if (stored.domain !== "spec" || stored.documentId !== request.documentId || stored.ownerUrl !== request.serviceBaseUrl) {
            throw new SourceCreationError(409, "The reserved chat does not match the created specification.");
          }
          reservation = { session: stored, workspace: {
            key: stored.workspaceKey, title: stored.workspaceTitle, path: stored.workspacePath,
            domain: stored.workspaceDomain, ownerUrl: stored.workspaceOwnerUrl, documentId: stored.workspaceDocumentId,
          } };
        } else {
          const result = await this.reserve({ domain: "spec", serviceBaseUrl: request.serviceBaseUrl,
            documentId: request.documentId, ownerDocumentKey: request.ownerDocumentKey, title: request.title, scope: "document", preset: request.preset }, request.destinationSessionId);
          reservation = { session: result.binding, workspace: result.workspace };
        }
        if (request.architectureReviewId) {
          const architecture = this.state.requireArchitecture(request.sourceSessionId, request.architectureReviewId);
          this.state.storeArchitecture({ ...architecture, destinationSessionId: request.destinationSessionId,
            destinationSourceRevision: request.sourceRevisionHash, destinationOwnerDocumentKey: request.ownerDocumentKey ?? null,
            destinationDocumentId: request.documentId });
        }
        request = { ...request, status: "reserved", reservation, error: null };
        this.state.storeSourceCreation(request);
      } catch (error) {
        this.state.storeSourceCreation({ ...request, error: `The package was saved at ${request.destination}, but chat setup failed: ${error instanceof Error ? error.message : String(error)}. Reopen that package in the Spec Editor if necessary, then retry this card.` });
        throw error;
      } finally { this.reserving.delete(requestId); }
    }
    return { ...request.reservation, creation_request: await this.present(request),
      continuation: { requestId: request.continuationRequestId, message: creationContinuation(request), sent: request.status === "continued" } };
  }
}

export const SOURCE_CREATION_PROMPT = `NEW SPECIFICATION PACKAGES
When the user explicitly asks for a new specification document/package, obtain an approved architecture review first, then call prepare_spec_document_creation with architecture_review_id. For an explicitly empty specification use empty=true. The tool creates it automatically when the selected owner allows automatic submission; restricted owners show an editable creation card. This applies even when no package is open or current context is unavailable. Do not read get_bound_context first for a new-package request. Suggest a title and document ID derived from the request. A saved receipt creates a separate document chat carrying the original request there. Do not claim contents are complete before owner application. Creating a component or design inside the current document uses get_bound_context and prepare_spec_proposal. A creation receipt in a new chat means the package already exists: populate it, do not create another package.`;

export function registerSourceCreationTool(
  agent: { ctx: { tools: { register(tool: unknown): () => void }; systemPrompt?: { section(value: unknown): () => void } } },
  creations: SourceCreations,
  currentRequest: () => { sourceSessionId: string; originalRequest: string; preset: AssistantPreset; preferredOwner?: string },
): void {
  agent.ctx.systemPrompt?.section({ name: "spec2gds:source-creation", order: 175, text: SOURCE_CREATION_PROMPT });
  agent.ctx.tools.register(defineTool({
    name: "prepare_spec_document_creation",
    description: "Create a NEW specification with available defaults under the owner's automatic policy, or prepare a confirmation card when human approval is required. Preserve the original request for a separate document-bound chat. Use before a bound-context read for a new-package request.",
    parameters: { title: { type: "string" }, document_id: { type: "string" }, architecture_review_id: { type: "string" }, empty: { type: "boolean" } },
    output: { schema: { type: "json" }, render: (_args: unknown, value: unknown) => [{ type: "text", text: JSON.stringify(value) }] },
    timeoutMs: 35_000,
    async execute(args, exec) {
      try {
        const creation = await creations.prepare({ ...currentRequest(), callId: String(exec.callId), title: args.title, documentId: args.document_id,
          architectureReviewId: args.architecture_review_id, empty: args.empty });
        if (creation.automatic === true) {
          const policy = await creations.owners.specPolicy(String(creation.serviceBaseUrl), exec.signal);
          if (policy.approval_policy !== "automatic") throw new SourceCreationError(409, "The owner now requires human approval. Prepare a new creation request.");
          const reserved = await creations.create(String(creation.requestId), {
            documentId: String(creation.documentId), title: String(creation.title), serviceBaseUrl: String(creation.serviceBaseUrl),
          });
          return snapshotJsonValue({ source_creation: reserved.creation_request,
            instruction: "The owner saved the new package with the suggested defaults. Its document chat will continue the original request automatically; do not claim its contents have been applied yet." }) as JsonValue;
        }
        return snapshotJsonValue({ source_creation: creation, instruction: "The creation card is ready. Ask the user to review it and select Create specification and continue. No package or contents have been created yet." }) as JsonValue;
      } catch (error) {
        return { creation_error: error instanceof Error ? error.message : String(error), instruction: "Explain why the creation card could not be prepared; do not claim a package was created." };
      }
    },
  }));
}
