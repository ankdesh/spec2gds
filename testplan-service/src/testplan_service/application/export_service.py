"""Export and import service for .vplan bundles, Markdown reports, and CSV.

Reviewer path: export current records and their snapshot/checkpoint provenance
without rewriting historical IDs. Bundle staging and commit are separate review
steps; external archive content must never become executable plugin configuration.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from typing import Any

from testplan_service.constants import SCHEMA_VERSION_BUNDLE
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.models import PlanHeader
from testplan_service.exceptions import BundleError, PlanNotFoundError
from testplan_service.storage.blob_store import BlobStore
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class ExportService:
    """Handles portable .vplan bundles, Markdown documentation, and CSV summaries."""

    def __init__(self, repo: SqlitePlanRepository, blob_store: BlobStore) -> None:
        self.repo = repo
        self.blob_store = blob_store

    def export_vplan_bundle(self, plan_id: str) -> bytes:
        """Create a deterministic, verifiable .vplan ZIP bundle."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        records = self.repo.get_records(plan_id, include_archived=True)
        checkpoints = self.repo.list_checkpoints(plan_id)
        snapshot = self.repo.get_snapshot(plan.snapshot_id)

        # Snapshot raw bytes from blob store if present
        snapshot_bytes = b""
        if snapshot and self.blob_store.has_blob(plan.snapshot_id):
            snapshot_bytes = self.blob_store.get_bytes(plan.snapshot_id)

        plan_content = {
            "header": plan.model_dump(),
            "records": records,
            "source_audit": {k: v.model_dump() for k, v in plan.source_audit.items()},
        }
        plan_json_bytes = canonical_json(plan_content)

        checkpoints_data = [cp.model_dump() for cp in checkpoints]
        checkpoints_json_bytes = canonical_json(checkpoints_data)

        # Build file manifest
        file_digests: dict[str, str] = {
            "plan.json": sha256_digest(plan_json_bytes),
            "checkpoints/checkpoints.json": sha256_digest(checkpoints_json_bytes),
        }
        if snapshot_bytes:
            file_digests["sources/source.snapshot"] = sha256_digest(snapshot_bytes)

        manifest = {
            "schema_version": SCHEMA_VERSION_BUNDLE,
            "plan_id": plan_id,
            "export_revision": plan.edit_revision,
            "file_digests": file_digests,
            "includes_evidence": False,
            "notes": "Evidence not included. Layer 1 Test Plan portable bundle.",
        }
        manifest_bytes = canonical_json(manifest)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", manifest_bytes)
            zf.writestr("plan.json", plan_json_bytes)
            zf.writestr("checkpoints/checkpoints.json", checkpoints_json_bytes)
            if snapshot_bytes:
                zf.writestr("sources/source.snapshot", snapshot_bytes)

        return buf.getvalue()

    def import_vplan_bundle(self, bundle_bytes: bytes, resolution: str = "create") -> str:
        """Validate and commit a portable .vplan bundle, optionally importing as a new copy."""
        try:
            with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as zf:
                if "manifest.json" not in zf.namelist():
                    raise BundleError("Missing 'manifest.json' in .vplan bundle.")

                manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                if manifest_data.get("schema_version") != SCHEMA_VERSION_BUNDLE:
                    raise BundleError(f"Unsupported bundle schema: {manifest_data.get('schema_version')}")

                file_digests = manifest_data.get("file_digests", {})
                for path, expected_hash in file_digests.items():
                    if path not in zf.namelist():
                        raise BundleError(f"Bundle file '{path}' missing from archive.")
                    actual_hash = sha256_digest(zf.read(path))
                    if actual_hash != expected_hash:
                        raise BundleError(f"Integrity check failed for '{path}': hash mismatch.")

                plan_data = json.loads(zf.read("plan.json").decode("utf-8"))
                checkpoints_data = json.loads(zf.read("checkpoints/checkpoints.json").decode("utf-8"))

                # Read snapshot bytes if present
                if "sources/source.snapshot" in zf.namelist():
                    s_bytes = zf.read("sources/source.snapshot")
                    s_hash = self.blob_store.put_bytes(s_bytes)
                    # Decode and save snapshot in repository
                    from testplan_service.integrations.snapshot_decoder import decode_snapshot_bytes
                    s_view = decode_snapshot_bytes(s_bytes)
                    self.repo.save_snapshot(s_view, s_hash, plan_data["header"].get("created_at", ""))

        except zipfile.BadZipFile as exc:
            raise BundleError(f"Invalid ZIP archive: {exc}") from exc

        original_plan_id = manifest_data["plan_id"]
        target_plan_id = original_plan_id

        existing = self.repo.get_plan(original_plan_id)
        if existing:
            if resolution == "import_as_copy":
                target_plan_id = str(uuid.uuid4())
            else:
                raise BundleError(f"Plan '{original_plan_id}' already exists. Use resolution='import_as_copy'.")

        # Create target plan header
        hdr = plan_data["header"]
        new_header = PlanHeader(
            id=target_plan_id,
            name=hdr["name"] if target_plan_id == original_plan_id else f"{hdr['name']} (Imported Copy)",
            description=hdr.get("description", ""),
            snapshot_id=hdr["snapshot_id"],
            root_scope_id=hdr["root_scope_id"],
            designer_label=hdr.get("designer_label", hdr.get("owner_label")),
            tags=hdr.get("tags", []),
            source_audit={},
            schema_version=hdr.get("schema_version", "verification.plan.v1"),
            edit_revision=hdr.get("edit_revision", 1),
            created_at=hdr.get("created_at", ""),
            updated_at=hdr.get("updated_at", ""),
        )
        self.repo.create_plan(new_header)

        # Restore records
        records = plan_data.get("records", [])
        for rec in records:
            r_copy = dict(rec)
            r_id = r_copy["id"]
            r_type = r_copy["record_type"]
            r_key = r_copy.get("key", r_id)
            r_scope = r_copy.get("scope_id", "")
            r_parent = r_copy.get("parent_section_id")
            r_archived = 1 if r_copy.get("archived") else 0
            with self.repo._lock, self.repo._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO records
                    (plan_id, id, record_type, key, record_revision, scope_id, parent_id, archived, data_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_plan_id,
                        r_id,
                        r_type,
                        r_key,
                        r_copy.get("record_revision", 1),
                        r_scope,
                        r_parent,
                        r_archived,
                        json.dumps(r_copy),
                        r_copy.get("created_at", ""),
                        r_copy.get("updated_at", ""),
                    ),
                )

        return target_plan_id

    def _scope_name(self, plan: Any, scope_id: str | None) -> str:
        snapshot = self.repo.get_snapshot(plan.snapshot_id)
        if snapshot:
            for occurrence in snapshot.occurrences:
                if occurrence.occurrence_id == scope_id:
                    return occurrence.path or occurrence.name
        return "Unavailable scope" if scope_id else "None"

    def export_markdown(self, plan_id: str) -> str:
        """Render a readable human Markdown document of the Test Plan."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        records = self.repo.get_records(plan_id, include_archived=False)
        checkpoints = self.repo.list_checkpoints(plan_id)

        reqs = {r["id"]: r for r in records if r.get("record_type") == "requirement"}
        secs = {r["id"]: r for r in records if r.get("record_type") == "section"}
        intents = {r["id"]: r for r in records if r.get("record_type") == "intent"}

        lines: list[str] = [
            f"# Verification Plan: {plan.name}",
            f"\n- **Plan**: {plan.name}",
            f"- **Edit Revision**: `{plan.edit_revision}`",
            f"- **Source**: {self.repo.get_snapshot(plan.snapshot_id).source_name if self.repo.get_snapshot(plan.snapshot_id) else 'Unavailable source'}",
            f"- **Root Scope**: `{self._scope_name(plan, plan.root_scope_id)}`",
            f"- **Checkpoints**: {', '.join(cp.key for cp in checkpoints) if checkpoints else 'None'}",
            f"\n## Description\n\n{plan.description or 'No description provided.'}",
            "\n---\n",
            "## Requirements\n",
        ]

        if not reqs:
            lines.append("*No requirements captured yet.*")
        else:
            for req in reqs.values():
                lines.append(f"### [{req.get('key')}] {req.get('title')}")
                lines.append(f"**Statement**: {req.get('statement')}")
                lines.append(f"- Scope: `{self._scope_name(plan, req.get('scope_id'))}` | Disposition: `{req.get('disposition')}`")
                lines.append("")

        lines.extend(["\n---\n", "## Verification Intents\n"])
        if not intents:
            lines.append("*No intents authored yet.*")
        else:
            for intent in intents.values():
                parent_sec_title = secs[intent["parent_section_id"]]["title"] if intent.get("parent_section_id") in secs else "Root"
                lines.append(f"### [{intent.get('key')}] {intent.get('title')}")
                lines.append(f"- **Scope**: `{self._scope_name(plan, intent.get('scope_id'))}` | **Section**: {parent_sec_title}")
                lines.append(f"- **Priority**: `{intent.get('priority_override') or 'inherited'}` | **State**: `{intent.get('authoring_state')}`")
                lines.append(f"- **Given**: {intent.get('preconditions') or 'None'}")
                lines.append(f"- **When**: {intent.get('trigger') or 'None'}")
                lines.append(f"- **Then**: {intent.get('expected_behavior') or 'None'}")
                if intent.get("observations"):
                    lines.append("- **Observations**:")
                    for obs in intent["observations"]:
                        lines.append(f"  - *{obs.get('name')}*: {obs.get('description')}")
                lines.append("")

        lines.extend(["\n<details><summary>Technical details</summary>\n", f"Plan ID: `{plan.id}`; snapshot: `{plan.snapshot_id}`; root scope: `{plan.root_scope_id}`", "\n</details>"])
        return "\n".join(lines)

    def export_csv(self, plan_id: str) -> str:
        """Export CSV table preventing spreadsheet formula injection by quoting and prefix escaping."""
        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise PlanNotFoundError(plan_id)

        records = self.repo.get_records(plan_id, include_archived=False)
        intents = [r for r in records if r.get("record_type") == "intent"]
        secs = {r["id"]: r for r in records if r.get("record_type") == "section"}

        def sanitize(val: Any) -> str:
            s = str(val or "")
            if s.startswith(("=", "+", "-", "@")):
                return "'" + s
            return s

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "Intent Key",
            "Title",
            "Scope",
            "Section",
            "Priority",
            "Authoring State",
            "Given",
            "When",
            "Then",
            "Linked Requirements",
        ])

        for item in intents:
            p_sec = secs.get(item.get("parent_section_id", ""), {}).get("title", "")
            writer.writerow([
                sanitize(item.get("key")),
                sanitize(item.get("title")),
                sanitize(self._scope_name(plan, item.get("scope_id"))),
                sanitize(p_sec),
                sanitize(item.get("priority_override") or "inherited"),
                sanitize(item.get("authoring_state")),
                sanitize(item.get("preconditions")),
                sanitize(item.get("trigger")),
                sanitize(item.get("expected_behavior")),
                sanitize(", ".join(item.get("requirement_ids", []))),
            ])

        return output.getvalue()
