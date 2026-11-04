"""SQLite catalogue indexer and reconciler for library packages."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec_catalog_service.catalog.schemas import (
    SUPPORTED_CATEGORIES,
    CatalogueAssetV1,
    EvidenceRecordV1,
    InventoryV1,
    compute_identity_key,
    compute_sha256,
    get_package_asset,
)


class LibraryIndexer:
    """Builds and updates SQLite catalogue index from canonical filesystem packages."""

    def __init__(
        self,
        library_root: Path = Path("spec_catalog_service/catalog"),
        state_dir: Path = Path("spec_catalog_service/.state"),
    ) -> None:
        self.library_root = library_root
        self.state_dir = state_dir
        self.db_path = self.state_dir / "catalogue.db"

    def initialize_db(self, conn: sqlite3.Connection) -> None:
        """Create database tables if they do not exist."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS components (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                latest_version TEXT NOT NULL,
                summary TEXT NOT NULL,
                tags TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                contract_anchor TEXT,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS releases (
                id TEXT NOT NULL,
                version TEXT NOT NULL,
                category TEXT NOT NULL,
                path TEXT NOT NULL,
                package_sha256 TEXT NOT NULL,
                source_revision_hash TEXT NOT NULL,
                catalogue_asset TEXT NOT NULL,
                evidence_sha256 TEXT,
                evidence_json TEXT,
                usage_markdown TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (id, version)
            );

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

            CREATE INDEX IF NOT EXISTS idx_components_category ON components(category);
            CREATE INDEX IF NOT EXISTS idx_releases_pkg_sha ON releases(package_sha256);
            """
        )
        conn.commit()

    def rebuild(self) -> dict[str, Any]:
        """Rebuild the SQLite index entirely from canonical files."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temp_db = self.state_dir / "catalogue.db.tmp"
        if temp_db.exists():
            temp_db.unlink()

        conn = sqlite3.connect(temp_db)
        self.initialize_db(conn)

        stats = {
            "components_indexed": 0,
            "releases_indexed": 0,
            "errors": [],
        }

        # 1. Read inventory to get base metadata and planned components
        inv_path = self.library_root / "inventory.json"
        inv_map: dict[str, Any] = {}
        if inv_path.is_file():
            try:
                inv = InventoryV1.model_validate_json(inv_path.read_text(encoding="utf-8"))
                inv_map = {e.id: e for e in inv.entries}
            except Exception as e:
                stats["errors"].append(f"Failed to read inventory {inv_path}: {e}")

        # 2. Discover all canonical category/id/version directories
        discovered_releases: dict[str, list[dict[str, Any]]] = {}

        for category_dir in self.library_root.iterdir():
            if not category_dir.is_dir() or category_dir.name not in SUPPORTED_CATEGORIES:
                continue

            for comp_dir in category_dir.iterdir():
                if not comp_dir.is_dir() or comp_dir.name.startswith((".", "TEMP_")):
                    continue
                comp_id = comp_dir.name

                for ver_dir in comp_dir.iterdir():
                    if not ver_dir.is_dir() or ver_dir.name.startswith((".", "TEMP_")):
                        continue
                    version = ver_dir.name

                    spec_file = ver_dir / f"{comp_id}.spec"
                    if not spec_file.is_file():
                        continue

                    # Read package and metadata
                    try:
                        spec_bytes = spec_file.read_bytes()
                        pkg = SpecPackage.from_bytes(spec_bytes)
                        cat_asset_bytes = get_package_asset(pkg, "library_catalogue_v1")
                        if not cat_asset_bytes:
                            stats["errors"].append(f"Missing catalogue asset in {spec_file}")
                            continue

                        cat_asset = CatalogueAssetV1.model_validate_json(cat_asset_bytes.decode("utf-8"))
                        spec_sha = compute_sha256(spec_bytes)
                        rev = SpecRevision.from_package(pkg)

                        # Check for usage.md
                        usage_file = ver_dir / "usage.md"
                        usage_md = usage_file.read_text(encoding="utf-8") if usage_file.is_file() else ""

                        # Check for evidence.json
                        ev_file = ver_dir / "evidence.json"
                        ev_sha = None
                        ev_json_str = None
                        if ev_file.is_file():
                            ev_bytes = ev_file.read_bytes()
                            ev_sha = compute_sha256(ev_bytes)
                            ev_json_str = ev_bytes.decode("utf-8")

                        rel_data = {
                            "id": comp_id,
                            "version": version,
                            "category": category_dir.name,
                            "path": str(spec_file.relative_to(self.library_root)),
                            "package_sha256": spec_sha,
                            "source_revision_hash": rev.source_revision_hash,
                            "catalogue_asset": cat_asset.model_dump(mode="json"),
                            "evidence_sha256": ev_sha,
                            "evidence_json": ev_json_str,
                            "usage_markdown": usage_md,
                            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }

                        discovered_releases.setdefault(comp_id, []).append(rel_data)
                    except Exception as e:
                        stats["errors"].append(f"Error indexing {spec_file}: {e}")

        # 3. Insert discovered releases and components
        now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Insert delivered components
        for comp_id, releases in discovered_releases.items():
            releases.sort(key=lambda r: [int(x) for x in r["version"].split(".")])
            latest = releases[-1]
            cat_asset_dict = latest["catalogue_asset"]

            comp_title = comp_id.replace("_", " ").title()
            identity_key = compute_identity_key("spec2gds.local", cat_asset_dict["category"], comp_id)

            conn.execute(
                """
                INSERT INTO components (
                    id, name, category, latest_version, summary, tags, identity_key, contract_anchor, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comp_id,
                    comp_title,
                    cat_asset_dict["category"],
                    latest["version"],
                    cat_asset_dict["summary"],
                    json.dumps(cat_asset_dict["tags"]),
                    identity_key,
                    cat_asset_dict.get("contracts"),
                    "delivered",
                    now_str,
                ),
            )
            stats["components_indexed"] += 1

            for rel in releases:
                conn.execute(
                    """
                    INSERT INTO releases (
                        id, version, category, path, package_sha256, source_revision_hash, catalogue_asset,
                        evidence_sha256, evidence_json, usage_markdown, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rel["id"],
                        rel["version"],
                        rel["category"],
                        rel["path"],
                        rel["package_sha256"],
                        rel["source_revision_hash"],
                        json.dumps(rel["catalogue_asset"]),
                        rel["evidence_sha256"],
                        rel["evidence_json"],
                        rel["usage_markdown"],
                        rel["created_at"],
                    ),
                )
                stats["releases_indexed"] += 1

        # Also insert any planned inventory entries not yet delivered
        for comp_id, inv_entry in inv_map.items():
            if comp_id not in discovered_releases:
                conn.execute(
                    """
                    INSERT INTO components (
                        id, name, category, latest_version, summary, tags, identity_key, contract_anchor, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        comp_id,
                        comp_id.replace("_", " ").title(),
                        inv_entry.category,
                        inv_entry.version,
                        f"Planned {inv_entry.category} component",
                        "[]",
                        f"spec2gds:library:{comp_id}:{inv_entry.version}",
                        inv_entry.contract,
                        "planned",
                        now_str,
                    ),
                )
                stats["components_indexed"] += 1

        # Evidence files are durable; the SQLite index can be reconstructed.
        for evidence_file in sorted(self.library_root.glob("*/*/*/evidence/*.json")):
            try:
                raw = evidence_file.read_bytes()
                evidence = EvidenceRecordV1.model_validate_json(raw)
                category, comp_id, version = evidence_file.relative_to(self.library_root).parts[:3]
                release = conn.execute("SELECT package_sha256 FROM releases WHERE id=? AND version=?", (comp_id, version)).fetchone()
                if not release or release[0] != evidence.package_sha256:
                    raise ValueError("Evidence does not match a published release")
                received = datetime.fromtimestamp(evidence_file.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("INSERT OR IGNORE INTO evidence_submissions VALUES (?, ?, ?, ?, ?)",
                             (comp_id, version, compute_sha256(raw), received, raw.decode()))
            except (ValueError, OSError) as exc:
                stats["errors"].append(f"Invalid evidence {evidence_file}: {exc}")
        generation = 0
        if self.db_path.exists():
            previous = sqlite3.connect(self.db_path)
            try:
                row = previous.execute("SELECT value FROM service_state WHERE key='index_generation'").fetchone()
                generation = int(row[0]) if row else 0
            finally:
                previous.close()
        conn.execute("INSERT OR REPLACE INTO service_state VALUES ('index_generation', ?)", (str(generation + 1),))
        conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '1')")
        conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('rebuilt_at', ?)", (now_str,))
        conn.commit()
        conn.close()

        # Atomic rename temp_db -> db_path
        if stats["errors"]:
            temp_db.unlink()
            return stats
        temp_db.replace(self.db_path)
        return stats
