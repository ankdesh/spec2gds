"""Test and verification runner for component releases."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec_library.checker import LibraryChecker, is_temp_directory
from spec2gds.spec_library.components.phase1 import PHASE1_COMPONENTS_BY_ID
from spec2gds.spec_library.schemas import InventoryV1
from spec2gds.spec_library.verification import verify_component


class LibraryVerifier:
    """Verifies library components across presets and generates evidence."""

    def __init__(
        self,
        phase: int,
        library_root: Path = Path("spec_library"),
        candidates: Path | None = None,
        output: Path = Path("temp/TEMP_verify"),
    ) -> None:
        self.phase = phase
        self.library_root = library_root
        self.candidates = candidates
        self.output = output

    def verify(self) -> tuple[int, dict[str, Any]]:
        """Execute verification across all target phase components."""
        if not is_temp_directory(self.output):
            print(f"Error: Output directory {self.output} must be inside an ignored temp/TEMP_* directory.")
            return 2, {"error": "Output directory not in temp/TEMP_*"}

        # 1. Run prerequisite checks
        checker = LibraryChecker(
            phase=self.phase,
            library_root=self.library_root,
            candidates=self.candidates,
            output=self.output / "prereq_check",
        )
        check_code, check_report = checker.check()
        if check_code != 0:
            print("Prerequisite checks failed prior to verification.")
            return check_code, check_report

        # 2. Load active inventory
        inv_path = (self.candidates / "inventory.json") if self.candidates else (self.library_root / "inventory.json")
        inv = InventoryV1.model_validate_json(inv_path.read_text(encoding="utf-8"))

        target_entries = [e for e in inv.entries if e.phase == self.phase]
        base_dir = self.candidates if self.candidates else self.library_root

        results: dict[str, Any] = {}
        all_passed = True

        for entry in target_entries:
            comp_def = PHASE1_COMPONENTS_BY_ID.get(entry.id)
            if not comp_def:
                print(f"Error: Component definition for {entry.id} not found in runner.")
                all_passed = False
                results[entry.id] = {"status": "fail", "summary": "Missing definition"}
                continue

            spec_path = base_dir / entry.path
            print(f"Verifying {entry.id} (version {entry.version}) from {spec_path}...")
            ev, _, ok = verify_component(comp_def, spec_path, self.output)
            results[entry.id] = {
                "status": "pass" if ok else "fail",
                "checks": [c.model_dump() for c in ev.checks],
            }
            if not ok:
                all_passed = False
                print(f"  FAILED: {entry.id}")
            else:
                print(f"  PASSED: {entry.id} ({len(ev.checks)} checks)")

        overall = "pass" if all_passed else "fail"
        report = {
            "phase": self.phase,
            "mode": "candidate" if self.candidates else "canonical",
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "overall_status": overall,
            "components": results,
        }

        report_file = self.output / "report.json"
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

        exit_code = 0 if all_passed else 1
        return exit_code, report
