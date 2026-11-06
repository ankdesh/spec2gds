"""Read-only verification of inventory, DAG, packages, and evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec_catalog_service.catalog.schemas import (
    CatalogueAssetV1,
    EvidenceRecordV1,
    InventoryEntry,
    InventoryV1,
    compute_sha256,
    get_package_asset,
)


def is_temp_directory(path: Path) -> bool:
    """Check if the path is located inside an ignored temp/TEMP_* directory."""
    resolved = path.resolve()
    for part in resolved.parts:
        if part == "temp" or part.startswith("TEMP_"):
            return True
    return False


class LibraryChecker:
    """Performs read-only validation of library inventories, packages, and evidence."""

    def __init__(
        self,
        phase: int,
        library_root: Path = Path("spec_catalog_service/catalog"),
        candidates: Path | None = None,
        output: Path = Path("temp/TEMP_check"),
    ) -> None:
        self.phase = phase
        self.library_root = library_root
        self.candidates = candidates
        self.output = output

    def check(self) -> tuple[int, dict[str, Any]]:
        """Run all check stages and write report.json. Returns (exit_code, report_dict)."""
        if not is_temp_directory(self.output):
            print(f"Error: Output directory {self.output} must be inside an ignored temp/TEMP_* directory.")
            return 2, {"error": "Output directory not in temp/TEMP_*"}

        self.output.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {
            "phase": self.phase,
            "mode": "candidate" if self.candidates else "canonical",
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entries_checked": 0,
            "errors": [],
            "warnings": [],
            "overall_status": "fail",
        }

        # 1. Load canonical inventory
        can_inv_path = self.library_root / "inventory.json"
        if not can_inv_path.is_file():
            report["errors"].append(f"Canonical inventory missing: {can_inv_path}")
            self._write_report(report)
            return 2, report

        try:
            can_inv = InventoryV1.model_validate_json(can_inv_path.read_text(encoding="utf-8"))
        except Exception as e:
            report["errors"].append(f"Malformed canonical inventory {can_inv_path}: {e}")
            self._write_report(report)
            return 1, report

        # 2. If candidates provided, validate candidate inventory
        active_inv = can_inv
        if self.candidates:
            cand_inv_path = self.candidates / "inventory.json"
            if not cand_inv_path.is_file():
                report["errors"].append(f"Candidate inventory missing: {cand_inv_path}")
                self._write_report(report)
                return 2, report

            try:
                active_inv = InventoryV1.model_validate_json(cand_inv_path.read_text(encoding="utf-8"))
            except Exception as e:
                report["errors"].append(f"Malformed candidate inventory {cand_inv_path}: {e}")
                self._write_report(report)
                return 1, report

            # Check that only selected phase pins differ from canonical
            can_map = {e.id: e for e in can_inv.entries}
            for cand_entry in active_inv.entries:
                if cand_entry.id not in can_map:
                    report["errors"].append(f"Candidate inventory has unknown ID {cand_entry.id}")
                    continue
                can_entry = can_map[cand_entry.id]
                if cand_entry.phase != self.phase:
                    if cand_entry.version != can_entry.version or cand_entry.path != can_entry.path:
                        report["errors"].append(
                            f"Candidate inventory modified entry {cand_entry.id} outside selected phase {self.phase}"
                        )

        # 3. Check DAG dependencies
        id_to_entry = {e.id: e for e in active_inv.entries}
        for entry in active_inv.entries:
            if entry.phase > self.phase:
                continue
            for dep_id in entry.dependencies:
                if dep_id not in id_to_entry:
                    report["errors"].append(f"Component {entry.id} has missing dependency {dep_id}")
                else:
                    dep_entry = id_to_entry[dep_id]
                    if dep_entry.phase > entry.phase:
                        report["errors"].append(
                            f"Dependency cycle/phase inversion: {entry.id} (phase {entry.phase}) depends on {dep_id} (phase {dep_entry.phase})"
                        )

        # 4. Check each entry up to the selected phase
        target_entries = [e for e in active_inv.entries if e.phase <= self.phase]
        report["entries_target"] = len(target_entries)
        report["entries_checked"] = 0
        report["planned_entries_skipped"] = 0

        for entry in target_entries:
            self._check_entry(entry, report)

        report["overall_status"] = "pass" if not report["errors"] else "fail"
        self._write_report(report)

        exit_code = 0 if report["overall_status"] == "pass" else 1
        return exit_code, report

    def _check_entry(self, entry: InventoryEntry, report: dict[str, Any]) -> None:
        """Validate one inventory entry's package, usage, and evidence."""
        is_candidate_entry = self.candidates is not None and entry.phase == self.phase
        base_dir = self.candidates if is_candidate_entry else self.library_root
        assert base_dir is not None

        spec_file = base_dir / entry.path
        if not spec_file.is_file():
            if entry.status == "planned":
                report["planned_entries_skipped"] += 1
                return
            report["errors"].append(f"Spec package missing for {entry.id}: {spec_file}")
            return

        report["entries_checked"] += 1
        usage_file = spec_file.parent / "usage.md"
        if not usage_file.is_file():
            report["errors"].append(f"usage.md missing for {entry.id}: {usage_file}")

        # Check package validity
        try:
            spec_bytes = spec_file.read_bytes()
            pkg = SpecPackage.from_bytes(spec_bytes)
            rev = SpecRevision.from_package(pkg)
        except Exception as e:
            report["errors"].append(f"Failed to load package for {entry.id} ({spec_file}): {e}")
            return

        expected_vlnv = f"spec2gds.local:{entry.category}:{entry.id}:{entry.version}"
        root_comp = next((c for c in rev.components if c.vlnv == expected_vlnv), None)
        if root_comp is None:
            report["errors"].append(
                f"Root component with VLNV {expected_vlnv} missing in package for {entry.id}"
            )
            return

        has_internal = rev.internal_design(root_comp.ref) is not None
        if not has_internal and len(rev.components) != 1:
            report["errors"].append(f"Expected 1 component in package for {entry.id}, found {len(rev.components)}")
            return

        # Required implementation check (either direct SV section or internal design composition)
        sections = rev.entity_sections_for(root_comp.ref)
        has_sv = any(s.section_type == "sv" and s.content.strip() for s in sections)
        if not (has_sv or has_internal):
            report["errors"].append(f"Required SystemVerilog implementation or internal design missing for {entry.id}")

        # Catalogue asset check
        cat_asset_bytes = get_package_asset(pkg, "library_catalogue_v1")
        if not cat_asset_bytes:
            report["errors"].append(f"library_catalogue_v1 asset missing in {entry.id}")
        else:
            try:
                cat_asset = CatalogueAssetV1.model_validate_json(cat_asset_bytes.decode("utf-8"))
                if cat_asset.id != entry.id or cat_asset.version != entry.version:
                    report["errors"].append(
                        f"Catalogue asset metadata mismatch in {entry.id}: id={cat_asset.id}, version={cat_asset.version}"
                    )
            except Exception as e:
                report["errors"].append(f"Malformed catalogue asset in {entry.id}: {e}")

        # Evidence validation
        evidence_file = spec_file.parent / "evidence.json"
        if not is_candidate_entry:
            # Canonical check requires evidence and delivered status
            if entry.status != "delivered":
                report["errors"].append(f"Canonical entry {entry.id} status must be 'delivered', got '{entry.status}'")
            if not evidence_file.is_file():
                report["errors"].append(f"evidence.json missing for canonical entry {entry.id}: {evidence_file}")
                return

        if evidence_file.is_file():
            try:
                ev_data = EvidenceRecordV1.model_validate_json(evidence_file.read_text(encoding="utf-8"))
                spec_sha = compute_sha256(spec_bytes)
                if ev_data.package_sha256 != spec_sha:
                    report["errors"].append(
                        f"Evidence package_sha256 mismatch for {entry.id}: evidence={ev_data.package_sha256}, spec={spec_sha}"
                    )
                if ev_data.source_revision_hash != rev.source_revision_hash:
                    report["errors"].append(
                        f"Evidence revision mismatch for {entry.id}: evidence={ev_data.source_revision_hash}, spec={rev.source_revision_hash}"
                    )
                for c in ev_data.checks:
                    if c.status == "fail":
                        report["errors"].append(f"Failing check in evidence for {entry.id}: {c.kind} ({c.preset})")
            except Exception as e:
                report["errors"].append(f"Malformed evidence for {entry.id}: {e}")

    def _write_report(self, report: dict[str, Any]) -> None:
        report_file = self.output / "report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
