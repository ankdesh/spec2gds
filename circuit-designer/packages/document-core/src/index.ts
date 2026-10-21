/** Renderer-neutral specification document contracts and local projection helpers.
 * The Spec service supplies source identity, cells and edit capabilities. Views
 * consume this projection without reinterpreting package XML or acquiring a
 * second mutation boundary; source edits return through host callbacks. */
import type { CircuitDocument, CircuitSourceBindingV1 } from "@spec2gds/circuit-core";

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
  display_text?: string;
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
  display_text?: string;
}

export type SectionValidationStatus = "verified" | "warnings" | "unverified" | "errors";

export interface SectionDiagnostic {
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  blocking: boolean;
  file_path?: string | null;
  source_kind?: "section" | "generated" | null;
}

export interface EntityContentSection {
  section_id: string;
  section_type: "text" | "ports" | "sv";
  type_version: number;
  title: string;
  parent: EntityRef;
  payload: { content?: string; media_type?: string; source_path?: string; count?: number };
  editable: boolean;
  deletable: boolean;
  validation_status: SectionValidationStatus;
  diagnostics: SectionDiagnostic[];
}

export interface PersistedEntitySection {
  section_id: string;
  section_type: "sv";
  type_version: number;
  title: string;
  parent: EntityRef;
  media_type: "text/x-systemverilog";
  source_path: string;
  source_sha256: string;
  content: string;
}

export interface AvailableSectionType {
  section_type: "sv";
  type_version: number;
  title: string;
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
  entity_labels?: Record<string, { name: string; anchor: string; qualified_name?: string }>;
}

