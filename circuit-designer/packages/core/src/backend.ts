import type {
  CircuitChangeResult,
  CircuitConstruction,
  CircuitDocument,
  CircuitOperationBatch,
  CircuitProposal,
  CircuitProposalCreateRequest,
  CircuitSnapshot,
  ComponentDefinition,
  Diagnostic,
  DocumentSummary,
  EditLease,
  ProviderCommitRequest,
  ProviderCommitResult,
  ResolvedComponentDesign,
} from "./types.generated";

export type ProposalDecision = "accept" | "reject";

export interface CircuitExportOptions {
  format: "json" | "svg" | "png";
  selection?: string[];
}

export interface CircuitExport {
  media_type: "application/json" | "image/svg+xml" | "image/png";
  filename: string;
  data: string | Uint8Array;
}

export interface ComponentQuery {
  text?: string;
  origin?: ComponentDefinition["origin"];
}

export interface SubgraphQuery {
  element_ids: string[];
  depth?: number;
}

export interface ComponentDesignProvider {
  resolveComponentDesign(
    component: ComponentDefinition,
    context: { parent_document_id: string; ancestry: string[] },
  ): Promise<ResolvedComponentDesign>;
  commitComponentDesign?(
    request: ProviderCommitRequest,
  ): Promise<ProviderCommitResult>;
}

/**
 * Application boundary implemented by the REST client and the Node service's
 * ephemeral session backend. Revisions are opaque to callers.
 */
export interface CircuitDesignerBackend {
  create(document: CircuitDocument, requestId: string): Promise<CircuitChangeResult>;
  get(documentId: string): Promise<CircuitSnapshot>;
  replace(
    documentId: string,
    document: CircuitDocument,
    expectedRevision: string,
    requestId: string,
  ): Promise<CircuitChangeResult>;
  validateConstruction(construction: CircuitConstruction): Promise<CircuitChangeResult>;
  preview(documentId: string, batch: CircuitOperationBatch): Promise<CircuitChangeResult>;
  commit(documentId: string, batch: CircuitOperationBatch, leaseId?: string): Promise<CircuitChangeResult>;

  getLease(documentId: string): Promise<EditLease | null>;
  acquireLease(documentId: string, ownerId: string, ttlSeconds?: number): Promise<EditLease>;
  renewLease(documentId: string, leaseId: string, ttlSeconds?: number): Promise<EditLease>;
  releaseLease(documentId: string, leaseId: string): Promise<void>;

  summary(documentId: string): Promise<DocumentSummary>;
  lookupComponents(documentId: string, query?: ComponentQuery): Promise<ComponentDefinition[]>;
  subgraph(documentId: string, query: SubgraphQuery): Promise<CircuitDocument>;
  export(documentId: string, options: CircuitExportOptions): Promise<CircuitExport>;

  listProposals(documentId: string): Promise<CircuitProposal[]>;
  submitProposal(proposal: CircuitProposalCreateRequest): Promise<CircuitProposal>;
  decideProposal(documentId: string, proposalId: string, decision: ProposalDecision): Promise<CircuitChangeResult | undefined>;

  resolveComponentDesign(documentId: string, componentId: string): Promise<ResolvedComponentDesign>;
  commitComponentDesign(
    documentId: string,
    componentId: string,
    request: ProviderCommitRequest,
  ): Promise<ProviderCommitResult>;
}

export class CircuitBackendError extends Error {
  constructor(
    readonly code:
      | "validation_failed"
      | "revision_conflict"
      | "lock_conflict"
      | "not_found"
      | "provider_failed"
      | "proposal_stale",
    message: string,
    readonly diagnostics: Diagnostic[] = [],
  ) {
    super(message);
    this.name = "CircuitBackendError";
  }
}
