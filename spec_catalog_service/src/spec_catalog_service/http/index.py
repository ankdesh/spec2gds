"""SQLite catalogue index management and query engine for the library service."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec_catalog_service.catalog.indexer import LibraryIndexer
from spec_catalog_service.catalog.schemas import (
    CatalogueAssetV1,
    compute_identity_key,
)


class CatalogueIndex:
    """Manages SQLite index queries, generation tracking, and metadata updates."""

    def __init__(self, db_path: Path, library_root: Path) -> None:
        self.db_path = db_path
        self.library_root = library_root
        self._ensure_initialized()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        """Ensure database tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        indexer = LibraryIndexer(library_root=self.library_root, state_dir=self.db_path.parent)
        indexer.initialize_db(conn)

        # Ensure evidence_records table exists
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS evidence_submissions (
                id TEXT NOT NULL,
                version TEXT NOT NULL,
                evidence_sha256 TEXT NOT NULL,
                received_at TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                PRIMARY KEY (id, version, evidence_sha256)
            );

            CREATE TABLE IF NOT EXISTS service_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        # Ensure generation exists
        cur = conn.execute("SELECT value FROM service_state WHERE key = 'index_generation'")
        if cur.fetchone() is None:
            conn.execute("INSERT INTO service_state (key, value) VALUES ('index_generation', '0')")
        conn.commit()
        conn.close()

    def get_generation(self) -> int:
        """Retrieve current index generation number."""
        try:
            conn = self._get_connection()
            cur = conn.execute("SELECT value FROM service_state WHERE key = 'index_generation'")
            row = cur.fetchone()
            conn.close()
            return int(row["value"]) if row else 0
        except Exception:
            return 0

    def increment_generation(self, conn: sqlite3.Connection) -> int:
        """Increment generation counter within an existing transaction."""
        cur = conn.execute("SELECT value FROM service_state WHERE key = 'index_generation'")
        row = cur.fetchone()
        gen = int(row["value"]) + 1 if row else 1
        conn.execute("INSERT OR REPLACE INTO service_state (key, value) VALUES ('index_generation', ?)", (str(gen),))
        return gen

    def compute_functional_status(
        self, cat_asset: dict[str, Any], evidence_list: list[dict[str, Any]]
    ) -> tuple[str, int]:
        """Compute functional status (unreported, reported_pass, reported_fail, reported_incomplete)."""
        if not evidence_list:
            return "unreported", 0

        any_failure = False
        all_checks: list[dict[str, Any]] = []

        for ev in evidence_list:
            raw_str = ev.get("raw_json") or ev.get("evidence_json")
            if not raw_str:
                continue
            try:
                ev_obj = json.loads(raw_str)
                checks = ev_obj.get("checks", [])
                all_checks.extend(checks)
                for c in checks:
                    if c.get("status") == "fail":
                        any_failure = True
            except Exception:
                pass

        if any_failure:
            return "reported_fail", len(evidence_list)

        # Check required checks: package, implementation, determinism
        kinds_present = {c.get("kind") for c in all_checks if c.get("preset") is None and c.get("status") == "pass"}
        if not {"package", "implementation", "determinism"}.issubset(kinds_present):
            return "reported_incomplete", len(evidence_list)

        # Check preset checks
        declared_presets = cat_asset.get("presets", {})
        for preset_name in declared_presets:
            p_kinds = {
                c.get("kind")
                for c in all_checks
                if c.get("preset") == preset_name and c.get("status") == "pass"
            }
            if not {"lint", "simulation", "parameter_validation"}.issubset(p_kinds):
                return "reported_incomplete", len(evidence_list)

        return "reported_pass", len(evidence_list)

    def _build_version_row(self, rel_row: sqlite3.Row, conn: sqlite3.Connection) -> dict[str, Any]:
        cat_asset = json.loads(rel_row["catalogue_asset"])
        comp_id = rel_row["id"]
        version = rel_row["version"]
        category = rel_row["category"]

        # Fetch evidence submissions for this version
        ev_cur = conn.execute(
            "SELECT evidence_sha256, received_at, raw_json FROM evidence_submissions WHERE id = ? AND version = ?",
            (comp_id, version),
        )
        ev_rows = [dict(r) for r in ev_cur.fetchall()]
        if rel_row["evidence_json"] and not ev_rows:
            ev_rows.append(
                {
                    "evidence_sha256": rel_row["evidence_sha256"],
                    "received_at": rel_row["created_at"],
                    "raw_json": rel_row["evidence_json"],
                }
            )

        f_status, ev_count = self.compute_functional_status(cat_asset, ev_rows)

        # Check implementation in archive/metadata
        has_impl = cat_asset.get("implementation") in ("body_sv", "composite")
        key = compute_identity_key("spec2gds.local", category, comp_id)
        vlnv = f"spec2gds.local:{category}:{comp_id}:{version}"

        spec_file = self.library_root / rel_row["path"]
        pkg_size = spec_file.stat().st_size if spec_file.exists() else 0

        return {
            "key": key,
            "vlnv": vlnv,
            "id": comp_id,
            "category": category,
            "version": version,
            "summary": cat_asset.get("summary", ""),
            "tags": cat_asset.get("tags", []),
            "implementation": "present" if has_impl else "absent",
            "implementation_kind": cat_asset.get("implementation"),
            "source_revision_hash": rel_row["source_revision_hash"],
            "package_sha256": rel_row["package_sha256"],
            "package_size_bytes": pkg_size,
            "validation": {
                "package": "valid",
                "implementation": "present" if has_impl else "absent",
                "diagnostics": [],
            },
            "functional_status": f_status,
            "evidence_count": ev_count,
            "download_url": f"/api/spec-catalog/v1/components/{key}/versions/{version}/download",
        }

    def list_components(
        self,
        q: str | None = None,
        category: str | None = None,
        implementation: str | None = None,
        functional_status: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        """List highest version row for matching components."""
        conn = self._get_connection()

        # Query all delivered components
        cur = conn.execute("SELECT id FROM components WHERE status = 'delivered' ORDER BY category ASC, id ASC")
        comp_ids = [r["id"] for r in cur.fetchall()]

        items: list[dict[str, Any]] = []

        for cid in comp_ids:
            # Get highest version release
            rel_cur = conn.execute(
                "SELECT * FROM releases WHERE id = ? ORDER BY version DESC",
                (cid,),
            )
            releases = rel_cur.fetchall()
            if not releases:
                continue

            # Sort descending by semver
            releases = sorted(
                releases,
                key=lambda r: [int(x) for x in r["version"].split(".")],
                reverse=True,
            )
            highest_rel = releases[0]
            vrow = self._build_version_row(highest_rel, conn)

            # Apply filters
            if category and vrow["category"] != category:
                continue
            if implementation and implementation not in {vrow["implementation"], vrow["implementation_kind"]}:
                continue
            if functional_status and vrow["functional_status"] != functional_status:
                continue
            if q:
                q_lower = q.lower()
                id_match = q_lower in vrow["id"].lower()
                sum_match = q_lower in vrow["summary"].lower()
                tag_match = any(q_lower in t.lower() for t in vrow["tags"])
                if not (id_match or sum_match or tag_match):
                    continue

            items.append(vrow)

        conn.close()

        total = len(items)
        paginated_items = items[offset : offset + limit]
        return total, paginated_items

    def get_component_by_key(self, key: str) -> dict[str, Any] | None:
        """Get component identity and list of all immutable versions."""
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM components WHERE identity_key = ?", (key,))
        comp = cur.fetchone()
        if not comp:
            # Also check if key matches compute_identity_key("spec2gds", "library", id)
            cur = conn.execute("SELECT * FROM components")
            for c in cur.fetchall():
                if compute_identity_key("spec2gds", "library", c["id"]) == key:
                    comp = c
                    break

        if not comp:
            conn.close()
            return None

        comp_id = comp["id"]
        rel_cur = conn.execute("SELECT * FROM releases WHERE id = ?", (comp_id,))
        releases = rel_cur.fetchall()
        releases = sorted(
            releases,
            key=lambda r: [int(x) for x in r["version"].split(".")],
            reverse=True,
        )

        version_rows = [self._build_version_row(r, conn) for r in releases]
        conn.close()

        return {
            "key": key,
            "vendor": "spec2gds.local",
            "library": comp["category"],
            "id": comp_id,
            "category": comp["category"],
            "versions": version_rows,
        }

    def get_version_details(self, key: str, version: str) -> dict[str, Any] | None:
        """Get details for a specific component version including parsed metadata."""
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM components WHERE identity_key = ?", (key,))
        comp = cur.fetchone()
        if not comp:
            cur = conn.execute("SELECT * FROM components")
            for c in cur.fetchall():
                if compute_identity_key("spec2gds", "library", c["id"]) == key:
                    comp = c
                    break

        if not comp:
            conn.close()
            return None

        rel_cur = conn.execute(
            "SELECT * FROM releases WHERE id = ? AND version = ?", (comp["id"], version)
        )
        rel_row = rel_cur.fetchone()
        if not rel_row:
            conn.close()
            return None

        vrow = self._build_version_row(rel_row, conn)
        vrow["metadata"] = json.loads(rel_row["catalogue_asset"])
        vrow["usage_markdown"] = rel_row["usage_markdown"]
        conn.close()
        return vrow

    def record_published_package(
        self,
        cat_asset: CatalogueAssetV1,
        rel_path: str,
        pkg_sha: str,
        source_rev_hash: str,
    ) -> None:
        """Insert or update published package in index."""
        conn = self._get_connection()
        now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        comp_title = cat_asset.id.replace("_", " ").title()
        identity_key = compute_identity_key("spec2gds.local", cat_asset.category, cat_asset.id)

        conn.execute(
            """
            INSERT INTO components (
                id, name, category, latest_version, summary, tags, identity_key, contract_anchor, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'delivered', ?)
            ON CONFLICT(id) DO UPDATE SET
                latest_version = excluded.latest_version,
                updated_at = excluded.updated_at,
                status = 'delivered'
            """,
            (
                cat_asset.id,
                comp_title,
                cat_asset.category,
                cat_asset.version,
                cat_asset.summary,
                json.dumps(cat_asset.tags),
                identity_key,
                cat_asset.contracts,
                now_str,
            ),
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO releases (
                id, version, category, path, package_sha256, source_revision_hash, catalogue_asset,
                evidence_sha256, evidence_json, usage_markdown, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, '', ?)
            """,
            (
                cat_asset.id,
                cat_asset.version,
                cat_asset.category,
                rel_path,
                pkg_sha,
                source_rev_hash,
                json.dumps(cat_asset.model_dump(mode="json")),
                now_str,
            ),
        )

        self.increment_generation(conn)
        conn.commit()
        conn.close()

    def record_evidence_submission(
        self,
        comp_id: str,
        version: str,
        ev_sha: str,
        ev_bytes: bytes,
        received_at: str,
    ) -> None:
        """Record newly submitted evidence."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_submissions (
                id, version, evidence_sha256, received_at, raw_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (comp_id, version, ev_sha, received_at, ev_bytes.decode("utf-8")),
        )
        self.increment_generation(conn)
        conn.commit()
        conn.close()

    def list_evidence_submissions(self, key: str, version: str) -> list[dict[str, Any]] | None:
        """List evidence submissions for a component version."""
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM components WHERE identity_key = ?", (key,))
        comp = cur.fetchone()
        if not comp:
            cur = conn.execute("SELECT * FROM components")
            for c in cur.fetchall():
                if compute_identity_key("spec2gds", "library", c["id"]) == key:
                    comp = c
                    break

        if not comp:
            conn.close()
            return None

        comp_id = comp["id"]
        # Check version exists in releases
        rel_cur = conn.execute("SELECT * FROM releases WHERE id = ? AND version = ?", (comp_id, version))
        rel_row = rel_cur.fetchone()
        if not rel_row:
            conn.close()
            return None

        ev_cur = conn.execute(
            "SELECT evidence_sha256, received_at, raw_json FROM evidence_submissions WHERE id = ? AND version = ?",
            (comp_id, version),
        )
        submissions = [dict(r) for r in ev_cur.fetchall()]

        # Include canonical evidence if present
        if rel_row["evidence_json"] and not any(s["evidence_sha256"] == rel_row["evidence_sha256"] for s in submissions):
            submissions.append(
                {
                    "evidence_sha256": rel_row["evidence_sha256"],
                    "received_at": rel_row["created_at"],
                    "raw_json": rel_row["evidence_json"],
                }
            )

        conn.close()

        # Sort by receipt time then digest
        submissions.sort(key=lambda s: (s["received_at"], s["evidence_sha256"]))

        items = []
        for s in submissions:
            report_obj = json.loads(s["raw_json"]) if s.get("raw_json") else {}
            items.append(
                {
                    "evidence_sha256": s["evidence_sha256"],
                    "received_at": s["received_at"],
                    "report": report_obj,
                }
            )
        return items