export interface DesignTopologyLiveViewOptionsV1 {
  schema_version: 1;
  status: "ready" | "empty" | "unavailable";
  circuit_document?: CircuitDocument;
  omitted_bus_items: string[];
  omitted_ports: string[];
  message?: string;
  read_only?: boolean;
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
  content_sections: EntityContentSection[];
  available_section_types: AvailableSectionType[];
  implementation_kind?: "sv" | "internal_design" | "missing" | null;
  preview_mode?: "interface" | "design" | null;
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
  display_name?: string;
  parameters?: ParameterInput[];
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

export interface ParameterInput { name: string; rtl_type: string; value: string; description: string }
export interface ComponentVerification {
  target: EntityRef;
  source_revision_hash: string;
  status: "passed" | "failed" | "unverified" | "stale";
  tool_version: string;
  diagnostics: Array<{ code: string; message: string; blocking?: boolean; line?: number | null; column?: number | null; file_path?: string | null; source_kind?: "section" | "generated" | null }>;
  functional_simulation: "unverified";
  interfaces?: Array<{ component: string; status: string; ports: Array<{ name: string; range: string | null; width: number | null }> }>;
}

export type EditorTransactionOperation =
  | { type: "create_entity"; kind: "component" | "design"; name: string; entry_design?: boolean }
  | { type: "delete_document"; ref: EntityRef }
  | { type: "delete_component_port"; component: EntityRef; name: string }
  | { type: "update_parameter"; component: EntityRef; parameter: ParameterInput }
  | { type: "delete_parameter"; component: EntityRef; name: string }
  | { type: "add_entry_design" | "remove_entry_design"; design: EntityRef }
  | { type: "set_internal_design"; component: EntityRef; internal_design: EntityRef }
  | { type: "clear_internal_design"; component: EntityRef }
  | { type: "set_document_title"; title: string }
  | { type: "upsert_narrative_block"; block: NarrativeBlock }
  | ({ type: "set_entity_metadata"; entity: EntityRef } & EntityMetadataInput)
  | { type: "upsert_instance"; design: EntityRef; instance: ComponentInstanceInput }
  | { type: "add_component_port"; component: EntityRef; port: ComponentPortInput }
  | {
    type: "update_component_port";
    component: EntityRef;
    name: string;
    port: ComponentPortUpdateInput;
  }
  | {
    type: "upsert_entity_section";
    parent: EntityRef;
    section_type: "sv";
    type_version: 1;
    section_id?: string;
    payload: { content: string };
  }
  | {
    type: "delete_entity_section";
    parent: EntityRef;
    section_type: "sv";
    section_id?: string;
  };

export interface TransactionResult {
  committed: true;
  snapshot: DocumentSnapshot;
  section_validation: Array<{
    section_id: string;
    status: SectionValidationStatus;
    diagnostics: SectionDiagnostic[];
  }>;
}

export interface DocumentSnapshot {
  verifications?: ComponentVerification[];
  owner_document_key: string;
  schema_version: string;
  document_id: string;
  source_path?: string;
  source_revision_hash: string;
  components: HardwareEntitySummary[];
  designs: HardwareEntitySummary[];
  entry_designs: HardwareEntitySummary[];
  bus_definitions: unknown[];
  abstraction_definitions: unknown[];
  component_compositions: ComponentComposition[];
  narrative: { title: string; blocks: NarrativeBlock[] };
  diagnostics: { source: string[]; artifacts: string[] };
  entity_sections: PersistedEntitySection[];
  section_validation: TransactionResult["section_validation"];
}

export interface CircuitDesignerLaunch {
  document_id: string;
  entity_id: string;
  entity_kind: "component" | "design";
  editor_url: string;
  reused_session: boolean;
  omitted_bus_items: string[];
  omitted_ports: string[];
  source_binding?: CircuitSourceBindingV1;
}

export interface AssistantLaunch {
  assistant_url: string;
  target: EntityRef;
}

export type AssistantDocumentLaunch = {
  assistant_url: string;
  document_id: string;
  source_revision_hash: string;
  scope: "document";
} | {
  assistant_url: string;
  document_id: null;
  source_revision_hash: null;
  scope: "unbound";
};

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

export interface FilesystemDirectoryListing {
  path: string;
  parent: string | null;
  home: string;
  separator: "/" | "\\";
  roots: string[];
  directories: Array<{ name: string; path: string }>;
  specifications: Array<{ name: string; path: string }>;
}

export interface SourceChangeEvent {
  owner_document_key: string;
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

export interface DocumentView {
  snapshot: DocumentSnapshot;
  a2ui: A2UIDocumentBatch;
  activity: ActivityState;
  approval_policy: "automatic" | "review";
  event_cursor: number;
  source_revision_hash: string;
}

export interface AssistantHistoryPage {
  items: Array<Record<string, unknown>>;
  next_cursor: number | null;
}

export interface EntityAction {
  action_id: string;
  title: string;
  version: string;
  produced_artifact_roles: string[];
}

export interface ActivityDefinition {
  activity_id: string;
  version: string;
  title: string;
  description: string;
  requires_workspace_output: boolean;
  artifact_roles: string[];
}

export interface EntityActivity {
  definition: ActivityDefinition;
  availability: { available: boolean; diagnostics: string[] };
}

export class SpecEditorHttpError extends Error {
  constructor(message: string, readonly status: number, readonly detail?: unknown) {
    super(message);
    this.name = "SpecEditorHttpError";
  }
}

function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  if (detail && typeof detail === "object" && "diagnostics" in detail) {
    const diagnostics = (detail as { diagnostics: unknown }).diagnostics;
    if (Array.isArray(diagnostics)) return diagnostics.map(String).join(" ");
  }
  return JSON.stringify(detail) ?? "Request failed.";
}

export class SpecEditorHttpClient {
  private serviceDocumentKey: string | null = null;
  constructor(private readonly baseUrl = "") {}

  bindDocument(key: string): void { this.serviceDocumentKey = key; }

  private documentPath(path: string, key = this.serviceDocumentKey): string {
    if (!key) return path;
    return `${path}${path.includes("?") ? "&" : "?"}owner_document_key=${encodeURIComponent(key)}`;
  }

  getDocumentView(key = this.serviceDocumentKey): Promise<DocumentView> {
    return this.request(this.documentPath("/documents/view", key));
  }

  getAssistantHistory(before?: number): Promise<AssistantHistoryPage> {
    return this.request(this.documentPath(`/assistant/history?limit=25${before === undefined ? "" : `&before=${before}`}`));
  }

  getAssistantSubmission(id: string): Promise<Record<string, unknown>> {
    return this.request(this.documentPath(`/assistant/proposals/${encodeURIComponent(id)}`));
  }

