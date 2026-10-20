/** Process-local Circuit snapshots, leases, proposals and replay receipts.
 * This store does not save .spec packages or independent files. Read previews
 * as candidate validation, commits as local accepted-state changes, and source
 * synchronization as a separate owner-mediated boundary in the HTTP service. */
import {
  applyOperations,
  availableHumanName, cleanHumanName, publicFilenameStem,
  commitProviderDocument,
  CircuitBackendError,
  clone,
  compileConstruction,
  diffDocuments,
  exportCircuitJson,
  renderCircuitSvg,
  resolveHierarchy,
  validateCircuitDocument,
  validateDocumentSemantics,
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
  type ComponentDefinition,
  type ComponentDesignProvider,
  type ComponentQuery,
  type DocumentSummary,
  type EditLease,
  type ProposalDecision,
  type ProviderCommitRequest,
  type ProviderCommitResult,
  type ResolvedComponentDesign,
  type SubgraphQuery,
} from "@spec2gds/circuit-core";
import { renderCircuitPngBytes } from "./png";

interface StoredDocument {
  snapshot: CircuitSnapshot;
  revisionNumber: number;
  lease: EditLease | null;
  proposals: Map<string, CircuitProposal>;
  requests: Map<string, CircuitChangeResult>;
}

export interface SessionBackendOptions {
  now?: () => Date;
  provider?: ComponentDesignProvider;
  documents?: CircuitDocument[];
}

const emptyDiff = () => ({ added: [], removed: [], changed: [], connections_changed: [] });

/**
 * Ephemeral service-side session store.
 *
 * Circuit state, revisions, edit leases, proposals, and idempotency results
 * exist only for the lifetime of the Node service process. Durable ownership
 * remains with REST clients such as a SpecIR translator or a downloaded
 * CircuitDocument file.
 */
export class EphemeralCircuitSessionBackend implements CircuitDesignerBackend {
  private readonly records = new Map<string, StoredDocument>();
  private readonly now: () => Date;
  private provider?: ComponentDesignProvider;
  private readonly documentProviders = new Map<string, ComponentDesignProvider>();
  private sequence = 0;

  constructor(options: SessionBackendOptions = {}) {
    this.now = options.now ?? (() => new Date());
    this.provider = options.provider;
    for (const document of options.documents ?? []) this.insertInitial(document);
  }

  registerProvider(provider: ComponentDesignProvider | undefined, documentId?: string): void {
    if (!documentId) {
      this.provider = provider;
      return;
    }
    if (provider) this.documentProviders.set(documentId, provider);
    else this.documentProviders.delete(documentId);
  }

  async create(document: CircuitDocument, requestId: string): Promise<CircuitChangeResult> {
    const existingRequest = [...this.records.values()]
      .map((record) => record.requests.get(requestId))
      .find(Boolean);
    if (existingRequest) return clone(existingRequest);
    if (this.records.has(document.document_id)) {
      return this.conflict("document_exists", `The document “${this.records.get(document.document_id)!.snapshot.document.label}” already exists.`);
    }
    const naming = this.nameDiagnostics(document);
    if (naming.length) return this.rejected(naming, document);
    document = { ...document, label: cleanHumanName(document.label) };
    const checked = validateCircuitDocument(document);
    if (!checked.valid) return this.rejected(checked.diagnostics, document);
    const record = this.makeRecord(document);
    const result: CircuitChangeResult = {
      status: "accepted",
      snapshot: clone(record.snapshot),
      diagnostics: checked.diagnostics,
      diff: diffDocuments(undefined, document),
      alias_map: {},
    };
    record.requests.set(requestId, clone(result));
    this.records.set(document.document_id, record);
    return result;
  }

  async listDocuments(): Promise<DocumentSummary[]> {
    return Promise.all([...this.records.keys()].map((documentId) => this.summary(documentId)));
  }

  async get(documentId: string): Promise<CircuitSnapshot> {
    return clone(this.record(documentId).snapshot);
  }

