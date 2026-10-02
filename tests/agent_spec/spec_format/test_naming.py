"""Acceptance coverage for presentation names and stable source authority."""

from pathlib import Path

import pytest

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.document import build_document_projection
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock
from spec2gds.agent_spec.spec_format.naming import (
    clean_name,
    entity_name,
    filename_stem,
    name_key,
    normalize_package_names,
    qualified_reference_name,
    require_unique_name,
    select_entity,
    select_reference,
    unique_name,
)
from spec2gds.agent_spec.spec_format.owner_store import OwnerBindings
from spec2gds.agent_spec.spec_format.testing import build_test_package
from spec2gds.agent_spec.spec_format.transactions import (
    CreateEntity,
    SetEntityMetadata,
    SpecEditTransaction,
    UpsertNarrativeBlock,
)


def test_names_compare_unicode_whitespace_and_case_and_suggest_numbers():
    assert clean_name("  ＦＩＦＯ\n timer ") == "FIFO timer"
    assert name_key("Straße") == name_key("STRASSE")
    assert unique_name("timer", ["Timer", "Timer 2"]) == "timer 3"
    with pytest.raises(ValueError, match="fifo 2"):
        require_unique_name("fifo", ["ＦＩＦＯ"])
    with pytest.raises(ValueError):
        clean_name(" ")
    assert filename_stem("../Café / Timer") == "cafe-timer"
    assert filename_stem("CON") == "document-con"
    assert filename_stem("../../") == "document"


def test_normalization_is_idempotent_and_preserves_identity():
    package = build_test_package()
    identities = [(entry.entity_id, entry.vlnv, entry.path) for entry in package.manifest.documents]
    package.narrative = package.narrative.model_copy(update={"title": "", "blocks": [
        NarrativeBlock(block_id="a", type="section", text="Timer"),
        NarrativeBlock(block_id="b", type="section", text="timer"),
    ]})
    for entry in package.manifest.documents:
        root = ipxact.parse_xml(package.files[entry.path])
        for label in root.xpath("./*[local-name()='displayName']"):
            label.getparent().remove(label)
        from lxml import etree
        package.add_document(entry.kind, etree.tostring(root))
    assert normalize_package_names(package, "Example")
    assert [block.text for block in package.narrative.blocks] == ["Timer", "timer 2"]
    digest = package.source_hash()
    assert not normalize_package_names(package)
    assert package.source_hash() == digest
    assert [(entry.entity_id, entry.vlnv, entry.path) for entry in package.manifest.documents] == identities


def test_display_creation_and_rename_preserve_hardware_and_symbols():
    revision = SpecRevision.from_package(SpecPackage.create(title="Timers"))
    result = SpecEditTransaction(revision.source_revision_hash, (
        CreateEntity("component", "Timer A", "timer-a"),
        CreateEntity("component", "Timer-A", "timer-b"),
    )).apply(revision)
    assert result.succeeded, result.diagnostics
    revision = result.revision
    assert [item.vlnv.split(":")[2] for item in revision.components] == ["timer_a", "timer_a_2"]
    target = select_entity(revision, "timer a")
    renamed = SpecEditTransaction(revision.source_revision_hash, (
        SetEntityMetadata(target.ref, display_name="Countdown timer", short_description=None, description=None),
    )).apply(revision)
    assert renamed.succeeded, renamed.diagnostics
    current = renamed.revision.resolve(target.ref)
    assert current.vlnv == target.vlnv
    assert current.ports == target.ports
    assert entity_name(current) == "Countdown timer"
    with pytest.raises(ValueError, match="Unknown or ambiguous"):
        select_entity(renamed.revision, "timer a")
    conflict = SpecEditTransaction(renamed.revision.source_revision_hash, (
        SetEntityMetadata(target.ref, display_name="TIMER-A", short_description=None, description=None),
    )).apply(renamed.revision)
    assert not conflict.succeeded


def test_authored_section_rename_keeps_references_and_requires_unique_siblings():
    revision = SpecRevision.from_package(SpecPackage.create(title="Timers"))
    parent = NarrativeBlock(block_id="parent", type="section", text="Operation", children=[
        NarrativeBlock(block_id="child", type="section", text="Timing"),
    ])
    result = SpecEditTransaction(revision.source_revision_hash, (UpsertNarrativeBlock(parent),)).apply(revision)
    assert result.succeeded
    revision = result.revision
    ref = EntityRef(document_id=revision.document_id, entity_kind="narrative_block", entity_id="child")
    assert qualified_reference_name(revision, ref) == "Timers › Operation › Timing"
    result = SpecEditTransaction(revision.source_revision_hash, (
        UpsertNarrativeBlock(revision.resolve(ref).model_copy(update={"text": "Cycle timing"})),
    )).apply(revision)
    assert result.succeeded
    assert result.revision.resolve(ref).text == "Cycle timing"


