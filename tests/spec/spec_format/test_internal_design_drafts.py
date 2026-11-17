"""Private creation and first-save contracts, without a browser or HTTP transport."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from spec2gds.spec.activities import SpecAccess
from spec2gds.spec.activities.rtl.codegen import generate_project
from spec2gds.spec.activities.systemc_rtl.codegen import prepare_project
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.sections import SECTION_INDEX_PATH
from spec2gds.spec.spec_format.testing import direct_api_endpoints
from spec2gds.spec.spec_format.v1_api import (
    CircuitLaunchRequest,
    CircuitSourceSyncRequest,
    CreateDocumentRequest,
    EditAccessRequest,
    TransactionRequest,
    create_app,
)


@pytest.fixture
def source(tmp_path, monkeypatch):
    import spec2gds.spec.spec_format.v1_api as module

    api = direct_api_endpoints(create_app(spec_root=tmp_path))
    path = tmp_path / "source.spec"
    snapshot = api["create_document"](CreateDocumentRequest(path=str(path), title="New circuit"))
    snapshot = api["transaction"](
        TransactionRequest(
            expected_source_revision_hash=snapshot["source_revision_hash"],
            validation_mode="authoring",
            operations=[{"type": "create_entity", "kind": "component", "name": "Blank Component"}],
        )
    )["snapshot"]
    ref = snapshot["components"][0]["ref"]
    registrations = []
    monkeypatch.setattr(
        module,
        "publish_circuit_document",
        lambda document, **kw: SimpleNamespace(
            document_id=document["document_id"],
            editor_url="http://localhost/circuit",
            reused_session=False,
        ),
    )
    monkeypatch.setattr(
        module, "register_circuit_source_binding", lambda *args, **kw: registrations.append(kw)
    )

    def launch():
        snapshot = api["document_snapshot"]()
        result = api["launch_circuit"](
            CircuitLaunchRequest(entity_kind="component", entity_id=ref["entity_id"])
        )
        authorization = f"Bearer {registrations[-1]['token']}"
        request = CircuitSourceSyncRequest(
            request_id="prepare", base_source_revision_hash=snapshot["source_revision_hash"]
        )
        return result, request, authorization

    def edit(operations):
        latest = api["document_snapshot"]()
        return api["transaction"](
            TransactionRequest(
                expected_source_revision_hash=latest["source_revision_hash"],
                operations=operations,
                validation_mode="authoring",
            )
        )["snapshot"]

    return api, path, ref, launch, edit


@pytest.mark.parametrize("with_ports", [False, True])
def test_empty_first_save_is_atomic_and_idempotent(source, with_ports):
    api, path, ref, launch, edit = source
    if with_ports:
        edit(
            [
                {
                    "type": "add_component_port",
                    "component": ref,
                    "port": {"name": "a", "family": "wire", "direction": "in", "range": "7:0"},
                }
            ]
        )
    launched, request, auth = launch()
    assert not launched["source_binding"]["writable"]
    assert "create-internal-design" in launched["source_binding"]["capabilities"]
    before = path.read_bytes()
    with patch("subprocess.run", side_effect=AssertionError("No implicit hardware lint")):
        prepared = api["prepare_internal_design"](request, authorization=auth)
        assert prepared["accepted"], prepared
        assert api["prepare_internal_design"](request, authorization=auth) == prepared
        assert path.read_bytes() == before
        document = prepared["document"]
        assert document["design"]["instances"] == []
        assert len(document["design"]["boundary_terminals"]) == int(with_ports)
        save = request.model_copy(
            update={"request_id": "first-save", "candidate_document": document}
        )
        assert api["preview_circuit_source"](save, authorization=auth)["accepted"]
        assert path.read_bytes() == before
        saved = api["commit_circuit_source"](save, authorization=auth)
        assert saved["accepted"], saved
        saved_bytes = path.read_bytes()
        assert api["commit_circuit_source"](save, authorization=auth) == saved
        assert path.read_bytes() == saved_bytes
    revision = SpecRevision.load(path)
    component = revision.components[0]
    internal = revision.internal_design(component)
    assert internal and len(revision.designs) == 1
    assert internal.ref.entity_id == prepared["binding"]["editable_design_id"]
    assert not revision.entry_designs()
    assert component.ref.model_dump(mode="json") == ref
    assert len(component.ports) == int(with_ports)
    assert not saved["binding"]["pending_internal_design"]
    assert launch()[0]["source_binding"]["writable"]


@pytest.mark.parametrize("choice", ["retain_reference", "remove", "cancel"])
def test_sv_choice_requires_explicit_decision_and_preserves_draft(source, choice):
    api, path, ref, launch, edit = source
    edit(
        [
            {
                "type": "upsert_entity_section",
                "parent": ref,
                "section_type": "sv",
                "type_version": 1,
                "payload": {"content": "assign reference_only_broken = ;"},
            }
        ]
    )
    _, request, auth = launch()
    before = path.read_bytes()
    prepared = api["prepare_internal_design"](request, authorization=auth)
    assert prepared["accepted"] and prepared["binding"]["sv_choice_required"]
    candidate = request.model_copy(
        update={"request_id": "save", "candidate_document": prepared["document"]}
    )
    rejected = api["commit_circuit_source"](candidate, authorization=auth)
    assert not rejected["accepted"] and "Choose Retain SV" in rejected["diagnostics"][0]["message"]
    assert path.read_bytes() == before
    if choice == "cancel":
        discarded = api["discard_internal_design"](request, authorization=auth)
        assert discarded["accepted"] and not discarded["binding"]["writable"]
        assert path.read_bytes() == before
        assert (
            SpecRevision.load(path).internal_design(SpecRevision.load(path).components[0]) is None
        )
        return
    candidate = candidate.model_copy(update={"sv_disposition": choice})
    with patch("subprocess.run", side_effect=AssertionError("Reference SV must not be linted")):
        saved = api["commit_circuit_source"](candidate, authorization=auth)
    assert saved["accepted"], saved
    revision = SpecRevision.load(path)
    assert revision.internal_design(revision.components[0])
    if choice == "remove":
        assert revision.entity_sections == ()
        return
    section = revision.entity_sections[0]
    assert section.usage == "reference" and section.content == "assign reference_only_broken = ;"
    target = revision.components[0].ref
    rtl = generate_project(SpecAccess(revision, target), target)
    assert "reference_only_broken" not in "\n".join(value.decode() for value in rtl.files.values())
    design_target = revision.internal_design(revision.components[0]).ref
    systemc = prepare_project(SpecAccess(revision, design_target), design_target)
    assert "reference_only_broken" not in "\n".join(
        value.decode() for value in systemc.source_files.values()
    )
    edit(
        [
            {
                "type": "upsert_entity_section",
                "parent": ref,
                "section_type": "sv",
                "type_version": 1,
                "payload": {"content": "logic still_reference;"},
            },
            {"type": "clear_internal_design", "component": ref},
        ]
    )
    reopened = SpecRevision.load(path)
    assert reopened.entity_sections[0].usage == "reference"
    assert b'"version": 2' in reopened.to_package().files[SECTION_INDEX_PATH]
    from spec2gds.spec.spec_format.component_verification import verify_target

    result = verify_target(reopened, target)
    assert any(item["code"] == "IMPLEMENTATION_MISSING" for item in result["diagnostics"])


def test_stale_source_and_competing_creation_leave_source_unchanged(source):
    api, path, ref, launch, edit = source
    _, first, auth = launch()
    prepared = api["prepare_internal_design"](first, authorization=auth)
    edit([{"type": "set_document_title", "title": "Changed elsewhere"}])
    before = path.read_bytes()
    candidate = first.model_copy(update={"candidate_document": prepared["document"]})
    result = api["commit_circuit_source"](candidate, authorization=auth)
    assert not result["accepted"] and result["diagnostics"][0]["code"] == "source_revision_conflict"
    assert path.read_bytes() == before

    assert api["discard_internal_design"](first, authorization=auth)["accepted"]
    _, other, other_auth = launch()
    second = api["prepare_internal_design"](other, authorization=other_auth)
    assert api["commit_circuit_source"](
        other.model_copy(update={"request_id": "winner", "candidate_document": second["document"]}),
        authorization=other_auth,
    )["accepted"]
    before = path.read_bytes()
    assert not api["prepare_internal_design"](first, authorization=auth)["accepted"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("prepare_first", [False, True])
def test_lost_spec_edit_access_rejects_creation_and_save(source, prepare_first):
    api, path, _, launch, _ = source
    launched, request, auth = launch()
    prepared = (
        api["prepare_internal_design"](request, authorization=auth) if prepare_first else None
    )
    snapshot = api["document_snapshot"]()
    grant = snapshot["edit_access"]
    api["document_edit_access"](
        "release",
        EditAccessRequest(
            context_id=grant["context_id"], participant_id="circuit:" + launched["document_id"]
        ),
        owner_document_key=snapshot["owner_document_key"],
    )
    before = path.read_bytes()
    if prepared:
        result = api["commit_circuit_source"](
            request.model_copy(update={"candidate_document": prepared["document"]}),
            authorization=auth,
        )
        assert api["discard_internal_design"](request, authorization=auth)["accepted"]
    else:
        result = api["prepare_internal_design"](request, authorization=auth)
    assert not result["accepted"] and result["diagnostics"][0]["code"] == "source_read_only"
    assert path.read_bytes() == before


@pytest.mark.parametrize("disposition", ["retain_reference", "remove"])
def test_direct_component_creation_is_atomic_and_retryable(source, disposition):
    api, path, component, launch, edit = source
    edit([{"type": "upsert_entity_section", "parent": component, "section_type": "sv", "payload": {"content": "// Reference notes"}}])
    before = api["document_snapshot"]()
    operation = {"type": "create_internal_design", "component": component, "design_id": "direct_internal", "name": "Direct internal", "sv_disposition": disposition}
    request = TransactionRequest(expected_source_revision_hash=before["source_revision_hash"], operations=[operation], validation_mode="authoring")
    saved = api["transaction"](request)["snapshot"]
    assert len(saved["designs"]) == 1
    assert saved["entry_designs"] == []
    assert saved["component_compositions"][0]["internal_design"]["entity_id"] == "direct_internal"
    data = path.read_bytes()
    replay = api["transaction"](request)["snapshot"]
    assert replay["source_revision_hash"] == saved["source_revision_hash"]
    assert path.read_bytes() == data
    assert all(section["usage"] == "reference" for section in saved["entity_sections"])
    assert len(saved["entity_sections"]) == int(disposition == "retain_reference")