  async replace(
    documentId: string,
    document: CircuitDocument,
    expectedRevision: string,
    requestId: string,
  ): Promise<CircuitChangeResult> {
    const record = this.record(documentId);
    const replay = record.requests.get(requestId);
    if (replay) return clone(replay);
    if (record.snapshot.revision !== expectedRevision) return this.revisionConflict(record);
    if (document.document_id !== documentId) {
      return this.rejected([{
        severity: "error",
        code: "document_id_mismatch",
        message: "Replacement document_id must match the target document.",
      }], document);
    }
    if (this.activeLease(record)) return this.locked(record);
    const naming = this.nameDiagnostics(document);
    if (naming.length) return this.rejected(naming, document);
    document = { ...document, label: cleanHumanName(document.label) };
    const checked = validateCircuitDocument(document);
    if (!checked.valid) return this.rejected(checked.diagnostics, document);
    const before = record.snapshot.document;
    this.advance(record, document);
    const result: CircuitChangeResult = {
      status: "accepted",
      snapshot: clone(record.snapshot),
      diagnostics: checked.diagnostics,
      diff: diffDocuments(before, document),
      alias_map: {},
    };
    record.requests.set(requestId, clone(result));
    return result;
  }

  async validateConstruction(construction: CircuitConstruction): Promise<CircuitChangeResult> {
    const compiled = compileConstruction(construction);
    return {
      status: compiled.document ? "accepted" : "rejected",
      ...(compiled.document ? { candidate: compiled.document } : {}),
      diagnostics: compiled.diagnostics,
      diff: compiled.document ? diffDocuments(undefined, compiled.document) : emptyDiff(),
      alias_map: compiled.alias_map,
    };
  }

  async preview(documentId: string, batch: CircuitOperationBatch): Promise<CircuitChangeResult> {
    const record = this.record(documentId);
    if (record.snapshot.revision !== batch.expected_revision) return this.revisionConflict(record);
    return this.evaluate(record.snapshot.document, batch);
  }

  async commit(documentId: string, batch: CircuitOperationBatch, leaseId?: string): Promise<CircuitChangeResult> {
    const record = this.record(documentId);
    const replay = record.requests.get(batch.request_id);
    if (replay) return clone(replay);
    if (record.snapshot.revision !== batch.expected_revision) return this.revisionConflict(record);
    const lease = this.activeLease(record);
    if (lease && lease.lease_id !== leaseId) return this.locked(record);
    if (leaseId && lease?.lease_id !== leaseId) return this.locked(record);
    const result = this.evaluate(record.snapshot.document, batch);
    if (result.status !== "accepted" || !result.candidate) return result;
    this.advance(record, result.candidate);
    const committed: CircuitChangeResult = {
      ...result,
      candidate: undefined,
      snapshot: clone(record.snapshot),
    };
    record.requests.set(batch.request_id, clone(committed));
    this.markProposalsStale(record);
    return committed;
  }

  async getLease(documentId: string): Promise<EditLease | null> {
    return clone(this.activeLease(this.record(documentId)));
  }

  async acquireLease(documentId: string, ownerId: string, ttlSeconds = 900): Promise<EditLease> {
    this.validateLeaseRequest(ownerId, ttlSeconds);
    const record = this.record(documentId);
    const current = this.activeLease(record);
    if (current && current.owner_id !== ownerId) {
      throw new CircuitBackendError("lock_conflict", `Document is locked by client session ${current.owner_id}.`);
    }
    record.lease = {
      lease_id: current?.lease_id ?? this.nextId("lease"),
      document_id: documentId,
      owner_id: ownerId,
      expires_at: new Date(this.now().getTime() + ttlSeconds * 1000).toISOString(),
    };
    return clone(record.lease);
  }

  async renewLease(documentId: string, leaseId: string, ttlSeconds = 900): Promise<EditLease> {
    this.validateLeaseRequest(leaseId, ttlSeconds);
    const record = this.record(documentId);
    const lease = this.activeLease(record);
    if (!lease || lease.lease_id !== leaseId) {
      throw new CircuitBackendError("lock_conflict", "The edit lease is missing or expired.");
    }
    lease.expires_at = new Date(this.now().getTime() + ttlSeconds * 1000).toISOString();
    return clone(lease);
  }

