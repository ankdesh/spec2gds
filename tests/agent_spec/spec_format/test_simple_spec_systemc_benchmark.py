"""Acceptance checks for the simple SystemC ODT import corpus."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.agent_spec.simple_spec_systemc.build_benchmark import verify_benchmarks


_REPOSITORY = Path(__file__).resolve().parents[3]
_GENERATED = (
    _REPOSITORY
    / "benchmarks"
    / "agent_spec"
    / "simple_spec_systemc"
    / "generated"
)


def test_simple_systemc_odt_imports_are_complete_valid_and_auditable() -> None:
    """Require one valid, source-faithful package for every authored ODT."""
    manifest = json.loads(
        (_GENERATED / "benchmark_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["format"] == "spec2gds-simple-spec-systemc-import-v1"
    assert manifest["generator"] == "spec2gds-import-document"
    assert manifest["enrichment"] == {
        "openai": True,
        "model": "gpt-5.6-sol",
    }
    assert manifest["package_count"] == len(manifest["packages"]) == 4
    assert verify_benchmarks() == []

    for entry in manifest["packages"]:
        assert entry["narrative_counts"]["tables"] == 4
        assert entry["narrative_counts"]["images"] == 4
        assert entry["formal_counts"]["ipxact_documents"] >= 1
        assert entry["formal_counts"]["ports"] > 0
        assert entry["openai_model"] == "gpt-5.6-sol"
