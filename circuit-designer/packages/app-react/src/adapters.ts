/** Host capabilities consumed by the reusable Circuit application.
 * File ownership, preferences, source saves, events, telemetry and tools are
 * injected so the shell need not assume browser storage or Spec API addresses.
 * Adapter implementations must preserve revision/receipt semantics. */
import type {
  CircuitDesignerBackend,
  CircuitDesignerPreferencesV1,
  CircuitDocument,
  CircuitOperationBatch,
  CircuitSnapshot,
  CircuitEditRecovery,
  Diagnostic,
  EditLease,
  ServiceEvent,
} from "@spec2gds/circuit-core";

export type CircuitLaunch =
  | { kind: "new"; document?: CircuitDocument }
  | { kind: "document"; documentId: string };

export interface CircuitFileReadResult {
  document: CircuitDocument;
  displayName?: string;
}

export interface CircuitFileWriteRequest {
  suggestedName: string;
  mediaType: "application/json" | "image/svg+xml" | "image/png";
  data: string | Uint8Array;
}

export interface CircuitFileAdapter {
  open(): Promise<CircuitFileReadResult | undefined>;
  write(request: CircuitFileWriteRequest): Promise<void>;
}

export interface CircuitPreferencesLoadResult {
  preferences: CircuitDesignerPreferencesV1;
  persisted: boolean;
}

export interface CircuitPreferencesAdapter {
  load(): Promise<CircuitPreferencesLoadResult>;
  save(preferences: CircuitDesignerPreferencesV1): Promise<CircuitPreferencesLoadResult>;
  readCached?(): CircuitDesignerPreferencesV1 | undefined;
  cacheFailedSave?(preferences: CircuitDesignerPreferencesV1): void;
  clearCache?(): void;
}

export interface CircuitSourceState {
  id: string;
  label: string;
  revision: string;
  writable: boolean;
  pendingInternalDesign?: boolean;
  svChoiceRequired?: boolean;
  interfacePreview?: boolean;
  enclosingComponentName?: string;
  capabilities: string[];
  message?: string;
  saveLabel?: string;
  draftLabel?: string;
  boundLabel?: string;
  identifierPattern?: string;
  identifierHint?: string;
  metadata?: unknown;
}

export interface CircuitSourceSaveResult {
  accepted: boolean;
  revision: string;
  diagnostics: Diagnostic[];
  state?: CircuitSourceState;
  snapshot?: CircuitSnapshot;
  lease?: EditLease;
}

export interface CircuitSourceAdapter {
  checkAccess?(documentId: string): Promise<boolean>;
  load(documentId: string): Promise<CircuitSourceState | undefined>;
  commit(documentId: string, batch: CircuitOperationBatch, leaseId: string, proposalId?: string, svDisposition?: "retain_reference" | "remove"): Promise<CircuitSourceSaveResult>;
  prepareInternalDesign?(documentId: string, leaseId: string, requestId: string): Promise<CircuitSourceSaveResult>;
  discardInternalDesign?(documentId: string, leaseId: string, requestId: string): Promise<CircuitSourceSaveResult>;
  reload(documentId: string): Promise<CircuitSourceSaveResult>;
  recover?(documentId: string, expectedLeaseId: string, clientId: string): Promise<CircuitEditRecovery & { state?: CircuitSourceState }>;
}

export interface CircuitToolContext {
  backend: CircuitDesignerBackend;
  document: CircuitDocument;
  snapshot: CircuitSnapshot;
}

export interface CircuitToolContribution {
  id: string;
  label: string;
  description: string;
  run(context: CircuitToolContext): void | Promise<void>;
}

export interface CircuitTelemetrySink {
  captureGlobalErrors?(): void | (() => void);
  event(component: string, event: string, message: string, severity: "debug" | "info" | "warning" | "error", details?: unknown): void;
}

export interface CircuitEventAdapter {
  subscribe(documentId: string, listener: (event: ServiceEvent) => void): () => void;
}

export const noopCircuitTelemetry: CircuitTelemetrySink = {
  event: () => undefined,
};