  async takeOverLease(documentId: string, expectedLeaseId: string, ownerId: string, ttlSeconds = 900, refreshedDocument?: CircuitDocument): Promise<EditLease> {
    this.validateLeaseRequest(ownerId, ttlSeconds);
    const record = this.record(documentId);
    const lease = this.activeLease(record);
    if (!expectedLeaseId || lease?.lease_id !== expectedLeaseId) {
      throw new CircuitBackendError("lock_conflict", "The editing lease changed. Review the current lock before taking over.", [], { document_id: documentId, lease });
    }
    if (refreshedDocument) {
      const checked = validateCircuitDocument(refreshedDocument);
      const naming = this.nameDiagnostics(refreshedDocument);
      if (refreshedDocument.document_id !== documentId || !checked.valid || naming.length) {
        throw new CircuitBackendError("validation_failed", "The refreshed source is not a valid replacement.", [...checked.diagnostics, ...naming]);
      }
      // No await between the lease comparison, replacement and new lease.
      this.advance(record, clone(refreshedDocument));
      this.markProposalsStale(record);
    }
    record.lease = {
      lease_id: this.nextId("lease"), document_id: documentId, owner_id: ownerId,
      expires_at: new Date(this.now().getTime() + ttlSeconds * 1000).toISOString(),
    };
    return clone(record.lease);
  }

  private validateLeaseRequest(clientId: string, ttlSeconds: number): void {
    if (typeof clientId !== "string" || !clientId.trim() || !Number.isFinite(ttlSeconds) || ttlSeconds <= 0
      || !Number.isFinite(new Date(this.now().getTime() + ttlSeconds * 1000).getTime())) {
      throw new CircuitBackendError("validation_failed", "A client identity and positive lease duration are required.");
    }
  }

  async releaseLease(documentId: string, leaseId: string): Promise<void> {
    const record = this.record(documentId);
    const lease = this.activeLease(record);
    if (!lease || lease.lease_id !== leaseId) {
      throw new CircuitBackendError("lock_conflict", "The edit lease is missing or expired.");
    }
    record.lease = null;
  }

  async summary(documentId: string): Promise<DocumentSummary> {
    const document = this.record(documentId).snapshot.document;
    const diagnostics = validateDocumentSemantics(document);
    return {
      document_id: document.document_id,
      label: document.label,
      design_id: document.design.id,
      component_count: document.components.length,
      instance_count: document.design.instances.length,
      net_count: document.design.nets.length,
      warning_count: diagnostics.filter((item) => item.severity === "warning").length,
    };
  }

  async lookupComponents(documentId: string, query: ComponentQuery = {}): Promise<ComponentDefinition[]> {
    const text = query.text?.trim().toLocaleLowerCase();
    return clone(this.record(documentId).snapshot.document.components.filter((component) =>
      (!query.origin || component.origin === query.origin)
      && (!text || `${component.id} ${component.label}`.toLocaleLowerCase().includes(text))));
  }

  async subgraph(documentId: string, query: SubgraphQuery): Promise<CircuitDocument> {
    const source = this.record(documentId).snapshot.document;
    const selected = new Set(query.element_ids);
    const depth = Math.max(0, query.depth ?? 1);
    for (let level = 0; level < depth; level += 1) {
      for (const net of source.design.nets) {
        if (selected.has(net.id) || net.endpoints.some((endpoint) =>
          endpoint.kind === "instance" && selected.has(endpoint.instance_id))) {
          selected.add(net.id);
          for (const endpoint of net.endpoints) {
            if (endpoint.kind === "instance") selected.add(endpoint.instance_id);
          }
        }
      }
    }
    const instances = source.design.instances.filter((item) => selected.has(item.id));
    const instanceIds = new Set(instances.map((item) => item.id));
    const nets = source.design.nets.filter((net) =>
      selected.has(net.id) || net.endpoints.some((endpoint) =>
        endpoint.kind === "instance" && instanceIds.has(endpoint.instance_id)));
    const componentIds = new Set(instances.map((item) => item.component_id));
    return clone({
      ...source,
      components: source.components.filter((item) => componentIds.has(item.id)),
      design: { ...source.design, instances, nets },
      layout: {
        ...source.layout,
        instance_geometry: Object.fromEntries(Object.entries(source.layout.instance_geometry)
          .filter(([id]) => instanceIds.has(id))),
        terminal_placements: Object.fromEntries(Object.entries(source.layout.terminal_placements)
          .filter(([key]) => [...instanceIds].some((id) => key.startsWith(`${id}:`)) || key.startsWith("boundary:"))),
        net_routes: Object.fromEntries(Object.entries(source.layout.net_routes)
          .filter(([id]) => nets.some((net) => net.id === id))),
      },
    });
  }

