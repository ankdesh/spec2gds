#!/usr/bin/env python3
"""UI Review and Find-and-Fix Loop Runner.

Coordinates discovery, isolated reproduction, behavior verification,
and ledger tracking for Spec Editor and Circuit Designer under UI Stage 1.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Hoist repository paths and constants
ROOT: Final[Path] = Path(__file__).resolve().parents[1]
LEDGER_PATH: Final[Path] = ROOT / "docs" / "ui-review-ledger.md"
SUMMARY_PATH: Final[Path] = ROOT / "TEMP-UI-test-progress" / "substage-a-summary.md"
VALID_PRIORITIES: Final[tuple[str, ...]] = ("P0", "P1", "P2")
VALID_STATUSES: Final[tuple[str, ...]] = ("Open", "In Progress", "Fixed", "Deferred")

# Test command mappings for registered items
TEST_RUNNERS: Final[dict[str, list[str]]] = {
    "UI-BASELINE-001": ["uv", "run", "--no-sync", "python", "-m", "pytest", "-q", "tests/test_test_profiles.py"],
    "UI-BASELINE-002": ["npm", "--prefix", "circuit-designer", "test"],
    "UI-SPEC-001": [
        "npm", "--prefix", "circuit-designer", "run", "test:e2e:editor", "--",
        "-g", "creates, opens, refreshes, and exposes truthful File menu state",
    ],
    "UI-SPEC-012": [
        "npx", "--prefix", "circuit-designer/packages/document-a2ui-react",
        "vitest", "run", "tests/document-summary.test.ts",
    ],
    "UI-CIRCUIT-007": [
        "npx", "--prefix", "circuit-designer/packages/core",
        "vitest", "run", "tests/export.test.ts",
    ],
    "UI-SHARED-004": [
        "npm", "--prefix", "circuit-designer", "run", "test:e2e:editor", "--",
        "-g", "Preferences dialog with persistence",
    ],
    "UI-SPEC-019": [
        "npm", "--prefix", "circuit-designer", "run", "test:e2e:editor", "--",
        "-g", "refreshes artifacts after completion",
    ],
    "UI-CIRCUIT-015": [
        "npm", "--prefix", "circuit-designer", "run", "test:e2e", "--",
        "-g", "exports the visible canvas layout consistently to SVG and PNG",
    ],
    "UI-SHARED-003": [
        "npm", "--prefix", "circuit-designer", "run", "test:e2e", "--",
        "-g", "toggles visual theme via quick toggle and preferences page",
    ],
}


@dataclass(frozen=True)
class LedgerEntry:
    """Structured representation of a single UI Review Ledger entry."""

    ref_id: str
    area: str
    app: str
    priority: str
    status: str
    test_reference: str
    decision: str


class UiReviewLoop:
    """Manages the UI review loop, ledger validation, and targeted test execution."""

    def __init__(self, ledger_file: Path = LEDGER_PATH) -> None:
        """Initialize the loop runner with a target ledger file."""
        self._ledger_file = ledger_file

    def parse_ledger(self) -> list[LedgerEntry]:
        """Parse all review entries from the markdown ledger."""
        if not self._ledger_file.exists():
            raise FileNotFoundError(f"Review ledger not found: {self._ledger_file}")

        content = self._ledger_file.read_text(encoding="utf-8")
        sections = re.split(r"\n###\s+`?([A-Z0-9_-]+)`?", content)
        if len(sections) < 2:
            return []

        entries: list[LedgerEntry] = []
        for index in range(1, len(sections), 2):
            ref_id = sections[index].strip("`")
            body = sections[index + 1]

            area = self._extract_field(body, "Area")
            app = self._extract_field(body, "App")
            priority = self._extract_field(body, "Priority")
            status = self._extract_field(body, "Status")
            test_ref = self._extract_field(body, "Test Reference")
            decision = self._extract_field(body, "Decision")

            entries.append(
                LedgerEntry(
                    ref_id=ref_id,
                    area=area,
                    app=app,
                    priority=priority,
                    status=status,
                    test_reference=test_ref,
                    decision=decision,
                )
            )
        return entries

    def validate_ledger(self) -> bool:
        """Verify that every entry in the ledger has valid required fields."""
        entries = self.parse_ledger()
        if not entries:
            print(f"[FAIL] No entries found in ledger: {self._ledger_file}", file=sys.stderr)
            return False

        has_errors = False
        print(f"[INFO] Validating {len(entries)} review ledger entries in {self._ledger_file}...")
        for entry in entries:
            errors: list[str] = []
            if not entry.area:
                errors.append("Missing 'Area'")
            if not entry.app:
                errors.append("Missing 'App'")
            if entry.priority not in VALID_PRIORITIES:
                errors.append(f"Invalid 'Priority' '{entry.priority}' (expected {VALID_PRIORITIES})")
            if entry.status not in VALID_STATUSES:
                errors.append(f"Invalid 'Status' '{entry.status}' (expected {VALID_STATUSES})")
            if not entry.test_reference:
                errors.append("Missing 'Test Reference'")

            if errors:
                has_errors = True
                print(f"  [ERROR] {entry.ref_id}: {'; '.join(errors)}", file=sys.stderr)
            else:
                print(f"  [OK] {entry.ref_id:18} | {entry.priority:2} | {entry.status:10} | {entry.area}")

        return not has_errors

    def verify_entry(self, ref_id: str) -> bool:
        """Execute the regression check associated with a specific ledger entry."""
        if ref_id not in TEST_RUNNERS:
            print(f"[ERROR] No dedicated test command registered for {ref_id}", file=sys.stderr)
            return False

        cmd = TEST_RUNNERS[ref_id]
        print(f"[RUN] Verifying {ref_id}: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(ROOT), check=False)
        if result.returncode == 0:
            print(f"[PASS] {ref_id} verification succeeded.")
            return True
        else:
            print(f"[FAIL] {ref_id} verification failed with exit code {result.returncode}", file=sys.stderr)
            return False

    def print_summary(self) -> None:
        """Display an aggregate progress table of ledger findings."""
        entries = self.parse_ledger()
        counts: dict[str, dict[str, int]] = {p: {s: 0 for s in VALID_STATUSES} for p in VALID_PRIORITIES}
        for entry in entries:
            if entry.priority in counts and entry.status in counts[entry.priority]:
                counts[entry.priority][entry.status] += 1

        print("\n" + "=" * 55)
        print("          UI STAGE 1 REVIEW LEDGER SUMMARY")
        print("=" * 55)
        print(f"{'Priority':<10} | {'Open':<8} | {'In Prog':<8} | {'Fixed':<8} | {'Deferred':<8}")
        print("-" * 55)
        for priority in VALID_PRIORITIES:
            row = counts[priority]
            print(
                f"{priority:<10} | {row['Open']:<8} | {row['In Progress']:<8} | {row['Fixed']:<8} | {row['Deferred']:<8}"
            )
        print("=" * 55)
        total_fixed = sum(counts[p]["Fixed"] for p in VALID_PRIORITIES)
        total_open = sum(counts[p]["Open"] for p in VALID_PRIORITIES)
        print(f"Total Entries: {len(entries)} | Fixed: {total_fixed} | Open: {total_open}\n")

    @staticmethod
    def _extract_field(text: str, field_name: str) -> str:
        """Helper to extract a bullet field like '- **Field**: Value'."""
        pattern = rf"-\s+\*\*{re.escape(field_name)}\*\*:\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""


def main() -> None:
    """CLI entry point for ui_review_loop."""
    parser = argparse.ArgumentParser(description="spec2gds UI Review & Find-and-Fix Loop Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ledger-check", help="Validate docs/ui-review-ledger.md structure and fields")
    subparsers.add_parser("summary", help="Display progress summary from the ledger")

    verify_parser = subparsers.add_parser("verify", help="Run the test check for a specific finding")
    verify_parser.add_argument("--id", required=True, help="Finding reference ID, e.g. UI-CIRCUIT-007")

    args = parser.parse_args()
    loop = UiReviewLoop()

    if args.command == "ledger-check":
        success = loop.validate_ledger()
        sys.exit(0 if success else 1)
    elif args.command == "summary":
        loop.print_summary()
    elif args.command == "verify":
        success = loop.verify_entry(args.id)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