def test_document_links_have_owner_resolved_names_and_correct_anchors():
    package = build_test_package()
    normalize_package_names(package)
    revision = SpecRevision.from_package(package)
    projection = build_document_projection(revision)
    links = [block for section in projection.sections for block in section.narrative if block["type"] == "entity_link"]
    assert links
    for block in links:
        for ref in block["entity_refs"]:
            label = block["entity_labels"][f"{ref['entity_kind']}:{ref['entity_id']}"]
            assert label["name"]
            assert "_" not in label["anchor"]


def test_catalog_names_and_creation_destinations_remain_reserved_across_retries(tmp_path: Path):
    catalog = OwnerBindings(tmp_path / "state")
    first = tmp_path / "timer-a.spec"
    values = {"path": str(first), "title": "Timer A", "derive_named_path": True}
    destination, identity, replay = catalog.reserve_creation("one", values)
    assert not replay
    first.write_bytes(b"source")
    assert catalog.reserve_creation("one", values) == (destination, identity, True)
    second, _, _ = catalog.reserve_creation("two", {**values, "title": "Timer-A"})
    assert second == str(tmp_path / "timer-a-2.spec")
    with pytest.raises(ValueError, match="different values"):
        catalog.reserve_creation("one", {**values, "title": "Renamed"})
    with catalog.reserve_name(str(first), identity, "Timer A"):
        pass
    with pytest.raises(ValueError, match="Timer A 2"):
        with catalog.reserve_name(second, "second", "Timer A"):
            pass


def test_document_display_rename_preserves_source_path_and_exact_package_binding(tmp_path: Path):
    from spec2gds.agent_spec.spec_format.transactions import SetDocumentTitle
    from spec2gds.agent_spec.spec_format.v1_api import V1Session
    source = tmp_path / "original.spec"
    SpecPackage.create(title="Original").save(str(source))
    session = V1Session(str(source))
    catalog = OwnerBindings(tmp_path / "state")
    session.name_catalog = catalog
    before = session.owner_document_key, session.revision.document_id, session.path
    result = SpecEditTransaction(session.revision.source_revision_hash, (SetDocumentTitle("Renamed document"),)).apply(session.revision)
    assert result.succeeded
    session.commit_revision(result.revision)
    assert before == (session.owner_document_key, session.revision.document_id, session.path)
    assert SpecPackage.load(str(source)).narrative.title == "Renamed document"
    assert list(tmp_path.glob("*.spec")) == [source]


def test_named_sections_require_qualified_choices_when_headings_repeat():
    package = SpecPackage.create(title="Timers")
    package.narrative = package.narrative.model_copy(update={"blocks": [
        NarrativeBlock(block_id=parent, type="section", text=label, children=[
            NarrativeBlock(block_id=f"{parent}-timing", type="section", text="Timing"),
        ]) for parent, label in (("operation", "Operation"), ("reset", "Reset"))
    ]})
    revision = SpecRevision.from_package(package)
    with pytest.raises(ValueError, match="Timers › Operation › Timing"):
        select_reference(revision, "timing")
    assert select_reference(revision, "OPERATION › timing").entity_id == "operation-timing"
    assert select_reference(revision, "Timers › Reset › Timing").entity_id == "reset-timing"
    with pytest.raises(ValueError, match="Unknown or ambiguous"):
        select_reference(revision, "operation-timing")


def test_service_resolves_names_in_exact_package_and_never_falls_back(tmp_path: Path, monkeypatch):
    import fastapi

    from spec2gds.agent_spec.spec_format.v1_api import OpenDocumentRequest, create_app

    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    endpoints = {route.name: route.endpoint for route in create_app().routes if hasattr(route, "endpoint")}
    package = SpecPackage.create(title="Timer controller")
    package.narrative = package.narrative.model_copy(update={"blocks": [
        NarrativeBlock(block_id="timing-section", type="section", text="Cycle timing"),
    ]})
    source = tmp_path / "original.spec"
    package.save(str(source))
    snapshot = endpoints["open_document"](OpenDocumentRequest(path=str(source)))
    resolve = endpoints["resolve_named_target"]
    named = resolve(name="ＴＩＭＥＲ controller", entity_name="cycle timing")
    assert named["owner_document_key"] == snapshot["owner_document_key"]
    assert named["entity_id"] == "timing-section"
    copied = tmp_path / "copy.spec"
    package.save(str(copied))
    other = endpoints["open_document"](OpenDocumentRequest(path=str(copied)))
    assert other["owner_document_key"] != named["owner_document_key"]
    assert resolve(name="Timer controller 2")["owner_document_key"] == other["owner_document_key"]
    with pytest.raises(fastapi.HTTPException) as mismatch:
        resolve(name="Timer controller", owner_document_key=other["owner_document_key"])
    assert mismatch.value.status_code == 422
    with pytest.raises(fastapi.HTTPException) as no_package:
        resolve(entity_name="Cycle timing")
    assert no_package.value.status_code == 422
    with pytest.raises(fastapi.HTTPException) as ambiguous_copy:
        resolve(document_id=package.manifest.document_id, entity_name="Cycle timing")
    assert ambiguous_copy.value.status_code == 409
    source.unlink()
    with pytest.raises(fastapi.HTTPException):
        resolve(name="Timer controller")
