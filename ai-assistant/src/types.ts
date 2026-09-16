export type Domain = "spec" | "circuit";
export type BindingScope = "document" | "entity";

export interface SessionBinding {
  sessionId: string;
  status: "creating" | "active";
  domain: Domain;
  ownerUrl: string;
  documentId: string;
  scope: BindingScope;
  entityKind: string | null;
  entityId: string | null;
  title: string;
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
  ownerResult: unknown;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface BindingInput {
  domain: Domain;
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
  specAllowlist: string[];
  circuitAllowlist: string[];
  requestTimeoutMs: number;
  maxActiveSessions: number;
  eventPageSize: number;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
