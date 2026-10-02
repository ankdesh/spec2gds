/** Versioned HTTP client for Circuit owner operations and event subscriptions.
 * Transport success is distinct from an accepted domain result. Callers retain
 * expected revisions, lease identities and request IDs across retries; this
 * adapter does not grant a fresh revision after a conflict. */
import {
  validateContractDefinition,
  type CircuitChangeResult,
  type CircuitConstruction,
  type CircuitDesignerBackend,
  type CircuitDocument,
  type CircuitExport,
  type CircuitExportOptions,
  type CircuitOperationBatch,
  type CircuitProposal,
  type CircuitProposalCreateRequest,
  type CircuitSnapshot,
  type CircuitSourceBindingV1,
  type CircuitSourceSyncResponse,
  type CircuitDesignerPreferencesV1,
  type ComponentDefinition,
  type ComponentQuery,
  type DocumentSummary,
  type EditLease,
  type ProposalDecision,
  type ProviderCommitRequest,
  type ProviderCommitResult,
  type ResolvedComponentDesign,
  type ServiceError,
  type ServiceEvent,
  type SubgraphQuery,
  isCircuitSourceBindingV1,
  validateCircuitDesignerPreferences,
} from "@spec2gds/circuit-core";

export type CircuitFetch = (input: string, init?: RequestInit) => Promise<Response>;

export class CircuitDesignerHttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
    this.name = "CircuitDesignerHttpError";
  }
}

export interface HttpCircuitDesignerOptions {
  baseUrl?: string;
  fetch?: CircuitFetch;
}

export interface CircuitPreferencesResponse {
  preferences: CircuitDesignerPreferencesV1;
  persisted: boolean;
}

export interface CircuitServiceCapabilities {
  schema_version: 1;
  service: "circuit_designer";
  api_version: "v1";
  capabilities: string[];
  integrations: {
    service_directory: boolean;
    callback_provider_allowlist: string[];
  };
}

export type { CircuitSourceBindingV1, CircuitSourceSyncResponse } from "@spec2gds/circuit-core";

/** Versioned HTTP implementation of the common independent backend contract. */
export class HttpCircuitDesignerBackend implements CircuitDesignerBackend {
  readonly baseUrl: string;
  readonly fetch: CircuitFetch;

  constructor(options: HttpCircuitDesignerOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "/api/circuit-designer/v1").replace(/\/$/, "");
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async create(document: CircuitDocument, requestId: string): Promise<CircuitChangeResult> {
    return this.change(await this.sendJson(`${this.baseUrl}/documents`, "POST", { request_id: requestId, document }));
  }

  async listDocuments(): Promise<DocumentSummary[]> {
    const value = await this.getJson(`${this.baseUrl}/documents`) as { documents?: DocumentSummary[] };
    if (!Array.isArray(value.documents)) throw new Error("Circuit service returned an invalid document list.");
    return value.documents;
  }

  async get(documentId: string): Promise<CircuitSnapshot> {
    return this.validated("CircuitSnapshot", await this.getJson(this.documentUrl(documentId))) as CircuitSnapshot;
  }

  async getPreferences(): Promise<CircuitPreferencesResponse> {
    return this.preferencesResponse(await this.getJson(`${this.baseUrl}/preferences`));
  }

  async getCapabilities(): Promise<CircuitServiceCapabilities> {
    return await this.getJson(`${this.baseUrl}/capabilities`) as CircuitServiceCapabilities;
  }

  async putPreferences(preferences: CircuitDesignerPreferencesV1): Promise<CircuitPreferencesResponse> {
    return this.preferencesResponse(await this.sendJson(`${this.baseUrl}/preferences`, "PUT", preferences));
  }

  async replace(
    documentId: string,
    document: CircuitDocument,
    expectedRevision: string,
    requestId: string,
  ): Promise<CircuitChangeResult> {
    return this.change(await this.sendJson(this.documentUrl(documentId), "PUT", {
      request_id: requestId,
      expected_revision: expectedRevision,
      document,
    }));
  }

  async validateConstruction(construction: CircuitConstruction): Promise<CircuitChangeResult> {
    return this.change(await this.sendJson(`${this.baseUrl}/constructions/validate`, "POST", construction));
  }

  async preview(documentId: string, batch: CircuitOperationBatch): Promise<CircuitChangeResult> {
    return this.change(await this.sendJson(`${this.documentUrl(documentId)}/operations/preview`, "POST", batch));
  }

  async commit(documentId: string, batch: CircuitOperationBatch, leaseId?: string): Promise<CircuitChangeResult> {
    return this.change(await this.sendJson(`${this.documentUrl(documentId)}/operations/commit`, "POST", {
      batch,
      ...(leaseId ? { lease_id: leaseId } : {}),
    }));
  }

