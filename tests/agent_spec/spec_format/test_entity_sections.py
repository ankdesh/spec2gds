"""Acceptance coverage for extensible entity sections and SV persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.assistant import (
    SpecChangeProposal,
    build_assistant_context,
    preview_assistant_proposal,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.sections import (
    SECTION_INDEX_PATH,
    SECTION_NAMESPACE,
    SV_MAX_BYTES,
    delete_entity_section,
    upsert_systemverilog_section,
)
from spec2gds.agent_spec.spec_format.testing import build_test_package
from spec2gds.agent_spec.spec_format.transactions import (
    CreateEntity,
    DeleteDocument,
    SpecEditTransaction,
    UpsertEntitySection,
)


def test_sv_section_round_trips_deterministically_and_cleans_registration(tmp_path: Path) -> None:
    package = build_test_package()
    revision = SpecRevision.from_package(package)
    leaf = revision.by_vlnv("component", "spec2gds.example:demo:leaf:1.0")
    section = upsert_systemverilog_section(package, leaf.ref, "assign irq = irq_in;\r\n")

    assert section.content == "assign irq = irq_in;\n"
    assert package.files[section.source_path] == b"assign irq = irq_in;\n"
    assert any(item.namespace == SECTION_NAMESPACE for item in package.manifest.annotation_schemas)

    destination = tmp_path / "sections.spec"
    package.save(destination)
    reopened = SpecRevision.from_package(SpecPackage.load(destination))
    assert reopened.entity_sections_for(leaf.ref, "sv")[0].section_id == section.section_id
    assert reopened.to_package().to_bytes() == reopened.to_package().to_bytes()

    mutable = reopened.to_package()
    delete_entity_section(mutable, leaf.ref, "sv")
    assert SECTION_INDEX_PATH not in mutable.files
    assert not any(item.namespace == SECTION_NAMESPACE for item in mutable.manifest.annotation_schemas)


def test_sv_boundaries_and_portability_checks() -> None:
    package = build_test_package()
    leaf = SpecRevision.from_package(package).by_vlnv(
        "component", "spec2gds.example:demo:leaf:1.0"
    )
    exact = "//" + "x" * (SV_MAX_BYTES - 2)
    upsert_systemverilog_section(package, leaf.ref, exact)
    assert len(package.files[next(path for path in package.files if path.endswith(".sv"))]) == SV_MAX_BYTES

    with pytest.raises(ValueError, match="256 KiB"):
        upsert_systemverilog_section(package, leaf.ref, exact + "x")
    with pytest.raises(ValueError, match="NUL"):
        upsert_systemverilog_section(package, leaf.ref, "assign irq = 1'b0;\x00")
    with pytest.raises(ValueError, match="module bodies"):
        upsert_systemverilog_section(package, leaf.ref, "module nested; endmodule")
    with pytest.raises(ValueError, match="include"):
        upsert_systemverilog_section(package, leaf.ref, "`include \"external.svh\"")
    for directive in ['`include "external.svh"', '`line 1 "external.sv" 0']:
        with pytest.raises(ValueError, match="directives"):
            upsert_systemverilog_section(package, leaf.ref, f"assign irq = irq_in; {directive}")
    literal = '// `include "ignored.sv"\ninitial $display("`line 1 is text");'
    assert upsert_systemverilog_section(package, leaf.ref, literal).content == literal


def test_loading_rejects_digest_mismatch_but_old_packages_remain_valid() -> None:
    package = build_test_package()
    assert SpecRevision.from_package(package).entity_sections == ()
    leaf = SpecRevision.from_package(package).by_vlnv(
        "component", "spec2gds.example:demo:leaf:1.0"
    )
    section = upsert_systemverilog_section(package, leaf.ref, "assign irq = irq_in;\n")
    package.files[section.source_path] = b"assign irq = 1'b0;\n"

    with pytest.raises(SpecValidationError, match="hash mismatch"):
        SpecRevision.from_package(package)


def test_transactions_preserve_ids_validate_and_cascade_entity_deletion() -> None:
    revision = SpecRevision.from_package(SpecPackage.create("section_transactions"))
    created = SpecEditTransaction(
        revision.source_revision_hash, (CreateEntity("component", "counter"),)
    ).apply(revision)
    assert created.succeeded and created.revision is not None
    owner = created.revision.components[0].ref
    added = SpecEditTransaction(
        created.revision.source_revision_hash,
        (UpsertEntitySection(owner, "sv", {"content": "logic value;\n"}),),
    ).apply(created.revision)
    assert added.succeeded, added.diagnostics
    assert added.revision is not None
    first = added.revision.entity_sections_for(owner, "sv")[0]

    updated = SpecEditTransaction(
        added.revision.source_revision_hash,
        (UpsertEntitySection(owner, "sv", {"content": "logic [1:0] value;\n"}),),
    ).apply(added.revision)
    assert updated.succeeded and updated.revision is not None
    assert updated.revision.entity_sections_for(owner, "sv")[0].section_id == first.section_id

    deleted = SpecEditTransaction(
        updated.revision.source_revision_hash, (DeleteDocument(owner),)
    ).apply(updated.revision)
    assert deleted.succeeded and deleted.revision is not None
    assert deleted.revision.entity_sections == ()


def test_generic_registry_operations_adapt_text_and_ports_to_ipxact() -> None:
    revision = SpecRevision.from_package(SpecPackage.create("section_adapters"))
    created = SpecEditTransaction(
        revision.source_revision_hash, (CreateEntity("component", "adapter"),)
    ).apply(revision)
    assert created.succeeded and created.revision is not None
    owner = created.revision.components[0].ref
    edited = SpecEditTransaction(
        created.revision.source_revision_hash,
        (
            UpsertEntitySection(owner, "text", {"content": "Behavioral adapter"}),
            UpsertEntitySection(owner, "ports", {"ports": [
                {"name": "clock", "family": "wire", "direction": "in", "range": None},
                {"name": "ready", "family": "wire", "direction": "out", "range": None},
            ]}),
        ),
    ).apply(created.revision)
    assert edited.succeeded, edited.diagnostics
    assert edited.revision is not None
    component = edited.revision.components[0]
    assert [item.name for item in component.ports] == ["clock", "ready"]
    package = edited.revision.to_package()
    source = package.files[next(item.path for item in package.manifest.documents if item.entity_id == owner.entity_id)]
    assert b"Behavioral adapter" in source


def test_index_rejects_duplicate_singleton() -> None:
    package = build_test_package()
    leaf = SpecRevision.from_package(package).by_vlnv(
        "component", "spec2gds.example:demo:leaf:1.0"
    )
    upsert_systemverilog_section(package, leaf.ref, "")
    index = json.loads(package.files[SECTION_INDEX_PATH])
    duplicate = dict(index["sections"][0])
    duplicate["section_id"] = "section_sv_duplicate"
    duplicate["path"] = "annotations/entity-sections/sv/section_sv_duplicate.sv"
    package.files[duplicate["path"]] = b""
    index["sections"].append(duplicate)
    package.files[SECTION_INDEX_PATH] = (json.dumps(index) + "\n").encode()

    with pytest.raises(SpecValidationError, match="too many sv sections"):
        SpecRevision.from_package(package)


def test_assistant_context_and_proposals_use_typed_sv_operations() -> None:
    revision = SpecRevision.from_package(SpecPackage.create("assistant_sections"))
    created = SpecEditTransaction(
        revision.source_revision_hash, (CreateEntity("component", "assistant_unit"),)
    ).apply(revision)
    assert created.revision is not None
    owner = created.revision.components[0].ref
    proposal = SpecChangeProposal(
        proposal_id="proposal_sv_upsert",
        document_id=created.revision.document_id,
        target=owner,
        base_source_revision_hash=created.revision.source_revision_hash,
        title="Add behavior",
        summary="Add an SV declaration.",
        rationale="Exercise typed section proposals.",
        operations=[{
            "operation_id": "op_sv",
            "type": "upsert_entity_section",
            "owner": owner.model_dump(mode="json"),
            "section_type": "sv",
            "type_version": 1,
            "payload": {"content": "logic assistant_marker;\n"},
        }],
    )
    preview = preview_assistant_proposal(created.revision, proposal)
    assert preview["status"] == "valid"
    candidate = preview["_revision"]
    context = build_assistant_context(candidate, owner)
    projected = context["writable"]["sections"]
    assert any(
        item["payload"]["content"] == "logic assistant_marker;\n"
        for section in projected
        for item in section["content_sections"]
        if item["section_type"] == "sv"
    )

    section_id = candidate.entity_sections_for(owner, "sv")[0].section_id
    delete = SpecChangeProposal(
        proposal_id="proposal_sv_delete",
        document_id=candidate.document_id,
        target=owner,
        base_source_revision_hash=candidate.source_revision_hash,
        title="Delete behavior",
        summary="Remove the SV section.",
        rationale="Exercise typed section deletion.",
        operations=[{
            "operation_id": "op_delete_sv",
            "type": "delete_entity_section",
            "owner": owner.model_dump(mode="json"),
            "section_type": "sv",
            "section_id": section_id,
        }],
    )
    deleted = preview_assistant_proposal(candidate, delete)
    assert deleted["status"] == "valid"
    assert deleted["_revision"].entity_sections == ()
