export type EntityKind =
  | "component"
  | "design"
  | "bus_definition"
  | "abstraction_definition"
  | "narrative_block"
  | "asset";

export interface EntityRef {
  document_id: string;
  entity_id: string;
  entity_kind: EntityKind;
}

export type CellKind = "text" | "multiline" | "boolean" | "integer" | "expression" | "enum" | "reference";
export type CellPresence = "explicit" | "defaulted" | "absent";

export interface DocumentCell {
  kind: CellKind;
  value: string | number | boolean | null;
  presence: CellPresence;
  schema_path: string;
  reference_anchor: string;
}

export interface DocumentColumn {
  key: string;
  label: string;
  schema_path: string;
}

export interface DocumentRow {
  row_id: string;
  cells: Record<string, DocumentCell>;
}

export interface DocumentTable {
  table_id: string;
  kind: string;
  title: string;
  columns: DocumentColumn[];
  rows: DocumentRow[];
}

export interface DocumentFact {
  label: string;
  value: string;
  schema_path: string;
  reference_anchor: string;
}

export interface NarrativeBlock {
  block_id: string;
  type: "section" | "paragraph" | "list" | "table" | "image" | "entity_link" | "live_view";
  text: string;
  inlines: Array<{
    type: "text" | "emphasis" | "strong" | "code" | "link";
    text: string;
    href: string;
    entity_ref?: EntityRef | null;
  }>;
  children: NarrativeBlock[];
  ordered: boolean;
  rows: string[][];
  asset_id: string;
  alt_text: string;
  caption: string;
  entity_refs: EntityRef[];
  renderer_id: string;
  options: Record<string, unknown>;
}

export interface DocumentSectionData {
  section_id: string;
  title: string;
  level: number;
  eyebrow: string;
  entity_ref: EntityRef | null;
  facts: DocumentFact[];
  tables: DocumentTable[];
  narrative: NarrativeBlock[];
}

export interface TocEntry {
  section_id: string;
  title: string;
  level: number;
}

export interface A2UIMessage {
  version: "v0.9";
  createSurface?: { surfaceId: string; catalogId: string };
  updateComponents?: { surfaceId: string; components: Array<Record<string, unknown>> };
  updateDataModel?: { surfaceId: string; path: string; value: unknown };
}

export interface A2UIDocumentBatch {
  protocol_version: "v0.9";
  catalog_id: string;
  surface_id: string;
  source_revision_hash: string;
  messages: A2UIMessage[];
}

export interface HardwareEntitySummary {
  ref: EntityRef;
  vlnv: string;
}

export interface ComponentComposition {
  component: EntityRef;
  internal_design: EntityRef;
}

export interface EntityMetadataInput {
  display_name: string;
  short_description: string;
  description: string;
}

export interface PortCommonInput {
  name: string;
  display_name?: string | null;
  description?: string | null;
}

export interface WirePortInput extends PortCommonInput {
  family: "wire";
  direction: "in" | "out" | "inout";
  range: string | null;
}

export type TransactionalPortKind =
  | "tlm_port"
  | "tlm_socket"
  | "simple_socket"
  | "multi_socket"
  | "custom";

export interface TransactionalPortInput extends PortCommonInput {
  family: "transactional";
  initiative: "requires" | "provides" | "both";
  kind: TransactionalPortKind | null;
  custom_kind: string | null;
  bus_width: string | null;
}

export interface StructuredPortInput extends PortCommonInput {
  family: "structured";
  direction: "in" | "out" | "inout";
}

export type ComponentPortInput = WirePortInput | TransactionalPortInput | StructuredPortInput;
export type ComponentPortUpdateInput =
  | Omit<WirePortInput, "name">
  | Omit<TransactionalPortInput, "name">
  | Omit<StructuredPortInput, "name">;

export interface ComponentInstanceInput {
  name: string;
  component_vlnv: string;
}

export type EditorTransactionOperation =
  | { type: "create_entity"; kind: "component" | "design"; name: string }
  | { type: "set_document_title"; title: string }
  | ({ type: "set_entity_metadata"; entity: EntityRef } & EntityMetadataInput)
  | { type: "upsert_instance"; design: EntityRef; instance: ComponentInstanceInput }
  | { type: "add_component_port"; component: EntityRef; port: ComponentPortInput }
  | {
    type: "update_component_port";
    component: EntityRef;
    name: string;
    port: ComponentPortUpdateInput;
  };

export interface TransactionResult {
  committed: true;
  snapshot: DocumentSnapshot;
}

export interface DocumentSnapshot {
  schema_version: string;
  document_id: string;
  source_revision_hash: string;
  components: HardwareEntitySummary[];
  designs: HardwareEntitySummary[];
  entry_designs: HardwareEntitySummary[];
  bus_definitions: unknown[];
  abstraction_definitions: unknown[];
  component_compositions: ComponentComposition[];
  narrative: { title: string; blocks: NarrativeBlock[] };
  diagnostics: { source: string[]; artifacts: string[] };
}

