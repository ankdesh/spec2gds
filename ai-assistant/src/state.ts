/** Product persistence for owner bindings, review claims and recoverable creation.
 * Native transcripts/event ledgers live in separate stores. A successful local
 * claim precedes the owner HTTP call; uncertainty must be reconciled by identity
 * rather than automatically repeating a possibly completed mutation. */
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { proposalError } from "./proposal-presentation.js";
import type { BindingInput, ProposalReview, ReviewState, SessionBinding, SourceCreationRequest } from "./types.js";

const now = (): string => new Date().toISOString();
const json = (value: unknown): string | null => value === undefined || value === null ? null : JSON.stringify(value);
function parseProductRecord(value: string): any {
  const record = JSON.parse(value);
  if (!record || typeof record !== "object" || Array.isArray(record)) return record;
  for (const [legacy, canonical] of Object.entries({ ownerUrl: "serviceUrl", ownerDocumentKey: "serviceDocumentKey", destinationOwnerDocumentKey: "destinationServiceDocumentKey", workspaceOwnerUrl: "workspaceServiceUrl", ownerResult: "serviceResult" })) {
    if (Object.hasOwn(record, legacy) && !Object.hasOwn(record, canonical)) record[canonical] = record[legacy];
  }
  if (typeof record.error_code === "string" && record.error_code.startsWith("OWNER_")) record.error_code = record.error_code.replace("OWNER_", "SERVICE_");
  return record;
}
const parse = (value: unknown): unknown => typeof value === "string" ? parseProductRecord(value) : null;

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
      CREATE TABLE IF NOT EXISTS architecture_reviews (
        review_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, call_id TEXT NOT NULL,
        status TEXT NOT NULL, record_json TEXT NOT NULL, UNIQUE(session_id, call_id)
      );
      CREATE TABLE IF NOT EXISTS proposal_inputs (
        input_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES bindings(session_id) ON DELETE CASCADE,
        fields_json TEXT NOT NULL,
        values_json TEXT,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS source_creation_requests (
        request_id TEXT PRIMARY KEY,
        source_session_id TEXT NOT NULL,
        call_id TEXT NOT NULL,
        status TEXT NOT NULL,
        request_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(source_session_id, call_id)
      );
    `);
    const reviewColumns = new Set((this.database.prepare("PRAGMA table_info(reviews)").all() as Array<Record<string, unknown>>)
      .map(row => String(row.name)));
    if (!reviewColumns.has("error_json")) this.database.exec("ALTER TABLE reviews ADD COLUMN error_json TEXT");
    const bindingColumns = new Set((this.database.prepare("PRAGMA table_info(bindings)").all() as Array<Record<string, unknown>>)
      .map(row => String(row.name)));
    if (!bindingColumns.has("preset")) this.database.exec("ALTER TABLE bindings ADD COLUMN preset TEXT NOT NULL DEFAULT 'focused'");
    if (!bindingColumns.has("owner_document_key")) this.database.exec("ALTER TABLE bindings ADD COLUMN owner_document_key TEXT");
    if (!bindingColumns.has("source_name")) this.database.exec("ALTER TABLE bindings ADD COLUMN source_name TEXT");
    for (const review of this.listArchitectureReviews()) {
      if (!review.reviewNumber) this.storeArchitecture(review);
    }
  }

  close(): void { this.database.close(); }

  architectureReview(id: string): Record<string, any> | null {
    const row = this.database.prepare("SELECT record_json FROM architecture_reviews WHERE review_id=?")
      .get(id) as { record_json: string } | undefined;
    return row ? parseProductRecord(row.record_json) : null;
  }

  architectureForCall(sessionId: string, callId: string): Record<string, any> | null {
    const row = this.database.prepare("SELECT record_json FROM architecture_reviews WHERE session_id=? AND call_id=?")
      .get(sessionId, callId) as { record_json: string } | undefined;
    return row ? parseProductRecord(row.record_json) : null;
  }

  listArchitectureReviews(): Record<string, any>[] {
    return (this.database.prepare("SELECT record_json FROM architecture_reviews ORDER BY rowid").all() as Array<{record_json: string}>)
      .map(row => parseProductRecord(row.record_json));
  }

  storeArchitecture(record: Record<string, any>): void {
    if (!record.reviewNumber) {
      const scope = record.serviceDocumentKey || `new:${record.sessionId}`;
      const previous = this.listArchitectureReviews().filter(item => (item.serviceDocumentKey || `new:${item.sessionId}`) === scope);
      record.reviewNumber = Math.max(0, ...previous.map(item => Number(item.reviewNumber) || 0)) + 1;
    }
    this.database.prepare(`INSERT INTO architecture_reviews VALUES(?,?,?,?,?)
      ON CONFLICT(review_id) DO UPDATE SET status=excluded.status, record_json=excluded.record_json`)
      .run(record.reviewId, record.sessionId, record.callId, record.status, JSON.stringify(record));
  }

  decideArchitecture(id: string, decision: "approved" | "revised" | "cancelled", feedback: string): Record<string, any> {
    const record = this.architectureReview(id);
    if (!record) throw new Error("Unknown architecture review.");
    if (record.status === decision) return record;
    if (record.status !== "pending") throw new Error("This review has already been decided. Prepare a new review to change its architecture.");
    if (decision === "approved" && record.plan.open_questions.length) throw new Error("Resolve essential open questions in a revised architecture before approval.");
    const updated = { ...record, status: decision, feedback, decidedAt: now() };
    const result = this.database.prepare(`UPDATE architecture_reviews SET status=?,record_json=? WHERE review_id=? AND status='pending'`)
      .run(decision, JSON.stringify(updated), id);
    if (Number(result.changes) !== 1) throw new Error("Architecture decision changed concurrently; reload the card.");
    return updated;
  }

  requireArchitecture(sessionId: string, id: string | undefined, revision?: string): Record<string, any> {
    const record = id ? this.architectureReview(id) : null;
    const binding = this.getBinding(sessionId);
    const sameSource = Boolean(binding?.serviceDocumentKey && binding.serviceDocumentKey === record?.serviceDocumentKey
      && binding.documentId === record?.documentId && binding.scope === record?.scope
      && binding.entityId === (record?.entityId ?? null));
    const sameDestination = Boolean(binding?.serviceDocumentKey && binding.serviceDocumentKey === record?.destinationServiceDocumentKey
      && binding.documentId === record?.destinationDocumentId && binding.scope === "document");
    if (!record || record.status !== "approved" || (![record.sessionId, record.destinationSessionId].includes(sessionId) && !sameSource && !sameDestination)) {
      throw new Error("Prepare an architecture review and obtain its approval before creating content or changing architecture. Supply architecture_review_id.");
    }
    const expected = sessionId === record.sessionId || sameSource ? record.sourceRevision : record.destinationSourceRevision;
    if (revision && expected && expected !== revision) {
      throw new Error("Architecture review is stale. Reread the stored specification and obtain approval of an updated architecture.");
    }
    return record;
  }

  getSourceCreation(requestId: string): SourceCreationRequest | null {
    const row = this.database.prepare("SELECT request_json FROM source_creation_requests WHERE request_id=?")
      .get(requestId) as { request_json: string } | undefined;
    return row ? parseProductRecord(row.request_json) as SourceCreationRequest : null;
  }

  sourceCreationForCall(sessionId: string, callId: string): SourceCreationRequest | null {
    const row = this.database.prepare("SELECT request_json FROM source_creation_requests WHERE source_session_id=? AND call_id=?")
      .get(sessionId, callId) as { request_json: string } | undefined;
    return row ? parseProductRecord(row.request_json) as SourceCreationRequest : null;
  }

  sourceCreationForArchitecture(reviewId: string): SourceCreationRequest | null {
    const row = this.database.prepare("SELECT request_json FROM source_creation_requests WHERE json_extract(request_json,'$.architectureReviewId')=? AND status<>'cancelled' ORDER BY rowid DESC LIMIT 1")
      .get(reviewId) as { request_json: string } | undefined;
    return row ? parseProductRecord(row.request_json) as SourceCreationRequest : null;
  }

  storeSourceCreation(request: SourceCreationRequest): void {
    this.database.prepare(`INSERT INTO source_creation_requests(request_id,source_session_id,call_id,status,request_json,updated_at)
      VALUES(?,?,?,?,?,?) ON CONFLICT(request_id) DO UPDATE SET status=excluded.status,request_json=excluded.request_json,updated_at=excluded.updated_at`)
      .run(request.requestId, request.sourceSessionId, request.callId, request.status, JSON.stringify(request), now());
  }

  claimSourceCreation(request: SourceCreationRequest): boolean {
    const result = this.database.prepare(`UPDATE source_creation_requests SET status='creating',request_json=?,updated_at=?
      WHERE request_id=? AND status='pending'`).run(JSON.stringify({ ...request, status: "creating" }), now(), request.requestId);
    return Number(result.changes) === 1;
  }

  retrySourceCreation(request: SourceCreationRequest): boolean {
    const result = this.database.prepare(`UPDATE source_creation_requests SET status='pending',request_json=?,updated_at=?
      WHERE request_id=? AND status='uncertain'`).run(JSON.stringify({ ...request, status: "pending", error: null }), now(), request.requestId);
    return Number(result.changes) === 1;
  }

  cancelSourceCreation(request: SourceCreationRequest): boolean {
    const cancelled = { ...request, status: "cancelled" as const, error: null };
    const result = this.database.prepare(`UPDATE source_creation_requests SET status='cancelled',request_json=?,updated_at=?
      WHERE request_id=? AND status='pending'`).run(JSON.stringify(cancelled), now(), request.requestId);
    return Number(result.changes) === 1;
  }

  // A local creating flag cannot tell whether the remote package save happened.
  // Recover as uncertain and reconcile the owner receipt before any retry.
  recoverInterruptedSourceCreations(): void {
    const rows = this.database.prepare("SELECT request_id FROM source_creation_requests WHERE status='creating'")
      .all() as Array<{ request_id: string }>;
    for (const row of rows) {
      const request = this.getSourceCreation(row.request_id)!;
      this.storeSourceCreation({ ...request, status: "uncertain",
        error: "Creation was interrupted. Check the destination in the Spec Editor before creating another package; this request will not be repeated automatically." });
    }
  }

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
    serviceUrl: string;
    workspaceKey: string;
    workspaceTitle: string;
    workspacePath: string;
    workspaceDomain: "spec" | "circuit";
    workspaceServiceUrl: string;
    workspaceDocumentId: string;
  }): SessionBinding {
    const timestamp = now();
    const scope = input.domain === "circuit" ? "document" : input.scope ?? "document";
    if (scope === "entity" && (!input.entityKind || !input.entityId)) {
      throw new Error("Entity bindings require entityKind and entityId.");
    }
    this.database.prepare(`
      INSERT INTO bindings(session_id,status,preset,domain,owner_url,document_id,scope,entity_kind,entity_id,title,workspace_key,workspace_title,workspace_path,workspace_domain,workspace_owner_url,workspace_document_id,created_at,updated_at,owner_document_key)
      VALUES(?, 'creating', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(sessionId, input.preset ?? "focused", input.domain, input.serviceUrl, input.documentId, scope,
      input.entityKind ?? null, input.entityId ?? null,
      input.title?.trim() || input.sourceName || (input.domain === "spec" ? "Specification" : "Circuit"),
      input.workspaceKey, input.workspaceTitle, input.workspacePath,
      input.workspaceDomain, input.workspaceServiceUrl, input.workspaceDocumentId,
      timestamp, timestamp, input.serviceDocumentKey ?? null);
    if (input.sourceName) this.refreshSourceName(sessionId, input.sourceName);
    return this.getBinding(sessionId)!;
  }

  refreshSourceName(sessionId: string, sourceName: string, workspaceTitle?: string): SessionBinding {
    this.database.prepare("UPDATE bindings SET source_name=? WHERE session_id=?").run(sourceName, sessionId);
    if (workspaceTitle) this.database.prepare("UPDATE bindings SET workspace_title=? WHERE workspace_key=(SELECT workspace_key FROM bindings WHERE session_id=?)").run(workspaceTitle, sessionId);
    return this.getBinding(sessionId)!;
  }

  // Reservation is durable before native session creation. Activation is the
  // second phase; startup can reconcile a transcript created before a crash.
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

  pinServiceDocument(sessionId: string, key: string): void {
    const binding = this.getBinding(sessionId);
    if (!binding || binding.domain !== "spec") throw new Error("Unknown Spec binding.");
    if (binding.serviceDocumentKey && binding.serviceDocumentKey !== key) throw new Error("A chat cannot switch package bindings.");
    this.database.prepare("UPDATE bindings SET owner_document_key=? WHERE session_id=?").run(key, sessionId);
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
      json(input.error), json(input.serviceResult), timestamp, timestamp);
    this.touchBinding(input.sessionId);
    return this.getReview(input.sessionId, input.proposalId)!;
  }

  getReview(sessionId: string, proposalId: string): ProposalReview | null {
    const row = this.database.prepare("SELECT * FROM reviews WHERE session_id=? AND proposal_id=?")
      .get(sessionId, proposalId);
    return row ? this.review(row as Record<string, unknown>) : null;
  }

  reviewForCall(sessionId: string, callId: string): ProposalReview | null {
    const row = this.database.prepare("SELECT * FROM reviews WHERE session_id=? AND call_id=? AND domain='spec' ORDER BY created_at DESC LIMIT 1")
      .get(sessionId, callId);
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
    // Pending Spec artifacts stay pending until an explicit decision. The
    // owner revalidates their original revision at approval time.
    const stale = this.listReviews(sessionId).filter(review => review.domain !== "spec" && review.baseRevision !== revision && ["ready", "rejected"].includes(review.state));
    const detail = "The service revision changed after this preview.";
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
    values: { preview?: unknown; diagnostics?: unknown; error?: unknown; serviceResult?: unknown } = {},
  ): ProposalReview {
    const current = this.getReview(sessionId, proposalId);
    if (!current) throw new Error("Unknown proposal review.");
    if (!expected.includes(current.state)) throw new Error(`Review is ${current.state}; expected ${expected.join(" or ")}.`);
    // Reloaded state and its version form a compare-and-swap claim. Concurrent
    // buttons cannot both own an apply/send transition for the same artifact.
    const result = this.database.prepare(`
      UPDATE reviews SET state=?, preview_json=?, diagnostics_json=?, error_json=?, owner_result_json=?, version=version+1, updated_at=?
      WHERE session_id=? AND proposal_id=? AND version=?
    `).run(state,
      values.preview === undefined ? json(current.preview) : json(values.preview),
      values.diagnostics === undefined ? json(current.diagnostics) : json(values.diagnostics),
      values.error === undefined ? json(current.error) : json(values.error),
      values.serviceResult === undefined ? json(current.serviceResult) : json(values.serviceResult),
      now(), sessionId, proposalId, current.version);
    if (result.changes !== 1) throw new Error("Review changed concurrently; reload and retry.");
    this.touchBinding(sessionId);
    return this.getReview(sessionId, proposalId)!;
  }

  private binding(row: Record<string, unknown>): SessionBinding {
    return {
      sessionId: String(row.session_id), status: row.status as SessionBinding["status"],
      preset: (row.preset ?? "focused") as SessionBinding["preset"],
      domain: row.domain as SessionBinding["domain"], serviceUrl: String(row.owner_url),
      serviceDocumentKey: typeof row.owner_document_key === "string" ? row.owner_document_key : null,
      documentId: String(row.document_id), scope: row.scope as SessionBinding["scope"],
      entityKind: row.entity_kind === null ? null : String(row.entity_kind),
      entityId: row.entity_id === null ? null : String(row.entity_id), title: String(row.title),
      sourceName: typeof row.source_name === "string" ? row.source_name : (row.domain === "spec" ? "Specification" : "Circuit"),
      workspaceKey: String(row.workspace_key), workspaceTitle: String(row.workspace_title),
      workspacePath: String(row.workspace_path),
      workspaceDomain: row.workspace_domain as SessionBinding["workspaceDomain"],
      workspaceServiceUrl: String(row.workspace_owner_url), workspaceDocumentId: String(row.workspace_document_id),
      archived: Boolean(row.archived), createdAt: String(row.created_at), updatedAt: String(row.updated_at),
    };
  }

  private review(row: Record<string, unknown>): ProposalReview {
    return {
      proposalId: String(row.proposal_id), sessionId: String(row.session_id), callId: String(row.call_id),
      domain: row.domain as ProposalReview["domain"], state: row.state as ReviewState,
      baseRevision: String(row.base_revision), artifact: parse(row.artifact_json) as Record<string, unknown>,
      artifactDigest: String(row.artifact_digest), preview: parse(row.preview_json) as Record<string, unknown> | null,
      diagnostics: parse(row.diagnostics_json), error: parse(row.error_json) as ProposalReview["error"], serviceResult: parse(row.owner_result_json),
      version: Number(row.version), createdAt: String(row.created_at), updatedAt: String(row.updated_at),
    };
  }
}