  async export(documentId: string, options: CircuitExportOptions): Promise<CircuitExport> {
    const document = this.record(documentId).snapshot.document;
    const used = new Set<string>();
    let stem = publicFilenameStem(document.label);
    for (const record of this.records.values()) {
      const base = publicFilenameStem(record.snapshot.document.label);
      let candidate = base, number = 2;
      while (used.has(candidate)) candidate = `${base}-${number++}`;
      used.add(candidate);
      if (record.snapshot.document.document_id === documentId) { stem = candidate; break; }
    }
    if (options.format === "json") {
      return {
        media_type: "application/json",
        filename: `${stem}.circuit.json`,
        data: exportCircuitJson(document),
      };
    }
    if (options.format === "svg") {
      return {
        media_type: "image/svg+xml",
        filename: `${stem}.svg`,
        data: renderCircuitSvg(document, { selection: options.selection }),
      };
    }
    return {
      media_type: "image/png",
      filename: `${stem}.png`,
      data: renderCircuitPngBytes(document, options.selection),
    };
  }

  async listProposals(documentId: string): Promise<CircuitProposal[]> {
    const record = this.record(documentId);
    this.markProposalsStale(record);
    return clone([...record.proposals.values()]);
  }

  async submitProposal(proposal: CircuitProposalCreateRequest): Promise<CircuitProposal> {
    const record = this.record(proposal.document_id);
    if (record.proposals.has(proposal.proposal_id)) {
      throw new CircuitBackendError("revision_conflict", `Proposal already exists: ${proposal.proposal_id}`);
    }
    if (proposal.base_revision !== record.snapshot.revision) {
      throw new CircuitBackendError("proposal_stale", "Proposal base revision is stale.");
    }
    let evaluation: CircuitChangeResult;
    if (proposal.batch) evaluation = await this.preview(proposal.document_id, proposal.batch);
    else evaluation = await this.validateConstruction(proposal.construction!);
    const saved = clone({
      ...proposal,
      status: "pending" as const,
      diagnostics: evaluation.diagnostics,
      diff: evaluation.diff,
      created_at: this.now().toISOString(),
    });
    record.proposals.set(saved.proposal_id, saved);
    return clone(saved);
  }

  async decideProposal(
    documentId: string,
    proposalId: string,
    decision: ProposalDecision,
  ): Promise<CircuitChangeResult | undefined> {
    const record = this.record(documentId);
    const proposal = record.proposals.get(proposalId);
    if (!proposal) throw new CircuitBackendError("not_found", `Unknown proposal: ${proposalId}`);
    if (proposal.base_revision !== record.snapshot.revision) {
      throw new CircuitBackendError("proposal_stale", "Proposal is stale.");
    }
    let result: CircuitChangeResult | undefined;
    if (decision === "accept") {
      if (proposal.batch) result = await this.commit(documentId, proposal.batch);
      else if (proposal.construction) {
        const compiled = compileConstruction(proposal.construction);
        if (!compiled.document) result = this.rejected(compiled.diagnostics);
        else if (proposal.construction.mode === "create") {
          result = await this.create(compiled.document, `proposal:${proposal.proposal_id}`);
        } else {
          result = await this.replace(
            documentId,
            compiled.document,
            proposal.base_revision,
            `proposal:${proposal.proposal_id}`,
          );
        }
      }
    }
    if (decision === "reject" || result?.status === "accepted") {
      record.proposals.delete(proposalId);
    }
    return result;
  }

  async resolveProposal(documentId: string, proposalId: string): Promise<void> {
    const record = this.record(documentId);
    if (!record.proposals.delete(proposalId)) {
      throw new CircuitBackendError("not_found", `Unknown proposal: ${proposalId}`);
    }
  }

  async resolveComponentDesign(documentId: string, componentId: string): Promise<ResolvedComponentDesign> {
    const document = this.record(documentId).snapshot.document;
    const component = document.components.find((item) => item.id === componentId);
    if (!component) throw new CircuitBackendError("not_found", `Unknown component: ${componentId}`);
    const provider = this.documentProviders.get(documentId) ?? this.provider;
    if (!provider) return { status: "unavailable", message: "No component design provider is registered." };
    const { result, diagnostics } = await resolveHierarchy(provider, document, component);
    if (diagnostics.some((item) => item.severity === "error")) {
      throw new CircuitBackendError("provider_failed", result.message ?? "Provider result is incompatible.", diagnostics);
    }
    return result;
  }