  decideAssistantSubmission(id: string, decision: "approve" | "reject"): Promise<Record<string, unknown>> {
    return this.request(this.documentPath(`/assistant/proposals/${encodeURIComponent(id)}/${decision}`), { method: "POST" });
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof payload === "object" && payload && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
      throw new SpecEditorHttpError(errorMessage(detail), response.status, detail);
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

  createDocument(path: string, title: string, requestId?: string): Promise<DocumentSnapshot> {
    return this.request("/documents/create", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, title, ...(requestId ? { request_id: requestId } : {}) }),
    });
  }

  browseDirectories(path?: string): Promise<FilesystemDirectoryListing> {
    const query = path ? `?${new URLSearchParams({ path }).toString()}` : "";
    return this.request(`/filesystem/directories${query}`);
  }

  createDirectory(parent: string, name: string): Promise<FilesystemDirectoryListing> {
    return this.request("/filesystem/directories", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ parent, name }),
    });
  }

  getA2UIBatch(): Promise<A2UIDocumentBatch> {
    return this.request(this.documentPath("/documents/a2ui"));
  }

  getSnapshot(): Promise<DocumentSnapshot> {
    return this.request(this.documentPath("/documents/snapshot"));
  }

  getServiceDirectory(): Promise<ServiceDirectory> {
    return this.request("/services");
  }

  applyTransaction(
    expectedSourceRevisionHash: string,
    operations: EditorTransactionOperation[],
    validationMode: "strict" | "authoring" = "strict",
  ): Promise<TransactionResult> {
    return this.request(this.documentPath("/transactions"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ...(validationMode === "authoring" ? { validation_mode: validationMode } : {}),
        expected_source_revision_hash: expectedSourceRevisionHash,
        operations,
      }),
    });
  }

  verifyComponent(ref: EntityRef, revision: string): Promise<ComponentVerification> {
    return this.request(this.documentPath(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/verify`), {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_source_revision_hash: revision }),
    });
  }

  eventsUrl(cursor = 0): string {
    return `${this.baseUrl}${this.documentPath(`/events?cursor=${cursor}`)}`;
  }

  activityEventsUrl(): string {
    return `${this.baseUrl}${this.documentPath("/activity-events")}`;
  }

  launchAssistant(ref: EntityRef): Promise<AssistantLaunch> {
    return this.request(this.documentPath("/assistant/launch"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        entity_kind: ref.entity_kind,
        entity_id: ref.entity_id,
      }),
    });
  }

  launchDocumentAssistant(attachActiveDocument: boolean): Promise<AssistantDocumentLaunch> {
    return this.request(this.documentPath("/assistant/launch/document"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ attach_active_document: attachActiveDocument }),
    });
  }

  launchCircuitDesigner(entityKind: "component" | "design", entityId: string): Promise<CircuitDesignerLaunch> {
    return this.request(this.documentPath("/circuit-designer/launch"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ entity_kind: entityKind, entity_id: entityId }),
    });
  }

  getActivity(): Promise<ActivityState> {
    return this.getDocumentView().then(value => value.activity);
  }

  listEntityActivities(ref: EntityRef): Promise<{ activities: EntityActivity[] }> {
    return this.request(this.documentPath(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/activities`));
  }

  launchEntityActivity(
    ref: EntityRef,
    activityId: string,
    expectedSourceRevisionHash: string,
  ): Promise<Record<string, unknown>> {
    return this.request(
      this.documentPath(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/activities/${encodeURIComponent(activityId)}/executions`),
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ expected_source_revision_hash: expectedSourceRevisionHash }),
      },
    );
  }

  cancelExecution(executionId: string): Promise<Record<string, unknown>> {
    return this.request(this.documentPath(`/executions/${encodeURIComponent(executionId)}/cancel`), { method: "POST" });
  }

  artifactContentUrl(artifactId: string, documentKey = this.serviceDocumentKey): string {
    return `${this.baseUrl}${this.documentPath(`/artifacts/${encodeURIComponent(artifactId)}/content`, documentKey)}`;
  }

  listEntityActions(ref: EntityRef): Promise<{ actions: EntityAction[] }> {
    return this.request(this.documentPath(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/actions`));
  }

  executeEntityAction(ref: EntityRef, actionId: string): Promise<Record<string, unknown>> {
    return this.request(
      this.documentPath(`/entities/${ref.entity_kind}/${encodeURIComponent(ref.entity_id)}/actions/${encodeURIComponent(actionId)}/executions`),
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
