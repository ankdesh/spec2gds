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

export interface DocumentSnapshot {
  schema_version: string;
  document_id: string;
  source_revision_hash: string;
  components: unknown[];
  designs: unknown[];
  entry_designs: unknown[];
  bus_definitions: unknown[];
  abstraction_definitions: unknown[];
  component_compositions: unknown[];
  narrative: { blocks: NarrativeBlock[] };
  diagnostics: { source: string[]; artifacts: string[] };
}

export interface ActivityState {
  executions: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  proposals: Array<Record<string, unknown>>;
}

export interface EntityAction {
  action_id: string;
  title: string;
  version: string;
  produced_artifact_roles: string[];
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
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return payload as T;
  }

  listSamples(): Promise<{ samples: Array<{ name: string; path: string }> }> {
    return this.request("/samples");
  }

  openDocument(path: string): Promise<DocumentSnapshot> {
    return this.request("/documents/open", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
  }

  getA2UIBatch(): Promise<A2UIDocumentBatch> {
    return this.request("/documents/a2ui");
  }

  getActivity(): Promise<ActivityState> {
    return Promise.all([
      this.request<{ executions: Array<Record<string, unknown>> }>("/executions"),
      this.request<{ artifacts: Array<Record<string, unknown>> }>("/artifacts"),
      this.request<{ proposals: Array<Record<string, unknown>> }>("/proposals"),
    ]).then(([executions, artifacts, proposals]) => ({
      executions: executions.executions,
      artifacts: artifacts.artifacts,
      proposals: proposals.proposals,
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
