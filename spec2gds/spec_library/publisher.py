"""Publication runner for promoting candidate releases to canonical library."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec_library.checker import is_temp_directory
from spec2gds.spec_library.schemas import (
    EvidenceRecordV1,
    InventoryV1,
    ReleaseRecord,
    compute_sha256,
)


class LibraryPublisher:
    """Atomically validates and copies candidates into canonical library paths and updates inventory."""

    def __init__(
        self,
        phase: int,
        candidates: Path,
        evidence: Path,
        output: Path,
        library_root: Path = Path("spec_library"),
    ) -> None:
        self.phase = phase
        self.candidates = candidates
        self.evidence = evidence
        self.output = output
        self.library_root = library_root

    def publish(self) -> tuple[int, dict[str, Any]]:
        """Validate candidate releases and evidence, then publish to canonical library."""
        if not is_temp_directory(self.output):
            print(f"Error: Output directory {self.output} must be inside an ignored TEMP_* directory.")
            return 2, {"error": "Output directory not in TEMP_*"}

        self.output.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {
            "phase": self.phase,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "published": [],
            "errors": [],
            "overall_status": "fail",
        }

        # 1. Load inventories
        cand_inv_file = self.candidates / "inventory.json"
        if not cand_inv_file.is_file():
            report["errors"].append(f"Candidate inventory missing at {cand_inv_file}")
            self._write_report(report)
            return 2, report

        can_inv_file = self.library_root / "inventory.json"
        if not can_inv_file.is_file():
            report["errors"].append(f"Canonical inventory missing at {can_inv_file}")
            self._write_report(report)
            return 2, report

        try:
            cand_inv = InventoryV1.model_validate_json(cand_inv_file.read_text(encoding="utf-8"))
            can_inv = InventoryV1.model_validate_json(can_inv_file.read_text(encoding="utf-8"))
        except Exception as e:
            report["errors"].append(f"Inventory validation error: {e}")
            self._write_report(report)
            return 1, report

        target_entries = [e for e in cand_inv.entries if e.phase == self.phase]
        if not target_entries:
            report["errors"].append(f"No entries found for phase {self.phase}")
            self._write_report(report)
            return 2, report

        # 2. Stage and validate all files BEFORE touching canonical directory
        staged_items: list[dict[str, Any]] = []
        for entry in target_entries:
            spec_file = self.candidates / entry.path
            if not spec_file.is_file():
                report["errors"].append(f"Candidate spec file missing: {spec_file}")
                continue

            usage_file = spec_file.parent / "usage.md"
            if not usage_file.is_file():
                report["errors"].append(f"Candidate usage.md missing: {usage_file}")
                continue

            ev_file = self.evidence / "components" / entry.id / entry.version / "evidence.json"
            if not ev_file.is_file():
                report["errors"].append(f"Evidence file missing: {ev_file}")
                continue

            spec_bytes = spec_file.read_bytes()
            spec_sha = compute_sha256(spec_bytes)

            ev_bytes = ev_file.read_bytes()
            try:
                ev_data = EvidenceRecordV1.model_validate_json(ev_bytes.decode("utf-8"))
                if ev_data.package_sha256 != spec_sha:
                    report["errors"].append(
                        f"Evidence digest mismatch for {entry.id}: evidence={ev_data.package_sha256}, spec={spec_sha}"
                    )
                for c in ev_data.checks:
                    if c.status == "fail":
                        report["errors"].append(f"Failing check in evidence for {entry.id}: {c.kind} ({c.preset})")
            except Exception as e:
                report["errors"].append(f"Malformed evidence for {entry.id}: {e}")
                continue

            ev_sha = compute_sha256(ev_bytes)
            staged_items.append(
                {
                    "entry": entry,
                    "spec_file": spec_file,
                    "spec_bytes": spec_bytes,
                    "spec_sha": spec_sha,
                    "usage_file": usage_file,
                    "ev_file": ev_file,
                    "ev_bytes": ev_bytes,
                    "ev_sha": ev_sha,
                }
            )

        if report["errors"]:
            print(f"Validation failed with {len(report['errors'])} errors; aborting publish.")
            self._write_report(report)
            return 1, report

        # 3. All valid: copy files to canonical tree and update inventory
        can_map = {e.id: e for e in can_inv.entries}
        for item in staged_items:
            entry = item["entry"]
            dest_dir = self.library_root / entry.category / entry.id / entry.version
            dest_dir.mkdir(parents=True, exist_ok=True)

            shutil.copy2(item["spec_file"], dest_dir / f"{entry.id}.spec")
            shutil.copy2(item["usage_file"], dest_dir / "usage.md")
            shutil.copy2(item["ev_file"], dest_dir / "evidence.json")

            # Update canonical entry
            can_entry = can_map[entry.id]
            existing_releases = list(can_entry.releases)
            existing_vers = {r.version for r in existing_releases}
            if entry.version not in existing_vers:
                existing_releases.append(
                    ReleaseRecord(
                        version=entry.version,
                        path=entry.path,
                        package_sha256=item["spec_sha"],
                        evidence_path=f"{entry.category}/{entry.id}/{entry.version}/evidence.json",
                        evidence_sha256=item["ev_sha"],
                    )
                )

            new_can_entry = can_entry.model_copy(
                update={
                    "status": "delivered",
                    "version": entry.version,
                    "path": entry.path,
                    "releases": existing_releases,
                }
            )
            can_map[entry.id] = new_can_entry

            report["published"].append(entry.id)
            print(f"Published {entry.id} {entry.version} -> {dest_dir}")

        # Save canonical inventory atomically
        new_entries = [can_map[e.id] for e in can_inv.entries]
        new_inv = can_inv.model_copy(update={"entries": new_entries})
        temp_inv_file = self.output / "inventory.json.tmp"
        temp_inv_file.write_text(json.dumps(new_inv.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
        shutil.move(temp_inv_file, can_inv_file)

        report["overall_status"] = "pass"
        self._write_report(report)
        return 0, report

    def _write_report(self, report: dict[str, Any]) -> None:
        report_file = self.output / "report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
