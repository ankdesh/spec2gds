import {
  type AgentProposal,
  type ChangePreview,
  type CircuitDesignerApi,
  type CircuitDesignerReadOptions,
  type CircuitDesignCatalog,
  type CircuitGraphSnapshot,
  type CircuitHistoryResult,
  type CircuitHistoryStatus,
  type CommandBatch,
  type EditLease,
  validateCatalog,
  validateContractDefinition,
  validateGraph,
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

/** HTTP implementation of the common read API; it contains no React or ELK concerns. */
export class HttpCircuitDesignerReadApi implements CircuitDesignerApi {
  readonly baseUrl: string;
  readonly fetch: CircuitFetch;

  constructor(options: HttpCircuitDesignerOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "/api/circuit-designer").replace(/\/$/, "");
    this.fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async getCatalog(options: CircuitDesignerReadOptions = {}): Promise<CircuitDesignCatalog> {
    const value = await this.getJson(`${this.baseUrl}/catalog`, options.signal);
    const validation = validateCatalog(value);
    if (!validation.valid) throw new CircuitDesignerHttpError("Server returned an invalid circuit catalog.", 502, validation.errors);
    return value as CircuitDesignCatalog;
  }

  async getGraph(designId: string, options: CircuitDesignerReadOptions = {}): Promise<CircuitGraphSnapshot> {
    if (!designId) throw new TypeError("designId is required.");
    const value = await this.getJson(`${this.baseUrl}/designs/${encodeURIComponent(designId)}`, options.signal);
    const validation = validateGraph(value);
    if (!validation.valid) throw new CircuitDesignerHttpError("Server returned an invalid circuit graph.", 502, validation.errors);
    return value as CircuitGraphSnapshot;
  }

  async getLease(options: CircuitDesignerReadOptions = {}): Promise<EditLease | null> {
    const value = await this.getJson(`${this.baseUrl}/lease`, options.signal) as { lease: EditLease | null };
    if (value.lease) this.validated("EditLease", value.lease);
    return value.lease;
  }

  async acquireLease(ownerId: string, ownerKind: "human" | "agent", ttlSeconds = 300): Promise<EditLease> {
    return this.validated("EditLease", await this.sendJson(`${this.baseUrl}/lease`, "POST", { owner_id: ownerId, owner_kind: ownerKind, ttl_seconds: ttlSeconds })) as EditLease;
  }

  async releaseLease(leaseId: string): Promise<void> {
    await this.sendJson(`${this.baseUrl}/lease/${encodeURIComponent(leaseId)}`, "DELETE");
  }

  async preview(batch: CommandBatch): Promise<ChangePreview> {
    return this.validated("ChangePreview", await this.sendJson(`${this.baseUrl}/commands/preview`, "POST", batch)) as ChangePreview;
  }

  async apply(batch: CommandBatch, leaseId: string): Promise<ChangePreview> {
    return this.validated("ChangePreview", await this.sendJson(`${this.baseUrl}/commands/apply`, "POST", { batch, lease_id: leaseId })) as ChangePreview;
  }

  async getHistory(): Promise<CircuitHistoryStatus> {
    return this.getJson(`${this.baseUrl}/history`) as Promise<CircuitHistoryStatus>;
  }

  async undo(leaseId: string, designId: string): Promise<CircuitHistoryResult> {
    const value = await this.sendJson(`${this.baseUrl}/history/undo`, "POST", { lease_id: leaseId, design_id: designId }) as CircuitHistoryResult;
    this.requireGraph(value.graph); return value;
  }

  async redo(leaseId: string, designId: string): Promise<CircuitHistoryResult> {
    const value = await this.sendJson(`${this.baseUrl}/history/redo`, "POST", { lease_id: leaseId, design_id: designId }) as CircuitHistoryResult;
    this.requireGraph(value.graph); return value;
  }

  async listProposals(): Promise<AgentProposal[]> {
    const value = await this.getJson(`${this.baseUrl}/proposals`) as { proposals: AgentProposal[] };
    value.proposals.forEach((proposal) => this.validated("AgentProposal", proposal));
    return value.proposals;
  }

  async submitProposal(proposal: AgentProposal): Promise<AgentProposal> {
    return this.validated("AgentProposal", await this.sendJson(`${this.baseUrl}/proposals`, "POST", proposal)) as AgentProposal;
  }

  async decideProposal(proposalId: string, decision: "accepted" | "rejected", leaseId?: string): Promise<AgentProposal> {
    return this.validated("AgentProposal", await this.sendJson(`${this.baseUrl}/proposals/${encodeURIComponent(proposalId)}/decision`, "POST", { decision, lease_id: leaseId })) as AgentProposal;
  }

  private async getJson(url: string, signal?: AbortSignal): Promise<unknown> {
    const response = await this.fetch(url, { headers: { Accept: "application/json" }, signal });
    const body = await response.json().catch(() => undefined);
    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? String((body as { detail: unknown }).detail) : response.statusText;
      throw new CircuitDesignerHttpError(detail || `Circuit Designer request failed (${response.status}).`, response.status, body);
    }
    return body;
  }

  private async sendJson(url: string, method: "POST" | "DELETE", body?: unknown): Promise<unknown> {
    const response = await this.fetch(url, {
      method,
      headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const value = await response.json().catch(() => undefined);
    if (!response.ok) {
      const detail = value && typeof value === "object" && "detail" in value ? String((value as { detail: unknown }).detail) : response.statusText;
      throw new CircuitDesignerHttpError(detail || `Circuit Designer request failed (${response.status}).`, response.status, value);
    }
    return value;
  }

  private validated(definition: string, value: unknown): unknown {
    const validation = validateContractDefinition(definition, value);
    if (!validation.valid) throw new CircuitDesignerHttpError(`Server returned an invalid ${definition}.`, 502, validation.errors);
    return value;
  }

  private requireGraph(value: unknown): asserts value is CircuitGraphSnapshot {
    const validation = validateGraph(value);
    if (!validation.valid) throw new CircuitDesignerHttpError("Server returned an invalid circuit graph.", 502, validation.errors);
  }
}
