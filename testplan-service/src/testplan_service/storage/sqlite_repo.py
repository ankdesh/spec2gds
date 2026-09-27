"""SQLite metadata and record repository for Verification Planner."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any
import uuid

from testplan_service.domain.evidence import (
    CampaignPurpose,
    CampaignState,
    EvaluationProfile,
    EvidenceCampaign,
    EvidenceObservation,
    EvidenceReport,
    EvidenceRun,
    ObservationOutcome,
    RealizationDescriptor,
    RunDisposition,
    RunDispositionKind,
    RunStatus,
)
from testplan_service.domain.models import (
    Intent,
    Issue,
    PlanCheckpoint,
    PlanHeader,
    Requirement,
    Section,
    SourceAuditEntry,
)
from testplan_service.domain.policies import IntentWaiver
from testplan_service.domain.recipes import (
    BackendConfiguration,
    ProducerManifest,
    Recipe,
    TargetBindingSet,
)
from testplan_service.exceptions import (
    CampaignFrozenError,
    CampaignNotFoundError,
    CampaignRevisionConflictError,
    IdempotencyMismatchError,
    PlanNotFoundError,
    ProfileNotFoundError,
    RecordNotFoundError,
    RevisionConflictError,
    RunNotFoundError,
    StorageError,
)
from testplan_service.integrations.models import SourceSnapshotView


class SqlitePlanRepository:
    """Thread-safe, WAL-enabled SQLite persistence layer for Verification Planner."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    root_scope_id TEXT NOT NULL,
                    owner_label TEXT,
                    tags_json TEXT NOT NULL,
                    edit_revision INTEGER NOT NULL DEFAULT 1,
                    schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    source_document_id TEXT NOT NULL,
                    source_revision_hash TEXT NOT NULL,
                    root_ref_json TEXT,
                    view_json TEXT NOT NULL,
                    blob_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_audits (
                    plan_id TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    reason TEXT,
                    linked_requirement_ids_json TEXT NOT NULL,
                    reviewer_label TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, section_id),
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS records (
                    plan_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    record_revision INTEGER NOT NULL DEFAULT 1,
                    scope_id TEXT NOT NULL,
                    parent_id TEXT,
                    archived INTEGER NOT NULL DEFAULT 0,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, id),
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS key_counters (
                    plan_id TEXT NOT NULL,
                    prefix TEXT NOT NULL,
                    last_number INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (plan_id, prefix),
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS command_log (
                    plan_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    base_edit_revision INTEGER NOT NULL,
                    new_edit_revision INTEGER NOT NULL,
                    payload_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, request_id),
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    layer TEXT NOT NULL DEFAULT 'plan',
                    upstream_checkpoint_id TEXT,
                    snapshot_id TEXT NOT NULL,
                    root_scope_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    reviewer_label TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    checklist_json TEXT NOT NULL,
                    acknowledged_warnings_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    edit_revision INTEGER NOT NULL,
                    evidence_sequence INTEGER NOT NULL DEFAULT 0,
                    changed_ids_json TEXT NOT NULL,
                    origin_request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    coverage_checkpoint_id TEXT NOT NULL,
                    source_snapshot_id TEXT NOT NULL,
                    source_snapshot_hash TEXT NOT NULL,
                    dut_source_hash TEXT NOT NULL,
                    root_occurrence_id TEXT NOT NULL,
                    resolved_parameters_json TEXT NOT NULL,
                    clock_reset_config_json TEXT NOT NULL,
                    realization_descriptors_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    coverage_checkpoint_id TEXT NOT NULL,
                    required_profile_ids_json TEXT NOT NULL,
                    included_run_ids_json TEXT NOT NULL,
                    run_dispositions_json TEXT NOT NULL,
                    waivers_json TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    state TEXT NOT NULL,
                    campaign_revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS campaign_commands (
                    campaign_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    base_campaign_revision INTEGER NOT NULL,
                    new_campaign_revision INTEGER NOT NULL,
                    payload_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (campaign_id, request_id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_runs (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    producer_id TEXT NOT NULL,
                    external_run_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    coverage_checkpoint_id TEXT NOT NULL,
                    producer_manifest_digest TEXT NOT NULL,
                    dut_source_hash TEXT NOT NULL,
                    configuration_hash TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_version TEXT NOT NULL,
                    seed INTEGER,
                    synthetic INTEGER NOT NULL DEFAULT 0,
                    producer_kind TEXT NOT NULL,
                    trust_label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    raw_artifact_digests_json TEXT NOT NULL,
                    parser_adapter_id TEXT NOT NULL,
                    validation_diagnostics_json TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    imported_at TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    UNIQUE (producer_id, external_run_id, attempt_id),
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_observations (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    producer_observation_id TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    objective_definition_hash TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    bin_id TEXT,
                    family TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    evaluation_count INTEGER NOT NULL DEFAULT 0,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    structural_elements_json TEXT NOT NULL,
                    correctness_association_id TEXT,
                    property_fields_json TEXT NOT NULL,
                    artifact_anchors_json TEXT NOT NULL,
                    diagnostic_message TEXT,
                    FOREIGN KEY (run_id) REFERENCES evidence_runs (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS result_imports (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    preview_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_reports (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    coverage_checkpoint_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    campaign_revision INTEGER NOT NULL,
                    evidence_sequence INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS generation_jobs (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    plugin_id TEXT NOT NULL,
                    plugin_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    diagnostics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS generated_artifacts (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    role TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    blob_digest TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS producer_manifests (
                    digest TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    checkpoint_id TEXT,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans (id) ON DELETE CASCADE
                );
            """)

    # --- Snapshots ---
    def save_snapshot(self, view: SourceSnapshotView, blob_hash: str, created_at: str) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_snapshots
                (snapshot_id, source_document_id, source_revision_hash, root_ref_json, view_json, blob_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    view.snapshot_id,
                    view.source_document_id,
                    view.source_revision_hash,
                    json.dumps(view.root_ref) if view.root_ref else None,
                    view.model_dump_json(),
                    blob_hash,
                    created_at,
                ),
            )

    def get_snapshot(self, snapshot_id: str) -> SourceSnapshotView | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT view_json FROM source_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            return SourceSnapshotView.model_validate_json(row["view_json"])

    # --- Plans ---
    def create_plan(self, header: PlanHeader) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO plans
                (id, name, description, snapshot_id, root_scope_id, owner_label, tags_json, edit_revision, schema_version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    header.id,
                    header.name,
                    header.description,
                    header.snapshot_id,
                    header.root_scope_id,
                    header.owner_label,
                    json.dumps(header.tags),
                    header.edit_revision,
                    header.schema_version,
                    header.created_at,
                    header.updated_at,
                ),
            )
            # Insert audit entries if any
            for sec_id, audit in header.source_audit.items():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO source_audits
                    (plan_id, section_id, disposition, reason, linked_requirement_ids_json, reviewer_label, source_digest, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        header.id,
                        sec_id,
                        audit.disposition.value,
                        audit.reason,
                        json.dumps(audit.linked_requirement_ids),
                        audit.reviewer_label,
                        audit.source_digest,
                        audit.updated_at,
                    ),
                )

    def get_plan(self, plan_id: str) -> PlanHeader | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not row:
                return None

            # Fetch source audits
            audit_rows = conn.execute(
                "SELECT * FROM source_audits WHERE plan_id = ?", (plan_id,)
            ).fetchall()
            source_audit: dict[str, SourceAuditEntry] = {}
            for a_row in audit_rows:
                source_audit[a_row["section_id"]] = SourceAuditEntry(
                    section_id=a_row["section_id"],
                    disposition=a_row["disposition"],
                    reason=a_row["reason"],
                    linked_requirement_ids=json.loads(a_row["linked_requirement_ids_json"]),
                    reviewer_label=a_row["reviewer_label"],
                    source_digest=a_row["source_digest"],
                    updated_at=a_row["updated_at"],
                )

            return PlanHeader(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                snapshot_id=row["snapshot_id"],
                root_scope_id=row["root_scope_id"],
                owner_label=row["owner_label"],
                tags=json.loads(row["tags_json"]),
                source_audit=source_audit,
                schema_version=row["schema_version"],
                edit_revision=row["edit_revision"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_plans(self) -> list[PlanHeader]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM plans ORDER BY updated_at DESC").fetchall()
            plans: list[PlanHeader] = []
            for row in rows:
                plans.append(
                    PlanHeader(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        snapshot_id=row["snapshot_id"],
                        root_scope_id=row["root_scope_id"],
                        owner_label=row["owner_label"],
                        tags=json.loads(row["tags_json"]),
                        source_audit={},
                        schema_version=row["schema_version"],
                        edit_revision=row["edit_revision"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
            return plans

    # --- Key Allocation ---
    def allocate_key(self, plan_id: str, prefix: str) -> str:
        """Atomically increment counter and allocate human-readable key (e.g. REQ-1)."""
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO key_counters (plan_id, prefix, last_number)
                VALUES (?, ?, 1)
                ON CONFLICT(plan_id, prefix) DO UPDATE SET last_number = last_number + 1
                """,
                (plan_id, prefix),
            )
            row = conn.execute(
                "SELECT last_number FROM key_counters WHERE plan_id = ? AND prefix = ?",
                (plan_id, prefix),
            ).fetchone()
            num = row["last_number"] if row else 1
            return f"{prefix}-{num}"

    # --- Records ---
    def get_records(
        self,
        plan_id: str,
        record_type: str | None = None,
        scope_id: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            query = "SELECT data_json, record_type FROM records WHERE plan_id = ?"
            params: list[Any] = [plan_id]
            if record_type:
                query += " AND record_type = ?"
                params.append(record_type)
            if scope_id:
                query += " AND scope_id = ?"
                params.append(scope_id)
            if not include_archived:
                query += " AND archived = 0"
            query += " ORDER BY created_at ASC"

            rows = conn.execute(query, params).fetchall()
            return [json.loads(r["data_json"]) for r in rows]

    def get_record(self, plan_id: str, record_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT data_json FROM records WHERE plan_id = ? AND id = ?",
                (plan_id, record_id),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["data_json"])

    # --- Command Idempotency and Transaction Execution ---
    def check_command_idempotency(
        self, plan_id: str, request_id: str, payload_hash: str
    ) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT payload_hash, response_json FROM command_log WHERE plan_id = ? AND request_id = ?",
                (plan_id, request_id),
            ).fetchone()
            if not row:
                return None
            if row["payload_hash"] != payload_hash:
                raise IdempotencyMismatchError(request_id)
            return json.loads(row["response_json"])

    def execute_command_transaction(
        self,
        plan_id: str,
        request_id: str,
        base_edit_revision: int,
        payload_hash: str,
        header_updates: dict[str, Any] | None,
        audit_updates: list[SourceAuditEntry],
        saved_records: list[dict[str, Any]],
        deleted_record_ids: list[str],
        response_data: dict[str, Any],
        event_data: dict[str, Any],
    ) -> int:
        """Atomically check revision, update records, update plan revision, log command, log event."""
        with self._lock, self._get_connection() as conn:
            # Check current plan revision
            row = conn.execute("SELECT edit_revision FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if not row:
                raise PlanNotFoundError(plan_id)
            current_rev = row["edit_revision"]
            if current_rev != base_edit_revision:
                raise RevisionConflictError(
                    plan_id=plan_id,
                    base_revision=base_edit_revision,
                    current_revision=current_rev,
                    request_id=request_id,
                )

            new_rev = current_rev + 1

            # 1. Update plan header
            if header_updates:
                sets = [f"{k} = ?" for k in header_updates.keys()]
                sets.append("edit_revision = ?")
                vals = list(header_updates.values()) + [new_rev, plan_id]
                conn.execute(f"UPDATE plans SET {', '.join(sets)} WHERE id = ?", vals)
            else:
                conn.execute(
                    "UPDATE plans SET edit_revision = ? WHERE id = ?",
                    (new_rev, plan_id),
                )

            # 2. Update source audits
            for audit in audit_updates:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO source_audits
                    (plan_id, section_id, disposition, reason, linked_requirement_ids_json, reviewer_label, source_digest, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        audit.section_id,
                        audit.disposition.value if hasattr(audit.disposition, "value") else audit.disposition,
                        audit.reason,
                        json.dumps(audit.linked_requirement_ids),
                        audit.reviewer_label,
                        audit.source_digest,
                        audit.updated_at,
                    ),
                )

            # 3. Save / Upsert records
            for rec in saved_records:
                r_id = rec["id"]
                r_type = rec["record_type"]
                r_key = rec.get("key", r_id)
                r_rev = rec.get("record_revision", 1)
                r_scope = rec.get("scope_id", "")
                r_parent = rec.get("parent_section_id")
                r_archived = 1 if rec.get("archived") else 0
                r_created = rec.get("created_at", "")
                r_updated = rec.get("updated_at", "")
                r_json = json.dumps(rec)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO records
                    (plan_id, id, record_type, key, record_revision, scope_id, parent_id, archived, data_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        r_id,
                        r_type,
                        r_key,
                        r_rev,
                        r_scope,
                        r_parent,
                        r_archived,
                        r_json,
                        r_created,
                        r_updated,
                    ),
                )

            # 4. Hard delete draft records if requested
            for d_id in deleted_record_ids:
                conn.execute(
                    "DELETE FROM records WHERE plan_id = ? AND id = ?",
                    (plan_id, d_id),
                )

            # 5. Log command
            conn.execute(
                """
                INSERT INTO command_log
                (plan_id, request_id, base_edit_revision, new_edit_revision, payload_hash, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    request_id,
                    base_edit_revision,
                    new_rev,
                    payload_hash,
                    json.dumps(response_data),
                    response_data.get("created_at", ""),
                ),
            )

            # 6. Log event
            conn.execute(
                """
                INSERT INTO events
                (event_id, plan_id, kind, edit_revision, evidence_sequence, changed_ids_json, origin_request_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_data["event_id"],
                    plan_id,
                    event_data["kind"],
                    new_rev,
                    event_data.get("evidence_sequence", 0),
                    json.dumps(event_data["changed_ids"]),
                    request_id,
                    event_data["created_at"],
                ),
            )

            return new_rev

    # --- Checkpoints ---
    def save_checkpoint(self, checkpoint: PlanCheckpoint) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints
                (id, plan_id, key, layer, upstream_checkpoint_id, snapshot_id, root_scope_id, content_hash, reviewer_label, comment, checklist_json, acknowledged_warnings_json, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.id,
                    checkpoint.plan_id,
                    checkpoint.key,
                    checkpoint.layer,
                    checkpoint.upstream_checkpoint_id,
                    checkpoint.snapshot_id,
                    checkpoint.root_scope_id,
                    checkpoint.content_hash,
                    checkpoint.reviewer_label,
                    checkpoint.comment,
                    json.dumps(checkpoint.checklist),
                    json.dumps(checkpoint.acknowledged_warnings),
                    json.dumps(checkpoint.payload),
                    checkpoint.created_at,
                ),
            )

    def get_checkpoint(self, plan_id: str, checkpoint_id: str) -> PlanCheckpoint | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE plan_id = ? AND (id = ? OR key = ?)",
                (plan_id, checkpoint_id, checkpoint_id),
            ).fetchone()
            if not row:
                return None
            return PlanCheckpoint(
                id=row["id"],
                key=row["key"],
                layer=row["layer"],
                plan_id=row["plan_id"],
                created_at=row["created_at"],
                reviewer_label=row["reviewer_label"],
                comment=row["comment"],
                upstream_checkpoint_id=row["upstream_checkpoint_id"],
                snapshot_id=row["snapshot_id"],
                root_scope_id=row["root_scope_id"],
                checklist=json.loads(row["checklist_json"]),
                acknowledged_warnings=json.loads(row["acknowledged_warnings_json"]),
                content_hash=row["content_hash"],
                payload=json.loads(row["payload_json"]),
            )

    def list_checkpoints(self, plan_id: str) -> list[PlanCheckpoint]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE plan_id = ? ORDER BY created_at ASC",
                (plan_id,),
            ).fetchall()
            return [
                PlanCheckpoint(
                    id=row["id"],
                    key=row["key"],
                    layer=row["layer"],
                    plan_id=row["plan_id"],
                    created_at=row["created_at"],
                    reviewer_label=row["reviewer_label"],
                    comment=row["comment"],
                    upstream_checkpoint_id=row["upstream_checkpoint_id"],
                    snapshot_id=row["snapshot_id"],
                    root_scope_id=row["root_scope_id"],
                    checklist=json.loads(row["checklist_json"]),
                    acknowledged_warnings=json.loads(row["acknowledged_warnings_json"]),
                    content_hash=row["content_hash"],
                    payload=json.loads(row["payload_json"]),
                )
                for row in rows
            ]

    # --- Events ---
    def get_events(self, plan_id: str, since_event_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            query = "SELECT * FROM events WHERE plan_id = ?"
            params: list[Any] = [plan_id]
            if since_event_id:
                query += " AND ROWID > (SELECT ROWID FROM events WHERE event_id = ?)"
                params.append(since_event_id)
            query += " ORDER BY ROWID ASC LIMIT 100"
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "event_id": r["event_id"],
                    "plan_id": r["plan_id"],
                    "kind": r["kind"],
                    "edit_revision": r["edit_revision"],
                    "evidence_sequence": r["evidence_sequence"],
                    "changed_ids": json.loads(r["changed_ids_json"]),
                    "origin_request_id": r["origin_request_id"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    # --- Layer 2: Profiles ---
    def save_profile(self, profile: EvaluationProfile) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles
                (id, plan_id, display_name, coverage_checkpoint_id, source_snapshot_id, source_snapshot_hash, dut_source_hash, root_occurrence_id, resolved_parameters_json, clock_reset_config_json, realization_descriptors_json, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.plan_id,
                    profile.display_name,
                    profile.coverage_checkpoint_id,
                    profile.source_snapshot_id,
                    profile.source_snapshot_hash,
                    profile.dut_source_hash,
                    profile.root_occurrence_id,
                    json.dumps(profile.resolved_parameters),
                    json.dumps(profile.clock_reset_config),
                    json.dumps([d.model_dump() for d in profile.realization_descriptors]),
                    profile.content_hash,
                    profile.created_at,
                ),
            )

    def get_profile(self, plan_id: str, profile_id: str) -> EvaluationProfile | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE plan_id = ? AND id = ?",
                (plan_id, profile_id),
            ).fetchone()
            if not row:
                return None
            descriptors = [RealizationDescriptor.model_validate(d) for d in json.loads(row["realization_descriptors_json"])]
            return EvaluationProfile(
                id=row["id"],
                plan_id=row["plan_id"],
                display_name=row["display_name"],
                coverage_checkpoint_id=row["coverage_checkpoint_id"],
                source_snapshot_id=row["source_snapshot_id"],
                source_snapshot_hash=row["source_snapshot_hash"],
                dut_source_hash=row["dut_source_hash"],
                root_occurrence_id=row["root_occurrence_id"],
                resolved_parameters=json.loads(row["resolved_parameters_json"]),
                clock_reset_config=json.loads(row["clock_reset_config_json"]),
                realization_descriptors=descriptors,
                content_hash=row["content_hash"],
                created_at=row["created_at"],
            )

    def list_profiles(self, plan_id: str) -> list[EvaluationProfile]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles WHERE plan_id = ? ORDER BY created_at ASC",
                (plan_id,),
            ).fetchall()
            return [
                EvaluationProfile(
                    id=r["id"],
                    plan_id=r["plan_id"],
                    display_name=r["display_name"],
                    coverage_checkpoint_id=r["coverage_checkpoint_id"],
                    source_snapshot_id=r["source_snapshot_id"],
                    source_snapshot_hash=r["source_snapshot_hash"],
                    dut_source_hash=r["dut_source_hash"],
                    root_occurrence_id=r["root_occurrence_id"],
                    resolved_parameters=json.loads(r["resolved_parameters_json"]),
                    clock_reset_config=json.loads(r["clock_reset_config_json"]),
                    realization_descriptors=[RealizationDescriptor.model_validate(d) for d in json.loads(r["realization_descriptors_json"])],
                    content_hash=r["content_hash"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # --- Layer 2: Campaigns ---
    def save_campaign(self, campaign: EvidenceCampaign) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO campaigns
                (id, plan_id, title, coverage_checkpoint_id, required_profile_ids_json, included_run_ids_json, run_dispositions_json, waivers_json, purpose, state, campaign_revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign.id,
                    campaign.plan_id,
                    campaign.title,
                    campaign.coverage_checkpoint_id,
                    json.dumps(campaign.required_profile_ids),
                    json.dumps(campaign.included_run_ids),
                    json.dumps({k: v.model_dump() for k, v in campaign.run_dispositions.items()}),
                    json.dumps([w.model_dump() for w in campaign.waivers]),
                    campaign.purpose.value if hasattr(campaign.purpose, "value") else campaign.purpose,
                    campaign.state.value if hasattr(campaign.state, "value") else campaign.state,
                    campaign.campaign_revision,
                    campaign.created_at,
                    campaign.updated_at,
                ),
            )

    def get_campaign(self, plan_id: str, campaign_id: str) -> EvidenceCampaign | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE plan_id = ? AND id = ?",
                (plan_id, campaign_id),
            ).fetchone()
            if not row:
                return None
            disps_raw = json.loads(row["run_dispositions_json"])
            run_dispositions = {k: RunDisposition.model_validate(v) for k, v in disps_raw.items()}
            waivers = [IntentWaiver.model_validate(w) for w in json.loads(row["waivers_json"])]
            return EvidenceCampaign(
                id=row["id"],
                plan_id=row["plan_id"],
                title=row["title"],
                coverage_checkpoint_id=row["coverage_checkpoint_id"],
                required_profile_ids=json.loads(row["required_profile_ids_json"]),
                included_run_ids=json.loads(row["included_run_ids_json"]),
                run_dispositions=run_dispositions,
                waivers=waivers,
                purpose=CampaignPurpose(row["purpose"]),
                state=CampaignState(row["state"]),
                campaign_revision=row["campaign_revision"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_campaigns(self, plan_id: str) -> list[EvidenceCampaign]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM campaigns WHERE plan_id = ? ORDER BY created_at ASC",
                (plan_id,),
            ).fetchall()
            campaigns: list[EvidenceCampaign] = []
            for r in rows:
                disps_raw = json.loads(r["run_dispositions_json"])
                run_dispositions = {k: RunDisposition.model_validate(v) for k, v in disps_raw.items()}
                waivers = [IntentWaiver.model_validate(w) for w in json.loads(r["waivers_json"])]
                campaigns.append(
                    EvidenceCampaign(
                        id=r["id"],
                        plan_id=r["plan_id"],
                        title=r["title"],
                        coverage_checkpoint_id=r["coverage_checkpoint_id"],
                        required_profile_ids=json.loads(r["required_profile_ids_json"]),
                        included_run_ids=json.loads(r["included_run_ids_json"]),
                        run_dispositions=run_dispositions,
                        waivers=waivers,
                        purpose=CampaignPurpose(r["purpose"]),
                        state=CampaignState(r["state"]),
                        campaign_revision=r["campaign_revision"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                    )
                )
            return campaigns

    def check_campaign_idempotency(self, campaign_id: str, request_id: str, payload_hash: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT payload_hash, response_json FROM campaign_commands WHERE campaign_id = ? AND request_id = ?",
                (campaign_id, request_id),
            ).fetchone()
            if not row:
                return None
            if row["payload_hash"] != payload_hash:
                raise IdempotencyMismatchError(request_id)
            return json.loads(row["response_json"])

    def execute_campaign_command(
        self,
        plan_id: str,
        campaign_id: str,
        request_id: str,
        base_campaign_revision: int,
        payload_hash: str,
        operations: list[dict[str, Any]],
        now_iso: str,
    ) -> dict[str, Any]:
        with self._lock, self._get_connection() as conn:
            campaign = self.get_campaign(plan_id, campaign_id)
            if not campaign:
                raise CampaignNotFoundError(campaign_id)

            if campaign.campaign_revision != base_campaign_revision:
                raise CampaignRevisionConflictError(
                    campaign_id=campaign_id,
                    base_revision=base_campaign_revision,
                    current_revision=campaign.campaign_revision,
                    request_id=request_id,
                )

            # Apply operations
            included_runs = list(campaign.included_run_ids)
            run_dispositions = dict(campaign.run_dispositions)
            waivers = list(campaign.waivers)
            campaign_state = campaign.state

            for op in operations:
                op_type = op.get("op")
                if campaign_state == CampaignState.FROZEN and op_type != "campaign.status":
                    raise CampaignFrozenError(campaign_id)

                if op_type == "run.include":
                    run_id = op["run_id"]
                    if run_id not in included_runs:
                        included_runs.append(run_id)
                elif op_type == "run.exclude":
                    run_id = op["run_id"]
                    if run_id in included_runs:
                        included_runs.remove(run_id)
                elif op_type == "run.resolve":
                    run_id = op["run_id"]
                    run_dispositions[run_id] = RunDisposition(
                        run_id=run_id,
                        disposition=RunDispositionKind(op["disposition"]),
                        reason=op["reason"],
                        reviewer_label=op.get("reviewer_label", "author"),
                        replacement_run_id=op.get("replacement_run_id"),
                        created_at=now_iso,
                    )
                elif op_type == "waiver.create":
                    waivers.append(
                        IntentWaiver(
                            id=op.get("id") or str(uuid.uuid4()),
                            intent_id=op["intent_id"],
                            profile_ids=op.get("profile_ids", []),
                            checkpoint_id=campaign.coverage_checkpoint_id,
                            reason=op["reason"],
                            owner_label=op.get("owner_label", "author"),
                            expires_at=op["expires_at"],
                            milestone_label=op.get("milestone_label"),
                            supporting_evidence_ids=op.get("supporting_evidence_ids", []),
                            created_at=now_iso,
                        )
                    )
                elif op_type == "waiver.revoke":
                    waiver_id = op["waiver_id"]
                    for w in waivers:
                        if w.id == waiver_id:
                            w.revoked = True
                elif op_type == "campaign.freeze":
                    campaign_state = CampaignState.FROZEN

            new_revision = campaign.campaign_revision + 1
            updated_campaign = campaign.model_copy(
                update={
                    "included_run_ids": included_runs,
                    "run_dispositions": run_dispositions,
                    "waivers": waivers,
                    "state": campaign_state,
                    "campaign_revision": new_revision,
                    "updated_at": now_iso,
                }
            )

            # Persist campaign updates
            conn.execute(
                """
                UPDATE campaigns SET
                    included_run_ids_json = ?,
                    run_dispositions_json = ?,
                    waivers_json = ?,
                    state = ?,
                    campaign_revision = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(updated_campaign.included_run_ids),
                    json.dumps({k: v.model_dump() for k, v in updated_campaign.run_dispositions.items()}),
                    json.dumps([w.model_dump() for w in updated_campaign.waivers]),
                    updated_campaign.state.value,
                    new_revision,
                    now_iso,
                    campaign_id,
                ),
            )

            response_data = {
                "campaign_id": campaign_id,
                "campaign_revision": new_revision,
                "state": updated_campaign.state.value,
                "included_run_ids_count": len(updated_campaign.included_run_ids),
                "request_id": request_id,
                "updated_at": now_iso,
            }

            conn.execute(
                """
                INSERT INTO campaign_commands
                (campaign_id, request_id, base_campaign_revision, new_campaign_revision, payload_hash, response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    request_id,
                    base_campaign_revision,
                    new_revision,
                    payload_hash,
                    json.dumps(response_data),
                    now_iso,
                ),
            )

            return response_data

    # --- Layer 2: Staged Result Imports ---
    def save_result_import(self, import_id: str, plan_id: str, status_str: str, preview_digest: str, payload_json: str, created_at: str) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO result_imports
                (id, plan_id, status, preview_digest, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (import_id, plan_id, status_str, preview_digest, payload_json, created_at),
            )

    def get_result_import(self, plan_id: str, import_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM result_imports WHERE plan_id = ? AND id = ?",
                (plan_id, import_id),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "plan_id": row["plan_id"],
                "status": row["status"],
                "preview_digest": row["preview_digest"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }

    # --- Layer 2: Evidence Runs and Observations ---
    def save_evidence_run(self, run: EvidenceRun, observations: list[EvidenceObservation]) -> bool:
        """Atomically persist run and its observations. Returns True if inserted, False if idempotent replay."""
        with self._lock, self._get_connection() as conn:
            existing = conn.execute(
                "SELECT id, payload_hash FROM evidence_runs WHERE producer_id = ? AND external_run_id = ? AND attempt_id = ?",
                (run.producer_id, run.external_run_id, run.attempt_id),
            ).fetchone()

            if existing:
                if existing["payload_hash"] == run.payload_hash:
                    # Idempotent replay: already committed with exact payload
                    return False
                raise IdempotencyMismatchError(f"{run.producer_id}:{run.external_run_id}:{run.attempt_id}")

            conn.execute(
                """
                INSERT INTO evidence_runs
                (id, plan_id, producer_id, external_run_id, attempt_id, profile_id, coverage_checkpoint_id, producer_manifest_digest, dut_source_hash, configuration_hash, tool_name, tool_version, seed, synthetic, producer_kind, trust_label, status, raw_artifact_digests_json, parser_adapter_id, validation_diagnostics_json, start_time, end_time, imported_at, payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.plan_id,
                    run.producer_id,
                    run.external_run_id,
                    run.attempt_id,
                    run.profile_id,
                    run.coverage_checkpoint_id,
                    run.producer_manifest_digest,
                    run.dut_source_hash,
                    run.configuration_hash,
                    run.tool_name,
                    run.tool_version,
                    run.seed,
                    1 if run.synthetic else 0,
                    run.producer_kind,
                    run.trust_label,
                    run.status.value if hasattr(run.status, "value") else run.status,
                    json.dumps(run.raw_artifact_digests),
                    run.parser_adapter_id,
                    json.dumps(run.validation_diagnostics),
                    run.start_time,
                    run.end_time,
                    run.imported_at,
                    run.payload_hash,
                ),
            )

            for obs in observations:
                conn.execute(
                    """
                    INSERT INTO evidence_observations
                    (id, run_id, producer_observation_id, objective_id, objective_definition_hash, scope_id, bin_id, family, outcome, evaluation_count, hit_count, structural_elements_json, correctness_association_id, property_fields_json, artifact_anchors_json, diagnostic_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        obs.id,
                        obs.run_id,
                        obs.producer_observation_id,
                        obs.objective_id,
                        obs.objective_definition_hash,
                        obs.scope_id,
                        obs.bin_id,
                        obs.family,
                        obs.outcome.value if hasattr(obs.outcome, "value") else obs.outcome,
                        obs.evaluation_count,
                        obs.hit_count,
                        json.dumps(obs.structural_elements),
                        obs.correctness_association_id,
                        json.dumps(obs.property_fields),
                        json.dumps(obs.artifact_anchors),
                        obs.diagnostic_message,
                    ),
                )

            return True

    def get_run(self, plan_id: str, run_id: str) -> EvidenceRun | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT * FROM evidence_runs WHERE plan_id = ? AND id = ?", (plan_id, run_id)).fetchone()
            if not row:
                return None
            return EvidenceRun(
                id=row["id"],
                plan_id=row["plan_id"],
                producer_id=row["producer_id"],
                external_run_id=row["external_run_id"],
                attempt_id=row["attempt_id"],
                profile_id=row["profile_id"],
                coverage_checkpoint_id=row["coverage_checkpoint_id"],
                producer_manifest_digest=row["producer_manifest_digest"],
                dut_source_hash=row["dut_source_hash"],
                configuration_hash=row["configuration_hash"],
                tool_name=row["tool_name"],
                tool_version=row["tool_version"],
                seed=row["seed"],
                synthetic=bool(row["synthetic"]),
                producer_kind=row["producer_kind"],
                trust_label=row["trust_label"],
                status=RunStatus(row["status"]),
                raw_artifact_digests=json.loads(row["raw_artifact_digests_json"]),
                parser_adapter_id=row["parser_adapter_id"],
                validation_diagnostics=json.loads(row["validation_diagnostics_json"]),
                start_time=row["start_time"],
                end_time=row["end_time"],
                imported_at=row["imported_at"],
                payload_hash=row["payload_hash"],
            )

    def list_runs(self, plan_id: str, profile_id: str | None = None) -> list[EvidenceRun]:
        with self._lock, self._get_connection() as conn:
            query = "SELECT * FROM evidence_runs WHERE plan_id = ?"
            params: list[Any] = [plan_id]
            if profile_id:
                query += " AND profile_id = ?"
                params.append(profile_id)
            query += " ORDER BY imported_at ASC"
            rows = conn.execute(query, params).fetchall()
            return [
                EvidenceRun(
                    id=r["id"],
                    plan_id=r["plan_id"],
                    producer_id=r["producer_id"],
                    external_run_id=r["external_run_id"],
                    attempt_id=r["attempt_id"],
                    profile_id=r["profile_id"],
                    coverage_checkpoint_id=r["coverage_checkpoint_id"],
                    producer_manifest_digest=r["producer_manifest_digest"],
                    dut_source_hash=r["dut_source_hash"],
                    configuration_hash=r["configuration_hash"],
                    tool_name=r["tool_name"],
                    tool_version=r["tool_version"],
                    seed=r["seed"],
                    synthetic=bool(r["synthetic"]),
                    producer_kind=r["producer_kind"],
                    trust_label=r["trust_label"],
                    status=RunStatus(r["status"]),
                    raw_artifact_digests=json.loads(r["raw_artifact_digests_json"]),
                    parser_adapter_id=r["parser_adapter_id"],
                    validation_diagnostics=json.loads(r["validation_diagnostics_json"]),
                    start_time=r["start_time"],
                    end_time=r["end_time"],
                    imported_at=r["imported_at"],
                    payload_hash=r["payload_hash"],
                )
                for r in rows
            ]

    def get_observations_for_run(self, run_id: str) -> list[EvidenceObservation]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM evidence_observations WHERE run_id = ?", (run_id,)).fetchall()
            return [
                EvidenceObservation(
                    id=r["id"],
                    run_id=r["run_id"],
                    producer_observation_id=r["producer_observation_id"],
                    objective_id=r["objective_id"],
                    objective_definition_hash=r["objective_definition_hash"],
                    scope_id=r["scope_id"],
                    bin_id=r["bin_id"],
                    family=r["family"],
                    outcome=ObservationOutcome(r["outcome"]),
                    evaluation_count=r["evaluation_count"],
                    hit_count=r["hit_count"],
                    structural_elements=json.loads(r["structural_elements_json"]),
                    correctness_association_id=r["correctness_association_id"],
                    property_fields=json.loads(r["property_fields_json"]),
                    artifact_anchors=json.loads(r["artifact_anchors_json"]),
                    diagnostic_message=r["diagnostic_message"],
                )
                for r in rows
            ]

    def get_observations_for_runs(self, run_ids: list[str]) -> dict[str, list[EvidenceObservation]]:
        if not run_ids:
            return {}
        with self._lock, self._get_connection() as conn:
            placeholders = ",".join("?" for _ in run_ids)
            rows = conn.execute(
                f"SELECT * FROM evidence_observations WHERE run_id IN ({placeholders})",
                run_ids,
            ).fetchall()
            res: dict[str, list[EvidenceObservation]] = {rid: [] for rid in run_ids}
            for r in rows:
                obs = EvidenceObservation(
                    id=r["id"],
                    run_id=r["run_id"],
                    producer_observation_id=r["producer_observation_id"],
                    objective_id=r["objective_id"],
                    objective_definition_hash=r["objective_definition_hash"],
                    scope_id=r["scope_id"],
                    bin_id=r["bin_id"],
                    family=r["family"],
                    outcome=ObservationOutcome(r["outcome"]),
                    evaluation_count=r["evaluation_count"],
                    hit_count=r["hit_count"],
                    structural_elements=json.loads(r["structural_elements_json"]),
                    correctness_association_id=r["correctness_association_id"],
                    property_fields=json.loads(r["property_fields_json"]),
                    artifact_anchors=json.loads(r["artifact_anchors_json"]),
                    diagnostic_message=r["diagnostic_message"],
                )
                res[r["run_id"]].append(obs)
            return res

    # --- Layer 2: Evidence Reports ---
    def save_evidence_report(self, report: EvidenceReport) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_reports
                (id, plan_id, coverage_checkpoint_id, campaign_id, campaign_revision, evidence_sequence, status, report_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.plan_id,
                    report.coverage_checkpoint_id,
                    report.campaign_id,
                    report.campaign_revision,
                    report.evidence_sequence,
                    report.status,
                    json.dumps(report.report_data),
                    report.created_at,
                ),
            )

    def get_evidence_report(self, plan_id: str, report_id: str) -> EvidenceReport | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute("SELECT * FROM evidence_reports WHERE plan_id = ? AND id = ?", (plan_id, report_id)).fetchone()
            if not row:
                return None
            return EvidenceReport(
                id=row["id"],
                plan_id=row["plan_id"],
                coverage_checkpoint_id=row["coverage_checkpoint_id"],
                campaign_id=row["campaign_id"],
                campaign_revision=row["campaign_revision"],
                evidence_sequence=row["evidence_sequence"],
                status=row["status"],
                report_data=json.loads(row["report_json"]),
                created_at=row["created_at"],
            )

    # --- Layer 3: Generation Jobs & Artifacts ---
    def save_generation_job(self, job: dict[str, Any]) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO generation_jobs
                (id, plan_id, checkpoint_id, plugin_id, plugin_version, status, request_json, result_json, diagnostics_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["id"],
                    job["plan_id"],
                    job["checkpoint_id"],
                    job["plugin_id"],
                    job["plugin_version"],
                    job["status"],
                    json.dumps(job["request_data"]),
                    json.dumps(job.get("result_data")) if job.get("result_data") else None,
                    json.dumps(job.get("diagnostics", [])),
                    job["created_at"],
                    job["updated_at"],
                ),
            )

    def get_generation_job(self, plan_id: str, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM generation_jobs WHERE plan_id = ? AND id = ?",
                (plan_id, job_id),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "plan_id": row["plan_id"],
                "checkpoint_id": row["checkpoint_id"],
                "plugin_id": row["plugin_id"],
                "plugin_version": row["plugin_version"],
                "status": row["status"],
                "request_data": json.loads(row["request_json"]),
                "result_data": json.loads(row["result_json"]) if row["result_json"] else None,
                "diagnostics": json.loads(row["diagnostics_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def list_generation_jobs(self, plan_id: str) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE plan_id = ? ORDER BY created_at DESC",
                (plan_id,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "plan_id": r["plan_id"],
                    "checkpoint_id": r["checkpoint_id"],
                    "plugin_id": r["plugin_id"],
                    "plugin_version": r["plugin_version"],
                    "status": r["status"],
                    "request_data": json.loads(r["request_json"]),
                    "result_data": json.loads(r["result_json"]) if r["result_json"] else None,
                    "diagnostics": json.loads(r["diagnostics_json"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    def update_generation_job_status(
        self,
        job_id: str,
        status: str,
        result_data: dict[str, Any] | None,
        diagnostics: list[dict[str, Any]],
        updated_at: str,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE generation_jobs
                SET status = ?, result_json = ?, diagnostics_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result_data) if result_data else None,
                    json.dumps(diagnostics),
                    updated_at,
                    job_id,
                ),
            )

    def save_generated_artifact(self, artifact: dict[str, Any]) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO generated_artifacts
                (id, job_id, plan_id, relative_path, role, media_type, sha256, blob_digest, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact["id"],
                    artifact["job_id"],
                    artifact["plan_id"],
                    artifact["relative_path"],
                    artifact["role"],
                    artifact.get("media_type", "text/plain"),
                    artifact["sha256"],
                    artifact["blob_digest"],
                    artifact.get("size_bytes", 0),
                    artifact["created_at"],
                ),
            )

    def get_generated_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM generated_artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "job_id": row["job_id"],
                "plan_id": row["plan_id"],
                "relative_path": row["relative_path"],
                "role": row["role"],
                "media_type": row["media_type"],
                "sha256": row["sha256"],
                "blob_digest": row["blob_digest"],
                "size_bytes": row["size_bytes"],
                "created_at": row["created_at"],
            }

    def list_generated_artifacts_for_job(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM generated_artifacts WHERE job_id = ? ORDER BY relative_path ASC",
                (job_id,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "job_id": r["job_id"],
                    "plan_id": r["plan_id"],
                    "relative_path": r["relative_path"],
                    "role": r["role"],
                    "media_type": r["media_type"],
                    "sha256": r["sha256"],
                    "blob_digest": r["blob_digest"],
                    "size_bytes": r["size_bytes"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def save_producer_manifest(self, manifest: ProducerManifest, plan_id: str) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO producer_manifests
                (digest, plan_id, checkpoint_id, data_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    manifest.manifest_digest,
                    plan_id,
                    manifest.implementation_checkpoint_id,
                    json.dumps(manifest.model_dump()),
                    manifest.created_at,
                ),
            )

    def get_producer_manifest(self, digest: str) -> ProducerManifest | None:
        with self._lock, self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM producer_manifests WHERE digest = ?",
                (digest,),
            ).fetchone()
            if not row:
                return None
            return ProducerManifest.model_validate(json.loads(row["data_json"]))

    # --- Layer 3: Typed Record Accessors ---
    def get_recipes(self, plan_id: str, include_archived: bool = False) -> list[Recipe]:
        records = self.get_records(plan_id, include_archived=include_archived)
        return [
            Recipe.model_validate(r)
            for r in records
            if r.get("record_type") == "recipe"
        ]

    def get_recipe(self, plan_id: str, recipe_id: str) -> Recipe | None:
        rec = self.get_record(plan_id, recipe_id)
        if rec and rec.get("record_type") == "recipe":
            return Recipe.model_validate(rec)
        return None

    def get_binding_sets(self, plan_id: str, include_archived: bool = False) -> list[TargetBindingSet]:
        records = self.get_records(plan_id, include_archived=include_archived)
        return [
            TargetBindingSet.model_validate(r)
            for r in records
            if r.get("record_type") == "target_binding_set"
        ]

    def get_binding_set(self, plan_id: str, binding_set_id: str) -> TargetBindingSet | None:
        rec = self.get_record(plan_id, binding_set_id)
        if rec and rec.get("record_type") == "target_binding_set":
            return TargetBindingSet.model_validate(rec)
        return None

    def get_backend_configurations(self, plan_id: str) -> list[BackendConfiguration]:
        records = self.get_records(plan_id, include_archived=False)
        return [
            BackendConfiguration.model_validate(r)
            for r in records
            if r.get("record_type") == "backend_configuration"
        ]

    def get_backend_configuration(self, plan_id: str, config_id: str) -> BackendConfiguration | None:
        rec = self.get_record(plan_id, config_id)
        if rec and rec.get("record_type") == "backend_configuration":
            return BackendConfiguration.model_validate(rec)
        return None

