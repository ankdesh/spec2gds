import type { CircuitDocument, CircuitSnapshot, Diagnostic } from "./types.generated";

/** Public metadata for an ephemeral Circuit session backed by a `.spec` design. */
export interface CircuitSourceBindingV1 {
  schema_version: 1;
  binding_id: string;
  source_document_id: string;
  source_entity: {
    document_id: string;
    entity_id: string;
    entity_kind: "component" | "design";
  };
  editable_design_id?: string;
  base_source_revision_hash: string;
  writable: boolean;
  capabilities: string[];
  omitted_bus_items: string[];
  omitted_ports: string[];
  message?: string;
}

/** Provider response shared by source resolve, preview, and commit callbacks. */
export interface CircuitSourceSyncResult {
  accepted: boolean;
  source_revision_hash: string;
  document?: CircuitDocument;
  diagnostics: Diagnostic[];
  impact?: Record<string, unknown>;
}

/** Browser-facing result after the Circuit service reconciles a provider response. */
export interface CircuitSourceSyncResponse extends CircuitSourceSyncResult {
  binding?: CircuitSourceBindingV1;
  snapshot?: CircuitSnapshot;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/** Runtime guard used at the server registration and browser trust boundaries. */
export function isCircuitSourceBindingV1(value: unknown): value is CircuitSourceBindingV1 {
  if (!isRecord(value) || value.schema_version !== 1) return false;
  if (
    typeof value.binding_id !== "string" || !value.binding_id
    || typeof value.source_document_id !== "string" || !value.source_document_id
    || typeof value.base_source_revision_hash !== "string" || !value.base_source_revision_hash
    || typeof value.writable !== "boolean"
    || !isStringArray(value.capabilities)
    || !isStringArray(value.omitted_bus_items)
    || !isStringArray(value.omitted_ports)
  ) return false;
  if (value.editable_design_id !== undefined && typeof value.editable_design_id !== "string") return false;
  if (value.message !== undefined && typeof value.message !== "string") return false;
  const source = value.source_entity;
  return isRecord(source)
    && typeof source.document_id === "string" && Boolean(source.document_id)
    && typeof source.entity_id === "string" && Boolean(source.entity_id)
    && (source.entity_kind === "component" || source.entity_kind === "design");
}
