#!/usr/bin/env python3
"""Preview or remove physical-port display labels from project Spec archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format import ipxact


def clean_package(package: SpecPackage) -> tuple[SpecPackage, int]:
    """Prepare a private replacement; never copy label text into descriptions."""
    replacement = SpecPackage.from_bytes(package.to_bytes())
    count = 0
    for entry in list(replacement.manifest.documents):
        if entry.kind != "component":
            continue
        root = ipxact.parse_xml(replacement.files[entry.path])
        labels = root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']/*[local-name()='displayName']")
        if not labels:
            continue
        for label in labels:
            label.getparent().remove(label)
        count += len(labels)
        import lxml.etree as ET
        replacement.add_document(entry.kind, ET.tostring(root))
    return replacement, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    roots = (project, project.parent / "spec_samples")
    paths = sorted({path.resolve() for root in roots if root.exists() for path in root.rglob("*.spec")
                    if path.is_file() and not {"node_modules", ".git", ".venv"}.intersection(path.parts)
                    and any(path.resolve().is_relative_to(allowed) for allowed in roots)})
    report = {"applied": args.apply, "roots": list(map(str, roots)), "files": []}
    args.output.mkdir(parents=True, exist_ok=True)
    for path in paths:
        try:
            original = path.read_bytes()
            digest = hashlib.sha256(original).hexdigest()
            replacement, count = clean_package(SpecPackage.from_bytes(original))
            if not count:
                continue
            record = {"path": str(path), "labels": count, "before_sha256": digest}
            if args.apply:
                # Backups can live inside the checkout. Do not make them inputs
                # to a later cleanup run, which scans active *.spec files.
                backup = args.output / "backups" / (hashlib.sha256(str(path).encode()).hexdigest()[:16] + ".spec.bak")
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(path, backup)
                if path.read_bytes() != original:
                    raise ValueError("The Spec changed after cleanup preview; retry with the current source.")
                replacement.save(str(path))
                record.update(backup=str(backup), after_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            report["files"].append(record)
        except Exception as exc:
            report["files"].append({"path": str(path), "error": str(exc)})
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(any("error" in item for item in report["files"]))


if __name__ == "__main__":
    sys.exit(main())
