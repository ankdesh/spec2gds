"""Tiny out-of-process reference executors for the generic V1.3 action platform."""

from __future__ import annotations

import argparse
import json
import typing
from pathlib import Path


def _write_json(path: Path, value: dict[str, typing.Any]) -> None:
    """Write deterministic executor output consumed by the action service."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot_summary(input_dir: Path, output_dir: Path) -> None:
    """Summarize the language-neutral immutable snapshot bundle."""
    snapshot = json.loads((input_dir / "snapshot.json").read_text(encoding="utf-8"))
    summary = {
        "snapshot_id": snapshot["snapshot_id"],
        "source_revision_hash": snapshot["source_revision_hash"],
        "target": snapshot["target"],
        "dependency_entity_count": len(snapshot["dependency_closure"]),
        "source_document_count": len(snapshot["source_documents"]),
        "linked_narrative_count": len(snapshot["linked_narrative"]),
    }
    artifact_path = output_dir / "snapshot-summary.json"
    _write_json(artifact_path, summary)
    _write_json(
        output_dir / "completion.json",
        {
            "status": "succeeded",
            "toolchain_identity": "spec2gds.reference-actions/1.0.0",
            "report": {"summary": f"Captured {summary['dependency_entity_count']} source entities."},
            "artifacts": [
                {
                    "role": "snapshot.summary",
                    "kind": "report",
                    "media_type": "application/json",
                    "path": artifact_path.name,
                    "size": artifact_path.stat().st_size,
                }
            ],
            "proposals": [],
        },
    )


def _artifact_transform(input_dir: Path, output_dir: Path) -> None:
    """Demonstrate verified input-artifact consumption and parent lineage."""
    snapshot = json.loads((input_dir / "snapshot.json").read_text(encoding="utf-8"))
    artifacts = snapshot["input_artifacts"]
    if len(artifacts) != 1:
        raise ValueError("Artifact transform requires exactly one selected input artifact.")
    selected = artifacts[0]
    source = input_dir / selected["bundle_path"]
    transformed = source.read_text(encoding="utf-8").upper().encode("utf-8")
    artifact_path = output_dir / "transformed.txt"
    artifact_path.write_bytes(transformed)
    _write_json(
        output_dir / "completion.json",
        {
            "status": "succeeded",
            "toolchain_identity": "spec2gds.reference-actions/1.0.0",
            "report": {"summary": "Transformed one input text artifact to upper case."},
            "artifacts": [
                {
                    "role": "text.transformed",
                    "kind": "text",
                    "media_type": "text/plain",
                    "path": artifact_path.name,
                    "size": artifact_path.stat().st_size,
                    "parent_artifact_ids": [selected["artifact_id"]],
                }
            ],
            "proposals": [],
        },
    )


def _narrative_proposal(input_dir: Path, output_dir: Path) -> None:
    """Produce a harmless review-gated narrative edit proposal."""
    snapshot = json.loads((input_dir / "snapshot.json").read_text(encoding="utf-8"))
    target = snapshot["target"]
    block_id = f"proposal_{target['entity_id']}"
    block = {
        "block_id": block_id,
        "type": "paragraph",
        "text": f"Action-generated review note for {target['entity_kind']} `{target['entity_id']}`.",
    }
    _write_json(
        output_dir / "completion.json",
        {
            "status": "succeeded",
            "toolchain_identity": "spec2gds.reference-actions/1.0.0",
            "report": {"summary": "Prepared a review-gated narrative proposal."},
            "artifacts": [],
            "proposals": [
                {
                    "rationale": "Add a harmless action-generated review note.",
                    "operations": [{"type": "upsert_narrative_block", "block": block}],
                }
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    """Dispatch one trusted reference executor command."""
    parser = argparse.ArgumentParser(description="spec2gds V1.3 reference action executor")
    parser.add_argument("action", choices=["snapshot-summary", "artifact-transform", "narrative-proposal"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if args.action == "snapshot-summary":
        _snapshot_summary(input_dir, output_dir)
    elif args.action == "artifact-transform":
        _artifact_transform(input_dir, output_dir)
    else:
        _narrative_proposal(input_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
