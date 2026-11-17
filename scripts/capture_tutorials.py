"""Prepare, capture, and publish real tutorial screenshots with provenance.

All raw output stays in a fresh ignored repository temp/TEMP_ directory. Publishing
copies only referenced screenshots into documentation assets after completeness
and hash checks. Live Assistant capture requires configured model access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_tutorials import CORE, EXTRAS
from scripts.prepare_tutorials import prepare


def capture_plan():
    """Map each published image to the exact lesson actions it illustrates."""
    plan = {}
    for lesson in CORE + EXTRAS:
        for picture in lesson["pictures"]:
            plan.setdefault(picture["name"], []).append({
                "lesson": lesson["slug"], "action": picture["after"],
                "caption": picture["caption"],
            })
    return plan


def temporary(path: Path):
    path = path.resolve()
    parts = path.relative_to(ROOT).parts
    if len(parts) < 2 or parts[0] != "temp" or not parts[1].startswith("TEMP_"):
        raise ValueError("Use a repository temp/TEMP_ directory.")
    return path


def source_digests():
    """UI source dependencies let checks flag screenshots after a UI change."""
    prefixes = ["circuit-designer/apps/editor/src", "circuit-designer/packages/document-a2ui-react/src",
                "circuit-designer/packages/app-react/src", "circuit-designer/packages/react/src",
                "testplan-service/src/testplan_service/ui/static", "ai-assistant/profile"]
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *prefixes], cwd=ROOT, text=True).splitlines()
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(set(names))}


def publish(output: Path):
    """Refuse incomplete or altered originals instead of mixing old and new shots."""
    report = json.loads((output / "captures.json").read_text())
    selected = {entry["name"]: entry for entry in report["captures"]}
    plan = capture_plan()
    inputs = source_digests()
    tree_digest = hashlib.sha256(json.dumps(inputs, separators=(",", ":")).encode()).hexdigest()
    missing = sorted(set(plan) - set(selected))
    if missing:
        raise ValueError("Capture these required states before publishing: " + ", ".join(missing))
    records = []
    for name, uses in plan.items():
        record = dict(selected[name])
        if record.get("source_tree_digest") != tree_digest:
            raise ValueError(f"UI source changed since capture: {name}. Capture a fresh take before publishing.")
        original = (output / record["file"]).resolve()
        original.relative_to(output)
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Changed capture original: {name}")
        record.update(file=f"{name}.jpg", uses=uses)
        records.append((original, record))
    assets = ROOT / "docs/tutorials/assets"
    for original, record in records:
        shutil.copyfile(original, assets / record["file"])
    manifest = {"schema_version": 1, "source_digests": inputs,
                "captures": [record for _, record in records],
                "note": "Real application captures. Prepared source is teaching data; only Assistant architecture captures labelled live used live inference. Human practice time is unmeasured."}
    (assets / "captures.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Published {len(records)} referenced screenshots and their capture manifest.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--starts", type=Path, help="Existing fresh prepared starts; otherwise prepare inside the run")
    parser.add_argument("--only", default="spec,systemc,catalog,circuit,planner,layouts",
                        help="Comma-separated capture groups. Add assistant explicitly for live model access.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Keep earlier takes and update selected captures in this run")
    parser.add_argument("--publish", action="store_true", help="Publish complete verified captures; do not start services")
    args = parser.parse_args()
    output = temporary(args.output)
    if args.dry_run:
        print(json.dumps({"output": str(output), "groups": args.only.split(","), "captures": capture_plan()}, indent=2))
        return
    if args.publish:
        publish(output)
        return
    if output.exists() and not args.resume:
        parser.error("Use a fresh output directory, or explicitly --resume to retain and extend its takes.")
    if not shutil.which("node"):
        parser.error("Node.js 24+ is required.")
    version = subprocess.check_output(["node", "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 24:
        parser.error(f"Node.js 24+ is required; found {version}.")
    output.mkdir(parents=True, exist_ok=True)
    scratch = output / "scratch"
    scratch.mkdir(exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
    environment.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "circuit-designer/.playwright-browsers"))
    starts = temporary(args.starts) if args.starts else output / "prepared"
    if args.starts is None and not starts.exists():
        prepare(starts)
    if not (starts / "starts.json").exists():
        parser.error("The starts directory is incomplete: starts.json is missing.")
    command = ["node", "--import", "tsx", "runner/capture_tutorials.ts", "--output", str(output),
               "--starts", str(starts), "--only", args.only]
    raise SystemExit(subprocess.call(command, cwd=ROOT / "tests/ui-scenarios", env=environment))


if __name__ == "__main__":
    main()
