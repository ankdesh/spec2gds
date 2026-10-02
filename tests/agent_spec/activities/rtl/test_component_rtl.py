"""Tests for direct component-level RTL generation."""

from __future__ import annotations

from pathlib import Path
import tempfile

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    activity_availability,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.spec_format.ir import SpecRevision

ROOT = Path(__file__).resolve().parents[4]
SAMPLE_SPEC = ROOT / "samples/minimal/single_component_with_rtl.spec"


def test_component_rtl_generation_succeeds_for_leaf_component() -> None:
    revision = SpecRevision.load(str(SAMPLE_SPEC))
    assert revision.components, "Sample spec must define at least one component."
    component = revision.components[0]

    registry = SpecExtensionRegistry()
    register_extensions(registry)

    snapshot = ActivitySnapshot.create(revision, component.ref)
    availability = activity_availability(registry, "rtl.generate", snapshot)

    assert availability.available is True, f"RTL generation should be available for component: {availability.diagnostics}"

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = LocalActivityWorkspace(Path(temp_dir))
        result = invoke_activity(registry, "rtl.generate", snapshot, workspace)

        assert result.report["generator_id"] == "rtl.generate"
        assert result.report["top_module"] == "new_component"
        assert result.report["wrapper_generated"] is False
        assert result.report["module_count"] == 1

        output_dir = Path(temp_dir) / result.report["output_path"]
        assert (output_dir / "rtl/components/new_component.sv").is_file()
        assert (output_dir / "rtl/files.f").is_file()
        assert (output_dir / "Makefile").is_file()
        assert (output_dir / "generation-manifest.json").is_file()
