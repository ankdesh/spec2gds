import { createHash, randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { proposalError } from "./proposal-presentation.js";
import type { BindingInput, ProposalReview, ReviewState, SessionBinding } from "./types.js";

const now = (): string => new Date().toISOString();
const json = (value: unknown): string | null => value === undefined || value === null ? null : JSON.stringify(value);
const parse = (value: unknown): unknown => typeof value === "string" ? JSON.parse(value) : null;

export function artifactDigest(value: unknown): string {
  return `sha256:${createHash("sha256").update(JSON.stringify(value)).digest("hex")}`;
}

export class ProductState {
  readonly database: DatabaseSync;

  constructor(path: string) {
    mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
    this.database = new DatabaseSync(path);
    this.database.exec("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA synchronous=FULL;");
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS bindings (
        session_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK(status IN ('creating', 'active')),
        preset TEXT NOT NULL DEFAULT 'focused',
        domain TEXT NOT NULL CHECK(domain IN ('spec', 'circuit')),
        owner_url TEXT NOT NULL,
        document_id TEXT NOT NULL,
        scope TEXT NOT NULL CHECK(scope IN ('document', 'entity')),
        entity_kind TEXT,
        entity_id TEXT,
        title TEXT NOT NULL,
        workspace_key TEXT NOT NULL,
        workspace_title TEXT NOT NULL,
        workspace_path TEXT NOT NULL,
        workspace_domain TEXT NOT NULL CHECK(workspace_domain IN ('spec', 'circuit')),
        workspace_owner_url TEXT NOT NULL,
        workspace_document_id TEXT NOT NULL,
        archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS reviews (
        proposal_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES bindings(session_id) ON DELETE CASCADE,
        call_id TEXT NOT NULL,
        domain TEXT NOT NULL CHECK(domain IN ('spec', 'circuit')),
        state TEXT NOT NULL,
        base_revision TEXT NOT NULL,
        artifact_json TEXT NOT NULL,
        artifact_digest TEXT NOT NULL,
        preview_json TEXT,
        diagnostics_json TEXT,
        owner_result_json TEXT,
        version INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS reviews_session_created ON reviews(session_id, created_at);
      CREATE TABLE IF NOT EXISTS proposal_inputs (
        input_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES bindings(session_id) ON DELETE CASCADE,
        fields_json TEXT NOT NULL,
        values_json TEXT,
        created_at TEXT NOT NULL
      );
    `);
    const reviewColumns = new Set((this.database.prepare("PRAGMA table_info(reviews)").all() as Array<Record<string, unknown>>)
      .map(row => String(row.name)));
    if (!reviewColumns.has("error_json")) this.database.exec("ALTER TABLE reviews ADD COLUMN error_json TEXT");
    const bindingColumns = new Set((this.database.prepare("PRAGMA table_info(bindings)").all() as Array<Record<string, unknown>>)
      .map(row => String(row.name)));
    if (!bindingColumns.has("preset")) this.database.exec("ALTER TABLE bindings ADD COLUMN preset TEXT NOT NULL DEFAULT 'focused'");
  }

  close(): void { this.database.close(); }

  createProposalInput(sessionId: string, fields: readonly { name: string }[]): string {
    const inputId = randomUUID();
    this.database.prepare("INSERT INTO proposal_inputs(input_id,session_id,fields_json,created_at) VALUES(?,?,?,?)")
      .run(inputId, sessionId, JSON.stringify(fields.map(field => field.name)), now());
    return inputId;
  }

  confirmProposalInput(inputId: string, values: Record<string, string>): void {
    const row = this.database.prepare("SELECT fields_json FROM proposal_inputs WHERE input_id=?").get(inputId) as { fields_json: string } | undefined;
    if (!row) throw new Error("Unknown proposal input request.");
    const fields = JSON.parse(row.fields_json) as string[];
    if (Object.keys(values).length !== fields.length || fields.some(name => typeof values[name] !== "string" || !values[name]?.trim())
      || Object.keys(values).some(name => !fields.includes(name))) {
      throw new Error("Confirmed proposal values do not match the requested fields.");
    }
    this.database.prepare("UPDATE proposal_inputs SET values_json=? WHERE input_id=?").run(JSON.stringify(values), inputId);
  }

  confirmedProposalInput(sessionId: string, inputId: string): Record<string, string> | null {
    const row = this.database.prepare("SELECT values_json FROM proposal_inputs WHERE session_id=? AND input_id=?")
      .get(sessionId, inputId) as { values_json: string | null } | undefined;
    return row?.values_json ? JSON.parse(row.values_json) as Record<string, string> : null;
  }

  createBinding(sessionId: string, input: BindingInput & {
    ownerUrl: string;
    workspaceKey: string;
    workspaceTitle: string;
    workspacePath: string;
    workspaceDomain: "spec" | "circuit";
    workspaceOwnerUrl: string;
    workspaceDocumentId: string;
  }): SessionBinding {
    const timestamp = now();
    const scope = input.domain === "circuit" ? "document" : input.scope ?? "document";
    if (scope === "entity" && (!input.entityKind || !input.entityId)) {
      throw new Error("Entity bindings require entityKind and entityId.");
    }
    this.database.prepare(`
      INSERT INTO bindings(session_id,status,preset,domain,owner_url,document_id,scope,entity_kind,entity_id,title,workspace_key,workspace_title,workspace_path,workspace_domain,workspace_owner_url,workspace_document_id,created_at,updated_at)
      VALUES(?, 'creating', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(sessionId, input.preset ?? "focused", input.domain, input.ownerUrl, input.documentId, scope,
      input.entityKind ?? null, input.entityId ?? null,
      input.title?.trim() || `${input.domain === "spec" ? "Spec" : "Circuit"}: ${input.documentId}`,
      input.workspaceKey, input.workspaceTitle, input.workspacePath,
      input.workspaceDomain, input.workspaceOwnerUrl, input.workspaceDocumentId,
      timestamp, timestamp);
    return this.getBinding(sessionId)!;
  }

  activateBinding(sessionId: string): SessionBinding {
    this.database.prepare("UPDATE bindings SET status='active', updated_at=? WHERE session_id=? AND status='creating'")
      .run(now(), sessionId);
    const binding = this.getBinding(sessionId);
    if (!binding) throw new Error("Binding activation failed.");
    return binding;
  }

  deleteBinding(sessionId: string): void {
    this.database.prepare("DELETE FROM bindings WHERE session_id=?").run(sessionId);
  }

  listBindings(includeArchived = false): SessionBinding[] {
    const rows = this.database.prepare(
      `SELECT * FROM bindings WHERE status='active'${includeArchived ? "" : " AND archived=0"} ORDER BY updated_at DESC`,
    ).all();
    return rows.map(row => this.binding(row as Record<string, unknown>));
  }

  listCreatingBindings(): SessionBinding[] {
    return (this.database.prepare("SELECT * FROM bindings WHERE status='creating'").all() as Record<string, unknown>[])
      .map(row => this.binding(row));
  }

  getBinding(sessionId: string): SessionBinding | null {
    const row = this.database.prepare("SELECT * FROM bindings WHERE session_id=?").get(sessionId);
    return row ? this.binding(row as Record<string, unknown>) : null;
  }

  touchBinding(sessionId: string): void {
    this.database.prepare("UPDATE bindings SET updated_at=? WHERE session_id=?").run(now(), sessionId);
  }

  updateBinding(sessionId: string, values: { title?: string; archived?: boolean }): SessionBinding {
    const current = this.getBinding(sessionId);
    if (!current) throw new Error("Unknown assistant session.");
    const title = values.title === undefined ? current.title : values.title.trim();
    if (!title) throw new Error("Conversation title cannot be empty.");
    this.database.prepare("UPDATE bindings SET title=?, archived=?, updated_at=? WHERE session_id=?")
      .run(title, values.archived === undefined ? Number(current.archived) : Number(values.archived), now(), sessionId);
    return this.getBinding(sessionId)!;
  }

  recoverInterruptedReviews(): number {
    const result = this.database.prepare(`
      UPDATE reviews SET state='reconcile', version=version+1, updated_at=? WHERE state='applying'
    `).run(now());
    return Number(result.changes);
  }

  createReview(input: Omit<ProposalReview, "artifactDigest" | "version" | "createdAt" | "updatedAt">): ProposalReview {
    const timestamp = now();
    const digest = artifactDigest(input.artifact);
    this.database.prepare(`
      INSERT INTO reviews(proposal_id,session_id,call_id,domain,state,base_revision,artifact_json,artifact_digest,preview_json,diagnostics_json,error_json,owner_result_json,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    `).run(input.proposalId, input.sessionId, input.callId, input.domain, input.state,
      input.baseRevision, json(input.artifact), digest, json(input.preview), json(input.diagnostics),
      json(input.error), json(input.ownerResult), timestamp, timestamp);
    this.touchBinding(input.sessionId);
    return this.getReview(input.sessionId, input.proposalId)!;
  }

  getReview(sessionId: string, proposalId: string): ProposalReview | null {
    const row = this.database.prepare("SELECT * FROM reviews WHERE session_id=? AND proposal_id=?")
      .get(sessionId, proposalId);
    return row ? this.review(row as Record<string, unknown>) : null;
  }

  listReviews(sessionId: string): ProposalReview[] {
    return (this.database.prepare("SELECT * FROM reviews WHERE session_id=? ORDER BY created_at").all(sessionId) as Record<string, unknown>[])
      .map(row => this.review(row));
  }

  discardOpenReviews(sessionId: string, domain: "spec" | "circuit"): number {
    const result = this.database.prepare(`
      UPDATE reviews SET state='discarded', version=version+1, updated_at=?
      WHERE session_id=? AND domain=? AND state IN ('ready','rejected','stale')
    `).run(now(), sessionId, domain);
    if (result.changes) this.touchBinding(sessionId);
    return Number(result.changes);
  }

  markRevisionStale(sessionId: string, revision: string): number {
    const binding = this.getBinding(sessionId);
    if (!binding) return 0;
    const stale = this.listReviews(sessionId).filter(review => review.baseRevision !== revision && ["ready", "rejected"].includes(review.state));
    const detail = "The owner revision changed after this preview.";
    for (const review of stale) {
      this.transitionReview(sessionId, review.proposalId, [review.state], "stale", {
        diagnostics: detail,
        error: proposalError(binding, review.proposalId, "STALE_REVISION", detail, true),
      });
    }
    return stale.length;
  }

  transitionReview(
    sessionId: string,
    proposalId: string,
    expected: ReviewState[],
    state: ReviewState,
    values: { preview?: unknown; diagnostics?: unknown; error?: unknown; ownerResult?: unknown } = {},
  ): ProposalReview {
    const current = this.getReview(sessionId, proposalId);
    if (!current) throw new Error("Unknown proposal review.");
    if (!expected.includes(current.state)) throw new Error(`Review is ${current.state}; expected ${expected.join(" or ")}.`);
    const result = this.database.prepare(`
      UPDATE reviews SET state=?, preview_json=?, diagnostics_json=?, error_json=?, owner_result_json=?, version=version+1, updated_at=?
      WHERE session_id=? AND proposal_id=? AND version=?
    `).run(state,
      values.preview === undefined ? json(current.preview) : json(values.preview),
      values.diagnostics === undefined ? json(current.diagnostics) : json(values.diagnostics),
      values.error === undefined ? json(current.error) : json(values.error),
      values.ownerResult === undefined ? json(current.ownerResult) : json(values.ownerResult),
      now(), sessionId, proposalId, current.version);
    if (result.changes !== 1) throw new Error("Review changed concurrently; reload and retry.");
    this.touchBinding(sessionId);
    return this.getReview(sessionId, proposalId)!;
  }

  private binding(row: Record<string, unknown>): SessionBinding {
    return {
      sessionId: String(row.session_id), status: row.status as SessionBinding["status"],
      preset: (row.preset ?? "focused") as SessionBinding["preset"],
      domain: row.domain as SessionBinding["domain"], ownerUrl: String(row.owner_url),
      documentId: String(row.document_id), scope: row.scope as SessionBinding["scope"],
      entityKind: row.entity_kind === null ? null : String(row.entity_kind),
      entityId: row.entity_id === null ? null : String(row.entity_id), title: String(row.title),
      workspaceKey: String(row.workspace_key), workspaceTitle: String(row.workspace_title),
      workspacePath: String(row.workspace_path),
      workspaceDomain: row.workspace_domain as SessionBinding["workspaceDomain"],
      workspaceOwnerUrl: String(row.workspace_owner_url), workspaceDocumentId: String(row.workspace_document_id),
      archived: Boolean(row.archived), createdAt: String(row.created_at), updatedAt: String(row.updated_at),
    };
  }

  private review(row: Record<string, unknown>): ProposalReview {
    return {
      proposalId: String(row.proposal_id), sessionId: String(row.session_id), callId: String(row.call_id),
      domain: row.domain as ProposalReview["domain"], state: row.state as ReviewState,
      baseRevision: String(row.base_revision), artifact: parse(row.artifact_json) as Record<string, unknown>,
      artifactDigest: String(row.artifact_digest), preview: parse(row.preview_json) as Record<string, unknown> | null,
      diagnostics: parse(row.diagnostics_json), error: parse(row.error_json) as ProposalReview["error"], ownerResult: parse(row.owner_result_json),
      version: Number(row.version), createdAt: String(row.created_at), updatedAt: String(row.updated_at),
    };
  }
}