export interface CircuitDesignerLaunch {
  document_id: string;
  entity_id: string;
  entity_kind: "component" | "design";
  editor_url: string;
  reused_session: boolean;
  omitted_bus_items: string[];
  omitted_ports: string[];
}

export interface AssistantLaunch {
  assistant_url: string;
  target: EntityRef;
}

export interface HostedServiceLocation {
  service_url: string;
  ui_url: string;
}

export interface ServiceDirectory {
  schema_version: 2;
  services: {
    spec_editor: HostedServiceLocation;
    circuit_designer: HostedServiceLocation;
    ai_assistant: HostedServiceLocation;
  };
  logging: { enabled: boolean; level: "info" | "debug" };
}

export interface SourceChangeEvent {
  sequence: number;
  document_id: string;
  source_revision_hash: string;
  origin: string;
  affected_entities: EntityRef[];
}

export interface ActivityState {
  executions: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  proposals: Array<Record<string, unknown>>;
  assistant_changes: Array<Record<string, unknown>>;
}

export interface EntityAction {
  action_id: string;
  title: string;
  version: string;
  produced_artifact_roles: string[];
}

export class SpecEditorHttpError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "SpecEditorHttpError";
  }
}

function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "diagnostics" in detail) {
    const diagnostics = (detail as { diagnostics: unknown }).diagnostics;
    if (Array.isArray(diagnostics)) return diagnostics.map(String).join(" ");
  }
  return JSON.stringify(detail) ?? "Request failed.";
}

export class SpecEditorHttpClient {
  constructor(private readonly baseUrl = "") {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === "object" && payload && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
      throw new SpecEditorHttpError(errorMessage(detail), response.status);
    }
    return payload as T;
  }

  openDocument(path: string): Promise<DocumentSnapshot> {
    return this.request("/documents/open", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
  }

  createDocument(path: string, title: string): Promise<DocumentSnapshot> {
    return this.request("/documents/create", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, title }),
    });
  }

  getA2UIBatch(): Promise<A2UIDocumentBatch> {
    return this.request("/documents/a2ui");
  }

  getSnapshot(): Promise<DocumentSnapshot> {
    return this.request("/documents/snapshot");
  }

  getServiceDirectory(): Promise<ServiceDirectory> {
    return this.request("/services");
  }

  applyTransaction(
    expectedSourceRevisionHash: string,
    operations: EditorTransactionOperation[],
  ): Promise<TransactionResult> {
    return this.request("/transactions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        expected_source_revision_hash: expectedSourceRevisionHash,
        operations,
      }),
    });
  }

  eventsUrl(): string {
    return `${this.baseUrl}/events`;
  }

  launchAssistant(ref: EntityRef): Promise<AssistantLaunch> {
    return this.request("/assistant/launch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        entity_kind: ref.entity_kind,
        entity_id: ref.entity_id,
      }),
    });
  }

  launchCircuitDesigner(entityKind: "component" | "design", entityId: string): Promise<CircuitDesignerLaunch> {
    return this.request("/circuit-designer/launch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ entity_kind: entityKind, entity_id: entityId }),
    });
  }

  getActivity(): Promise<ActivityState> {
    return Promise.all([
      this.request<{ executions: Array<Record<string, unknown>> }>("/executions"),
      this.request<{ artifacts: Array<Record<string, unknown>> }>("/artifacts"),
      this.request<{ proposals: Array<Record<string, unknown>> }>("/proposals"),
      this.request<{ assistant_changes: Array<Record<string, unknown>> }>("/assistant/changes"),
    ]).then(([executions, artifacts, proposals, assistantChanges]) => ({
      executions: executions.executions,
      artifacts: artifacts.artifacts,
      proposals: proposals.proposals,
      assistant_changes: assistantChanges.assistant_changes,
    }));
  }

  listEntityActions(ref: EntityRef): Promise<{ actions: EntityAction[] }> {
    return this.request(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/actions`);
  }

  executeEntityAction(ref: EntityRef, actionId: string): Promise<Record<string, unknown>> {
    return this.request(
      `/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/actions/${encodeURIComponent(actionId)}/executions`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ inputs: {}, input_artifact_ids: [] }),
      },
    );
  }

  reviewProposal(
    proposalId: string,
    decision: "accept" | "reject",
    sourceRevisionHash: string,
  ): Promise<Record<string, unknown>> {
    return this.request(`/proposals/${encodeURIComponent(proposalId)}/${decision}`, {
      method: "POST",
      headers: decision === "accept" ? { "content-type": "application/json" } : undefined,
      body: decision === "accept"
        ? JSON.stringify({ expected_source_revision_hash: sourceRevisionHash })
        : undefined,
    });
  }
}
