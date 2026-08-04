import type {
  CircuitDiff,
  CircuitDocument,
  CircuitOperationBatch,
  Diagnostic,
} from "@spec2gds/circuit-core";
import type { DocumentSectionData, EntityRef } from "@spec2gds/document-core";

export interface AssistantThread {
  id: string;
  title: string;
  status: "regular" | "archived";
  domain: "circuit" | "spec";
  service_base_url: string | null;
  circuit_base_url: string | null;
  document_id: string | null;
  entity_kind: EntityRef["entity_kind"] | null;
  entity_id: string | null;
  include_png: boolean;
  conversation_summary: string | null;
  summary_message_count: number;
  created_at: string;
  updated_at: string;
}

export interface HostedServiceStatus {
  service_url: string;
  ui_url: string;
  available: boolean;
  detail: string;
}

export interface ServiceDirectory {
  schema_version: 1;
  services: {
    spec_editor: HostedServiceStatus;
    circuit_designer: HostedServiceStatus;
    ai_assistant: HostedServiceStatus;
  };
}

export interface StoredMessage {
  id: string;
  thread_id: string;
  parent_id: string | null;
  role: "user" | "assistant" | "system";
  content: unknown;
  created_at: string;
  updated_at: string;
}

export interface CircuitSnapshot {
  revision: string;
  document: CircuitDocument;
}

export interface CircuitProposalArtifact {
  kind: "circuit_change_proposal";
  schema_version: "1";
  proposal_id: string;
  document_id: string;
  base_revision: string;
  title: string;
  summary: string;
  rationale: string;
  assumptions: string[];
  batch: CircuitOperationBatch;
}

export interface SpecProposalArtifact {
  kind: "spec_change_proposal";
  schema_version: "1.0";
  proposal_id: string;
  document_id: string;
  target: EntityRef;
  base_source_revision_hash: string;
  title: string;
  summary: string;
  rationale: string;
  assumptions: string[];
  operations: Array<Record<string, unknown>>;
}

export type ProposalArtifact = CircuitProposalArtifact | SpecProposalArtifact;

export interface SpecDiffEntry {
  path: string;
  change: "added" | "removed" | "changed";
  before: unknown;
  after: unknown;
}

export type ReviewState =
  | "draft"
  | "invalid"
  | "ready"
  | "stale"
  | "discarded"
  | "sent"
  | "applied";

export interface ProposalReview {
  proposal_id: string;
  thread_id: string;
  message_id: string | null;
  state: ReviewState;
  artifact: ProposalArtifact;
  base_document: CircuitDocument | DocumentSectionData[] | null;
  candidate: CircuitDocument | DocumentSectionData[] | null;
  diff: CircuitDiff | SpecDiffEntry[] | null;
  diagnostics: Diagnostic[] | Record<string, unknown> | null;
  submitted_proposal_id: string | null;
  created_at: string;
  updated_at: string;
}
