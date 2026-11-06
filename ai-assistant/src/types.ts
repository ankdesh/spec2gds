export type Domain = "spec" | "circuit";
export type BindingScope = "document" | "entity";
export type AssistantPreset = "focused" | "goal" | "orchestrated";

export interface SessionBinding {
  sessionId: string;
  status: "creating" | "active";
  preset: AssistantPreset;
  domain: Domain;
  serviceUrl: string;
  documentId: string;
  serviceDocumentKey?: string | null;
  editContextId?: string | null;
  editParticipantId?: string | null;
  workspaceServiceDocumentKey?: string | null;
  scope: BindingScope;
  entityKind: string | null;
  entityId: string | null;
  title: string;
  sourceName?: string;
  workspaceKey: string;
  workspaceTitle: string;
  workspacePath: string;
  workspaceDomain: Domain;
  workspaceServiceUrl: string;
  workspaceDocumentId: string;
  archived: boolean;
  createdAt: string;
  updatedAt: string;
}

export type ReviewState =
  | "previewing"
  | "ready"
  | "rejected"
  | "stale"
  | "applying"
  | "reconcile"
  | "applied"
  | "sent"
  | "discarded";

export type ProposalErrorCode =
  | "UNSUPPORTED_REQUEST"
  | "INVALID_PROPOSAL"
  | "STALE_REVISION"
  | "SERVICE_REJECTED"
  | "SERVICE_LOCKED"
  | "SERVICE_UNAVAILABLE"
  | "SERVICE_CONTRACT_ERROR"
  | "INTERNAL_ERROR";

export interface ProposalIssue {
  error_code: string;
  target: string | null;
  details: string;
  suggested_actions: string[];
}

export interface ProposalError {
  error_code: ProposalErrorCode;
  target: string | null;
  details: string;
  retryable: boolean;
  suggested_actions: string[];
  issues: ProposalIssue[];
  owner_diagnostics: unknown;
  correlation_id: string;
}

export interface ProposalChangeSummary {
  text: string;
  operationCounts: Array<{ type: string; count: number }>;
  changedTargets: string[];
  assumptions: string[];
  diagnostics: string[];
}

/** Display data derived from service previews, never from inferred source values. */
export interface PresentedChange {
  id: string;
  label: string;
  change: "added" | "changed" | "removed";
  kind: "value" | "text" | "code";
  before: unknown;
  after: unknown;
  beforeAvailable: boolean;
  afterAvailable: boolean;
}

export interface ProposalPresentation {
  summary: string;
  rationale: string;
  assumptions: string[];
  warnings: string[];
  previewAvailable: boolean;
  errorMessage: string;
  saved: boolean;
  groups: Array<{ label: string; changes: PresentedChange[] }>;
}

export interface ProposalReview {
  proposalId: string;
  sessionId: string;
  callId: string;
  domain: Domain;
  state: ReviewState;
  baseRevision: string;
  artifact: Record<string, unknown>;
  artifactDigest: string;
  preview: Record<string, unknown> | null;
  diagnostics: unknown;
  error: ProposalError | null;
  serviceResult: unknown;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export type PublicProposalReview = Omit<ProposalReview, "artifactDigest"> & {
  changeSummary: ProposalChangeSummary;
  presentation: ProposalPresentation;
  reviewNumber?: number;
};

export interface BindingInput {
  domain: Domain;
  preset?: AssistantPreset;
  eventTemplateKey?: string;
  eventTemplateRevision?: number;
  serviceBaseUrl: string;
  documentId: string;
  serviceDocumentKey?: string;
  editContextId?: string;
  editParticipantId?: string;
  workspaceServiceDocumentKey?: string;
  scope?: BindingScope;
  entityKind?: string;
  entityId?: string;
  title?: string;
  sourceName?: string;
}

export interface ServiceConfig {
  provider: string;
  model: string;
  stateRoot: string;
  scratchRoot: string;
  specDocumentRoot: string;
  specAllowlist: string[];
  circuitAllowlist: string[];
  requestTimeoutMs: number;
  maxStepsPerTurn: number;
  maxOutputTokens: number;
  interactiveForms: boolean;
}

export interface WorkspaceDescriptor {
  serviceDocumentKey?: string;
  key: string;
  title: string;
  path: string;
  domain: Domain;
  serviceUrl: string;
  documentId: string;
}

export interface SourceCreationRequest {
  destinationDirectory?: string;
  editContextId?: string;
  flowExecutionId: string;
  architectureReviewId?: string;
  acceptedArchitecture?: Record<string, unknown>;
  requestId: string;
  sourceSessionId: string;
  callId: string;
  originalRequest: string;
  preset: AssistantPreset;
  status: "pending" | "creating" | "created" | "reserved" | "bound" | "cancelled" | "uncertain";
  documentId: string;
  title: string;
  serviceBaseUrl: string;
  destination: string;
  destinationSessionId: string;
  sourceRevisionHash: string | null;
  serviceDocumentKey?: string;
  automatic?: boolean;
  creationReceipts?: boolean;
  error: string | null;
  reservation: { session: SessionBinding; workspace: WorkspaceDescriptor } | null;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