  async getSourceBinding(documentId: string): Promise<CircuitSourceBindingV1 | undefined> {
    try {
      const value = await this.getJson(`${this.documentUrl(documentId)}/source-binding`);
      if (!isCircuitSourceBindingV1(value)) throw new Error("Circuit service returned invalid source-binding metadata.");
      return value;
    } catch (reason) {
      if (reason instanceof CircuitDesignerHttpError && reason.status === 404) return undefined;
      throw reason;
    }
  }

  async previewSource(
    documentId: string,
    batch: CircuitOperationBatch,
    leaseId: string,
  ): Promise<CircuitSourceSyncResponse> {
    return await this.sendJson(`${this.documentUrl(documentId)}/source/preview`, "POST", {
      batch,
      lease_id: leaseId,
    }) as CircuitSourceSyncResponse;
  }

  async commitSource(
    documentId: string,
    batch: CircuitOperationBatch,
    leaseId: string,
    proposalId?: string,
  ): Promise<CircuitSourceSyncResponse> {
    return await this.sendJson(`${this.documentUrl(documentId)}/source/commit`, "POST", {
      batch,
      lease_id: leaseId,
      ...(proposalId ? { proposal_id: proposalId } : {}),
    }) as CircuitSourceSyncResponse;
  }

  async reloadSource(documentId: string): Promise<CircuitSourceSyncResponse> {
    return await this.sendJson(`${this.documentUrl(documentId)}/source/reload`, "POST", {}) as CircuitSourceSyncResponse;
  }

  async getLease(documentId: string): Promise<EditLease | null> {
    const value = await this.getJson(`${this.documentUrl(documentId)}/lock`) as { lease: EditLease | null };
    if (value.lease) this.validated("EditLease", value.lease);
    return value.lease;
  }

  async acquireLease(documentId: string, ownerId: string, ttlSeconds = 900): Promise<EditLease> {
    return this.validated("EditLease", await this.sendJson(`${this.documentUrl(documentId)}/lock`, "POST", {
      owner_id: ownerId,
      ttl_seconds: ttlSeconds,
    })) as EditLease;
  }

  async renewLease(documentId: string, leaseId: string, ttlSeconds = 900): Promise<EditLease> {
    return this.validated("EditLease", await this.sendJson(
      `${this.documentUrl(documentId)}/lock/${encodeURIComponent(leaseId)}`,
      "PUT",
      { ttl_seconds: ttlSeconds },
    )) as EditLease;
  }

  async releaseLease(documentId: string, leaseId: string): Promise<void> {
    await this.sendJson(`${this.documentUrl(documentId)}/lock/${encodeURIComponent(leaseId)}`, "DELETE");
  }

  async summary(documentId: string): Promise<DocumentSummary> {
    return this.validated("DocumentSummary", await this.getJson(`${this.documentUrl(documentId)}/summary`)) as DocumentSummary;
  }

  async lookupComponents(documentId: string, query: ComponentQuery = {}): Promise<ComponentDefinition[]> {
    const parameters = new URLSearchParams();
    if (query.text) parameters.set("text", query.text);
    if (query.origin) parameters.set("origin", query.origin);
    const suffix = parameters.size ? `?${parameters}` : "";
    const result = await this.getJson(`${this.documentUrl(documentId)}/components${suffix}`) as { components: ComponentDefinition[] };
    result.components.forEach((component) => this.validated("ComponentDefinition", component));
    return result.components;
  }

  async subgraph(documentId: string, query: SubgraphQuery): Promise<CircuitDocument> {
    return this.validated("CircuitDocument", await this.sendJson(
      `${this.documentUrl(documentId)}/queries/subgraph`,
      "POST",
      query,
    )) as CircuitDocument;
  }

