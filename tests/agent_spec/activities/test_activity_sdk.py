"""Contract tests for Activity snapshots, read APIs, registry, and results."""

from __future__ import annotations

import io
import zipfile

import pydantic
import pytest

from spec2gds.agent_spec.activities import (
    ACTIVITY_SNAPSHOT_MIMETYPE,
    ActivityResult,
    ActivityScopes,
    ActivitySnapshot,
    ActivityTestHarness,
    SpecAccess,
    SpecExtensionRegistry,
    activity,
    invoke_activity,
    load_extension_modules,
    render_context,
)
from spec2gds.agent_spec.activities.contracts import ActivityContext
from spec2gds.agent_spec.activities.reference import register_extensions
from spec2gds.agent_spec.spec_format.ir import ComponentIR, SpecRevision
from spec2gds.agent_spec.spec_format.testing import build_test_package


def revision() -> SpecRevision:
    return SpecRevision.from_package(build_test_package())


def test_full_source_snapshot_is_deterministic_source_only_and_round_trips() -> None:
    source = revision()
    package = source.to_package()
    package.files["activity/v1/legacy.json"] = b'{"ignored":true}'
    with_activity = SpecRevision.from_package(package)
    target = with_activity.entry_designs()[0].ref

    first = ActivitySnapshot.create(with_activity, target)
    second = ActivitySnapshot.create(with_activity, target)
    encoded = first.to_bytes()
    restored = ActivitySnapshot.from_bytes(encoded)

    assert encoded == second.to_bytes()
    assert first.manifest.snapshot_id == restored.manifest.snapshot_id
    assert restored.target == target
    assert restored.revision.source_revision_hash == with_activity.source_revision_hash
    assert "activity/v1/legacy.json" not in restored.revision.to_package().files
    assert set(restored.manifest.dependency_closure) == set(source.dependency_closure(target))
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        assert archive.namelist() == ["mimetype", "snapshot.json", "source/source.spec"]
        assert archive.read("mimetype") == ACTIVITY_SNAPSHOT_MIMETYPE.encode("ascii")


def test_snapshot_rejects_tampered_embedded_source() -> None:
    snapshot = ActivitySnapshot.create(revision())
    encoded = snapshot.to_bytes()
    with zipfile.ZipFile(io.BytesIO(encoded)) as source:
        manifest = source.read("snapshot.json")
        package = source.read("source/source.spec") + b"tampered"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", ACTIVITY_SNAPSHOT_MIMETYPE)
        archive.writestr("snapshot.json", manifest)
        archive.writestr("source/source.spec", package)
    with pytest.raises(ValueError, match="hash does not match"):
        ActivitySnapshot.from_bytes(output.getvalue())


def test_high_and_low_level_apis_share_identity_and_are_read_only() -> None:
    source = revision()
    target = source.entry_designs()[0].ref
    access = SpecAccess(source, target)

    components = access.high.entities(kind="component")
    assert len(components) == len(access.low.components)
    first = components.first()
    assert first is not None
    assert isinstance(access.low.resolve(first.ref), ComponentIR)
    assert components.where(name=first.name).one().ref == first.ref
    assert access.high.related(target, "dependencies").where(kind="component")
    assert "Primary entry design" in access.high.text.linked_to(target).plain_text()
    assert not hasattr(access.low, "save")
    assert not hasattr(access.low, "to_package")

    manifest = access.low.manifest
    manifest.entry_designs.clear()
    assert access.low.entry_designs()


def test_reference_extensions_register_invoke_and_render() -> None:
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    snapshot = ActivitySnapshot.create(revision(), revision().entry_designs()[0].ref)

    result = invoke_activity(registry, "reference.spec_summary", snapshot)
    rendered = render_context(registry, "reference.spec_text_context", snapshot)

    assert result.report["component_count"] == 3
    assert result.artifacts[0].role == "spec.summary"
    assert b"Components: 3" in result.artifacts[0].data
    assert rendered.snapshot_id == snapshot.manifest.snapshot_id
    assert "DEPENDENCIES" in rendered.text

    harness = ActivityTestHarness(registry)
    assert harness.invoke("reference.spec_summary", snapshot) == result


def test_configured_plugin_errors_are_isolated_and_reported() -> None:
    registry = load_extension_modules(
        [
            "does_not_exist.activities:register",
            "spec2gds.agent_spec.activities.reference:register_extensions",
            "spec2gds.agent_spec.activities.reference:register_extensions",
        ]
    )
    assert [item.activity_id for item in registry.activities()] == ["reference.spec_summary"]
    assert len(registry.diagnostics) == 2
    assert "does_not_exist.activities:register" in registry.diagnostics[0].import_path
    assert "already registered" in registry.diagnostics[1].message


class CountReport(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    count: int


@activity(
    activity_id="tests.bad_role",
    version="1.0.0",
    title="Bad role",
    description="Return an artifact role not declared by the definition.",
    scopes=ActivityScopes(document=True),
    report_model=CountReport,
)
def bad_role(context: ActivityContext) -> ActivityResult:
    artifact = context.outputs.add_text(
        role="undeclared",
        name="bad.txt",
        text="bad",
    )
    return ActivityResult(summary="Invalid result.", report={"count": 1}, artifacts=(artifact,))


def test_result_validation_rejects_undeclared_artifact_roles() -> None:
    registry = SpecExtensionRegistry()
    registry.register_activity(bad_role)
    with pytest.raises(ValueError, match="undeclared artifact role"):
        invoke_activity(registry, "tests.bad_role", ActivitySnapshot.create(revision()))
