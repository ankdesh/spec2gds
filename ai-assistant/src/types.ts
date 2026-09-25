export type Domain = "spec" | "circuit";
export type BindingScope = "document" | "entity";
export type AssistantPreset = "focused" | "goal" | "orchestrated";

export interface SessionBinding {
  sessionId: string;
  status: "creating" | "active";
  preset: AssistantPreset;
  domain: Domain;
  ownerUrl: string;
  documentId: string;
  scope: BindingScope;
  entityKind: string | null;
  entityId: string | null;
  title: string;
  workspaceKey: string;
  workspaceTitle: string;
  workspacePath: string;
  workspaceDomain: Domain;
  workspaceOwnerUrl: string;
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
  | "OWNER_REJECTED"
  | "OWNER_LOCKED"
  | "OWNER_UNAVAILABLE"
  | "OWNER_CONTRACT_ERROR"
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
  ownerResult: unknown;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export type PublicProposalReview = Omit<ProposalReview, "artifactDigest"> & {
  changeSummary: ProposalChangeSummary;
};

export interface BindingInput {
  domain: Domain;
  preset?: AssistantPreset;
  serviceBaseUrl: string;
  documentId: string;
  scope?: BindingScope;
  entityKind?: string;
  entityId?: string;
  title?: string;
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
  key: string;
  title: string;
  path: string;
  domain: Domain;
  ownerUrl: string;
  documentId: string;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