  async export(documentId: string, options: CircuitExportOptions): Promise<CircuitExport> {
    const response = await this.fetch(`${this.documentUrl(documentId)}/exports`, {
      method: "POST",
      headers: { Accept: this.acceptFor(options.format), "Content-Type": "application/json" },
      body: JSON.stringify(options),
    });
    if (!response.ok) await this.throwResponse(response);
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename = disposition.match(/filename="?([^"]+)"?/)?.[1] ?? `${documentId}.${options.format}`;
    return {
      media_type: this.acceptFor(options.format),
      filename,
      data: options.format === "png" ? new Uint8Array(await response.arrayBuffer()) : await response.text(),
    };
  }

  async listProposals(documentId: string): Promise<CircuitProposal[]> {
    const value = await this.getJson(`${this.documentUrl(documentId)}/proposals`) as { proposals: CircuitProposal[] };
    value.proposals.forEach((proposal) => this.validated("CircuitProposal", proposal));
    return value.proposals;
  }

  async submitProposal(proposal: CircuitProposalCreateRequest): Promise<CircuitProposal> {
    return this.validated("CircuitProposal", await this.sendJson(
      `${this.documentUrl(proposal.document_id)}/proposals`,
      "POST",
      proposal,
    )) as CircuitProposal;
  }

  async decideProposal(
    documentId: string,
    proposalId: string,
    decision: ProposalDecision,
  ): Promise<CircuitChangeResult | undefined> {
    const value = await this.sendJson(
      `${this.documentUrl(documentId)}/proposals/${encodeURIComponent(proposalId)}/decision`,
      "POST",
      { decision },
    );
    return value ? this.change(value) : undefined;
  }

  async resolveComponentDesign(documentId: string, componentId: string): Promise<ResolvedComponentDesign> {
    return this.validated("ResolvedComponentDesign", await this.sendJson(
      `${this.documentUrl(documentId)}/components/${encodeURIComponent(componentId)}/resolve`,
      "POST",
      {},
    )) as ResolvedComponentDesign;
  }

  async commitComponentDesign(
    documentId: string,
    componentId: string,
    request: ProviderCommitRequest,
  ): Promise<ProviderCommitResult> {
    return this.validated("ProviderCommitResult", await this.sendJson(
      `${this.documentUrl(documentId)}/components/${encodeURIComponent(componentId)}/commit`,
      "POST",
      request,
    )) as ProviderCommitResult;
  }

  async registerProviderCallback(
    documentId: string,
    callbackUrl: string,
    allowNonLoopback = false,
  ): Promise<void> {
    await this.sendJson(`${this.documentUrl(documentId)}/provider`, "PUT", {
      callback_url: callbackUrl,
      allow_non_loopback: allowNonLoopback,
    });
  }

  /** SSE is invalidation-only: callers refetch snapshots after relevant events. */
  subscribe(documentId: string, onEvent: (event: ServiceEvent) => void): () => void {
    const source = new EventSource(`${this.documentUrl(documentId)}/events`);
    source.onmessage = (message) => {
      const value = JSON.parse(message.data) as unknown;
      if (validateContractDefinition("ServiceEvent", value).valid) onEvent(value as ServiceEvent);
    };
    return () => source.close();
  }

  private documentUrl(documentId: string): string {
    if (!documentId) throw new TypeError("documentId is required.");
    return `${this.baseUrl}/documents/${encodeURIComponent(documentId)}`;
  }

  private async getJson(url: string): Promise<unknown> {
    const response = await this.fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) await this.throwResponse(response);
    return response.json();
  }

  private async sendJson(
    url: string,
    method: "POST" | "PUT" | "DELETE",
    body?: unknown,
  ): Promise<unknown> {
    const response = await this.fetch(url, {
      method,
      headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) await this.throwResponse(response);
    if (response.status === 204) return undefined;
    return response.json();
  }

  private async throwResponse(response: Response): Promise<never> {
    const body = await response.json().catch(() => undefined) as ServiceError | undefined;
    throw new CircuitDesignerHttpError(
      body?.message || response.statusText || `Circuit Designer request failed (${response.status}).`,
      response.status,
      body,
    );
  }

  private validated(definition: string, value: unknown): unknown {
    const validation = validateContractDefinition(definition, value);
    if (!validation.valid) {
      throw new CircuitDesignerHttpError(`Server returned an invalid ${definition}.`, 502, validation.errors);
    }
    return value;
  }

  private change(value: unknown): CircuitChangeResult {
    return this.validated("CircuitChangeResult", value) as CircuitChangeResult;
  }

  private preferencesResponse(value: unknown): CircuitPreferencesResponse {
    if (!value || typeof value !== "object") {
      throw new CircuitDesignerHttpError("Server returned invalid Circuit Designer preferences.", 502, value);
    }
    const response = value as { preferences?: unknown; persisted?: unknown };
    const checked = validateCircuitDesignerPreferences(response.preferences);
    if (!checked.valid || typeof response.persisted !== "boolean") {
      throw new CircuitDesignerHttpError(
        checked.valid ? "Server returned an invalid preference persistence state." : checked.message,
        502,
        value,
      );
    }
    return { preferences: checked.preferences, persisted: response.persisted };
  }

  private acceptFor(format: CircuitExportOptions["format"]): CircuitExport["media_type"] {
    if (format === "json") return "application/json";
    if (format === "svg") return "image/svg+xml";
    return "image/png";
  }
}

/** Old name retained only as a source-level alias during the React migration. */
export { HttpCircuitDesignerBackend as HttpCircuitDesignerReadApi };