  async commitComponentDesign(
    documentId: string,
    componentId: string,
    request: ProviderCommitRequest,
  ): Promise<ProviderCommitResult> {
    const document = this.record(documentId).snapshot.document;
    const component = document.components.find((item) => item.id === componentId);
    if (!component) throw new CircuitBackendError("not_found", `Unknown component: ${componentId}`);
    if (request.component.id !== componentId) {
      throw new CircuitBackendError("validation_failed", "Provider commit component does not match the route.");
    }
    const provider = this.documentProviders.get(documentId) ?? this.provider;
    if (!provider) throw new CircuitBackendError("provider_failed", "No component design provider is registered.");
    return commitProviderDocument(provider, { ...request, component });
  }

  private insertInitial(document: CircuitDocument, revision = "1"): void {
    document = clone(document);
    document.label = availableHumanName(document.label || "Circuit", [...this.records.values()].map(record => record.snapshot.document.label));
    const names: string[] = [];
    for (const component of document.components) {
      component.label = availableHumanName(component.label || "Component", names);
      names.push(component.label);
    }
    this.records.set(document.document_id, {
      snapshot: { revision, document: clone(document) },
      revisionNumber: Number(revision) || 1,
      lease: null,
      proposals: new Map(),
      requests: new Map(),
    });
  }

  private makeRecord(document: CircuitDocument): StoredDocument {
    return {
      snapshot: { revision: "1", document: clone(document) },
      revisionNumber: 1,
      lease: null,
      proposals: new Map(),
      requests: new Map(),
    };
  }

  private record(documentId: string): StoredDocument {
    const value = this.records.get(documentId);
    if (!value) throw new CircuitBackendError("not_found", `Unknown document: ${documentId}`);
    return value;
  }

  private activeLease(record: StoredDocument): EditLease | null {
    if (record.lease && new Date(record.lease.expires_at) <= this.now()) record.lease = null;
    return record.lease;
  }

  private advance(record: StoredDocument, document: CircuitDocument): void {
    record.revisionNumber += 1;
    record.snapshot = { revision: String(record.revisionNumber), document: clone(document) };
  }

  private markProposalsStale(record: StoredDocument): void {
    for (const proposal of record.proposals.values()) {
      if (proposal.base_revision !== record.snapshot.revision) proposal.status = "stale";
    }
  }

  private nextId(prefix: string): string {
    this.sequence += 1;
    return `${prefix}_${this.sequence}`;
  }

  private evaluate(document: CircuitDocument, batch: CircuitOperationBatch): CircuitChangeResult {
    const result = applyOperations(document, batch.operations);
    if (!result.candidate) return result;
    const naming = this.nameDiagnostics(result.candidate);
    if (naming.length) return this.rejected(naming, result.candidate);
    const checked = validateCircuitDocument(result.candidate);
    if (checked.valid) {
      return {
        ...result,
        diagnostics: checked.diagnostics,
      };
    }
    return this.rejected(checked.diagnostics, result.candidate);
  }

  private nameDiagnostics(document: CircuitDocument): CircuitChangeResult["diagnostics"] {
    try {
      const name = cleanHumanName(document.label);
      const suggestion = availableHumanName(name, [...this.records.values()].filter(record => record.snapshot.document.document_id !== document.document_id).map(record => record.snapshot.document.label));
      return suggestion === name ? [] : [{ severity: "error", code: "duplicate_name", message: `A document named “${name}” already exists. Use “${suggestion}” or another name.`, element_key: document.document_id }];
    } catch (cause) { return [{ severity: "error", code: "invalid_name", message: String(cause) }]; }
  }

  private rejected(diagnostics: CircuitChangeResult["diagnostics"], candidate?: CircuitDocument): CircuitChangeResult {
    return {
      status: "rejected",
      ...(candidate ? { candidate: clone(candidate) } : {}),
      diagnostics,
      diff: emptyDiff(),
      alias_map: {},
    };
  }

  private conflict(code: string, message: string): CircuitChangeResult {
    return {
      status: "conflict",
      diagnostics: [{ severity: "error", code, message }],
      diff: emptyDiff(),
      alias_map: {},
    };
  }

  private revisionConflict(record: StoredDocument): CircuitChangeResult {
    return {
      status: "conflict",
      snapshot: clone(record.snapshot),
      diagnostics: [{ severity: "error", code: "revision_conflict", message: "The document changed; refetch and retry." }],
      diff: emptyDiff(),
      alias_map: {},
    };
  }

  private locked(record: StoredDocument): CircuitChangeResult {
    return {
      status: "locked",
      snapshot: clone(record.snapshot),
      diagnostics: [{ severity: "error", code: "lock_conflict", message: "The document has an active manual edit lease." }],
      diff: emptyDiff(),
      alias_map: {},
    };
  }
}
