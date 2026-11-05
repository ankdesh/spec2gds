"""Catalog imports preserve source, reject conflicts, and remap local references."""

import dataclasses
import json
from pathlib import Path

import pytest

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.catalog_import import (
    CatalogImportRequest,
    bounded_package,
    origins,
    prepare_import,
)
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import sha256_digest
from spec2gds.spec.spec_format.transactions import (
    ImportCatalogPackage,
    SpecEditTransaction,
    UpdateParameter,
)

CATALOG = Path(__file__).resolve().parents[3] / "spec_catalog_service/catalog"


def release(component="barrel_shift", category="logic"):
    raw = (CATALOG / category / component / "1.0.0" / f"{component}.spec").read_bytes()
    source = bounded_package(raw)
    package = source.to_package()
    asset = next(a for a in source.assets if a.asset_id == "library_catalogue_v1")
    return source, {
        "metadata": json.loads(package.files[asset.path]),
        "package_sha256": sha256_digest(raw),
        "evidence": [],
    }


def request(destination, details, **kwargs):
    return CatalogImportRequest(
        component_key="test-key",
        version="1.0.0",
        package_sha256=details["package_sha256"],
        expected_source_revision_hash=destination.source_revision_hash,
        **kwargs,
    )


def test_import_reopen_reuse_and_changed_local_copy(tmp_path):
    destination = SpecRevision.from_package(SpecPackage.create(title="My loaded Spec"))
    source, details = release()
    original = source.to_package().to_bytes()
    preview, candidate = prepare_import(destination, source, details, request(destination, details))
    assert preview["can_import"] and not preview["reused"]
    path = tmp_path / "imported.spec"
    candidate.to_package().save(str(path))
    reopened = SpecRevision.load(path)
    assert reopened.narrative.title == "My loaded Spec"
    assert reopened.components[0].parameters == source.components[0].parameters
    assert reopened.entity_sections[0].content == source.entity_sections[0].content
    assert source.to_package().to_bytes() == original
    assert origins(reopened)[0]["source_vlnv"] == source.components[0].vlnv
    reused, same = prepare_import(reopened, source, details, request(reopened, details))
    assert reused["reused"] and same.source_revision_hash == reopened.source_revision_hash
    parameter = dataclasses.asdict(reopened.components[0].parameters[0])
    parameter["value"] = "16"
    changed = (
        SpecEditTransaction(
            reopened.source_revision_hash,
            (UpdateParameter(reopened.components[0].ref, parameter),),
            "authoring",
        )
        .apply(reopened)
        .revision
    )
    conflict, candidate = prepare_import(changed, source, details, request(changed, details))
    assert not conflict["can_import"] and candidate is None
    renamed, candidate = prepare_import(
        changed, source, details, request(changed, details, renamed_copy=True)
    )
    assert renamed["can_import"] and len(candidate.components) == 2
    assert len({c.vlnv for c in candidate.components}) == 2
    assert candidate.components[0].parameters[0].value == "16"


def test_transaction_import_and_second_distinct_release():
    destination = SpecRevision.from_package(SpecPackage.create(title="Two definitions"))
    for component in ("barrel_shift", "mux"):
        source, details = release(component)
        operation = ImportCatalogPackage(source, details, request(destination, details))
        result = SpecEditTransaction(
            destination.source_revision_hash, (operation,), "authoring"
        ).apply(destination)
        assert result.succeeded, result.diagnostics
        destination = result.revision
    assert len(destination.components) == 2
    assert len(origins(destination)) == 2
    assert len({s.section_id for s in destination.entity_sections}) == 2


def test_stale_revision_and_invalid_archive_leave_destination_unchanged():
    destination = SpecRevision.from_package(SpecPackage.create())
    source, details = release()
    with pytest.raises(ValueError, match="Stale"):
        prepare_import(
            destination,
            source,
            details,
            request(destination, details).model_copy(
                update={"expected_source_revision_hash": "old"}
            ),
        )
    assert not destination.components
    with pytest.raises(Exception):
        bounded_package(b"not a package")


def test_composite_import_remaps_internal_design_and_preserves_entry_designs():
    from spec2gds.spec.spec_format.testing import build_test_package

    # The shared fixture includes a containing Component, internal Design and leaf.
    package = build_test_package()
    source = SpecRevision.from_package(package)
    root = next(c for c in source.components if source.internal_design(c))
    details = {
        "metadata": {"root": root.ref.model_dump(mode="json")},
        "package_sha256": sha256_digest(package.to_bytes()),
    }
    destination = SpecRevision.from_package(SpecPackage.create())
    preview, candidate = prepare_import(destination, source, details, request(destination, details))
    assert preview["can_import"]
    copied = candidate.resolve(type(root.ref).model_validate(preview["root"]))
    internal = candidate.internal_design(copied)
    assert internal and internal.ref.document_id == destination.document_id
    assert not candidate.to_package().manifest.entry_designs
    assert all(candidate.by_vlnv("component", i.component_vlnv) for i in internal.instances)


def test_import_api_keeps_document_binding_and_rejects_a_stale_preview(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from spec2gds.spec.spec_format.v1_api import CreateDocumentRequest, create_app

    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    app = create_app()
    endpoints = {r.name: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
    first = endpoints["create_document"](
        CreateDocumentRequest(path=str(tmp_path / "first.spec"), title="First")
    )
    key = first["owner_document_key"]
    second = endpoints["create_document"](
        CreateDocumentRequest(path=str(tmp_path / "second.spec"), title="Second")
    )
    source, details = release()
    monkeypatch.setattr(app.state.catalog_client, "release", lambda _: (source, details))
    value = CatalogImportRequest(
        component_key="barrel",
        version="1.0.0",
        package_sha256=details["package_sha256"],
        expected_source_revision_hash=first["source_revision_hash"],
    )
    preview = endpoints["preview_catalog_import"](value, key)
    assert preview["can_import"]
    assert not SpecRevision.load(tmp_path / "first.spec").components
    committed = endpoints["commit_catalog_import"](value, key)
    assert committed["snapshot"]["narrative"]["title"] == "First"
    assert len(SpecRevision.load(tmp_path / "first.spec").components) == 1
    assert not SpecRevision.load(tmp_path / "second.spec").components
    with pytest.raises(HTTPException) as stale:
        endpoints["commit_catalog_import"](value, key)
    assert stale.value.status_code == 409
    assert second["owner_document_key"] != key


def test_rtl_launch_verifies_without_receipt_and_records_failed_checks(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from spec2gds.spec.spec_format import component_verification
    from spec2gds.spec.spec_format.v1_api import (
        ActivityExecutionRequest,
        OpenDocumentRequest,
        create_app,
    )

    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    source, _ = release()
    path = tmp_path / "barrel.spec"
    source.to_package().save(str(path))
    app = create_app()
    endpoints = {r.name: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(path)))
    ref = opened["components"][0]["ref"]
    args = ("component", ref["entity_id"])
    assert next(
        a
        for a in endpoints["entity_activities"](*args)["activities"]
        if a["definition"]["activity_id"] == "rtl.generate"
    )["availability"]["available"]
    requested = ActivityExecutionRequest(
        expected_source_revision_hash=opened["source_revision_hash"]
    )
    verified = component_verification.verify_target
    for unavailable in (False, True):
        monkeypatch.setattr(
            component_verification,
            "verify_target",
            lambda rev, target: {
                "target": target.model_dump(mode="json"),
                "source_revision_hash": rev.source_revision_hash,
                "status": "failed",
                "tool_version": "Unavailable" if unavailable else "Verilator",
                "diagnostics": [
                    {
                        "code": "VERILATOR_UNAVAILABLE" if unavailable else "LINT_ERROR",
                        "blocking": True,
                        "message": "Check failed",
                    }
                ],
            },
        )
        with pytest.raises(HTTPException) as failed:
            endpoints["launch_activity"](*args, "rtl.generate", requested)
        assert failed.value.status_code == (503 if unavailable else 422)
        assert failed.value.detail["verification"]["status"] == "failed"
        assert next(
            a
            for a in endpoints["entity_activities"](*args)["activities"]
            if a["definition"]["activity_id"] == "rtl.generate"
        )["availability"]["available"]
    monkeypatch.setattr(component_verification, "verify_target", verified)
    # A failed receipt must not block a new successful launch.
    result = endpoints["launch_activity"](*args, "rtl.generate", requested)
    assert result["status"] in {"queued", "running", "succeeded"}


def test_composite_renamed_copy_has_its_own_internal_design_and_reuses_leaf_definitions():
    from spec2gds.spec.spec_format.testing import build_test_package

    source = SpecRevision.from_package(build_test_package())
    root = next(c for c in source.components if source.internal_design(c))
    details = {
        "metadata": {"root": root.ref.model_dump(mode="json")},
        "package_sha256": sha256_digest(source.to_package().to_bytes()),
    }
    destination = SpecRevision.from_package(SpecPackage.create())
    _, first = prepare_import(destination, source, details, request(destination, details))
    preview, second = prepare_import(
        first, source, details, request(first, details, renamed_copy=True)
    )
    assert preview["can_import"]
    composites = [c for c in second.components if second.internal_design(c)]
    assert len(composites) == 2
    assert len({second.internal_design(c).ref.entity_id for c in composites}) == 2
    assert any(row["reused"] for row in preview["definitions"])


def test_all_published_components_import_with_their_defaults():
    destination = SpecRevision.from_package(SpecPackage.create(title="All published Components"))
    paths = sorted(CATALOG.rglob("*.spec"))
    for path in paths:
        source = bounded_package(path.read_bytes())
        package = source.to_package()
        metadata = next(a for a in source.assets if a.asset_id == "library_catalogue_v1")
        details = {
            "metadata": json.loads(package.files[metadata.path]),
            "package_sha256": sha256_digest(path.read_bytes()),
        }
        preview, candidate = prepare_import(
            destination, source, details, request(destination, details)
        )
        assert preview["can_import"], path
        imported = candidate.resolve(type(source.components[0].ref).model_validate(preview["root"]))
        assert imported.parameters == source.components[0].parameters
        destination = candidate
    assert len(destination.components) >= len(paths)
    assert len(origins(destination)) == len(paths)


def test_narrative_assets_and_nested_references_are_remapped():
    from spec2gds.spec.spec_format.models import EntityRef, NarrativeBlock

    source, details = release()
    package = source.to_package()
    component = source.components[0].ref
    package.add_asset(
        "source_illustration", b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml", "svg"
    )
    asset = EntityRef(
        document_id=source.document_id, entity_id="source_illustration", entity_kind="asset"
    )
    block = NarrativeBlock(
        block_id="import_notes",
        type="paragraph",
        text="Interface reference",
        entity_refs=[component, asset],
        options={
            "selection": component.model_dump(mode="json"),
            "picture": asset.model_dump(mode="json"),
        },
    )
    package.narrative = package.narrative.model_copy(update={"blocks": [block]})
    source = SpecRevision.from_package(package)
    details["package_sha256"] = sha256_digest(package.to_bytes())
    destination = SpecRevision.from_package(SpecPackage.create())
    preview, candidate = prepare_import(destination, source, details, request(destination, details))
    assert preview["can_import"]
    copied = candidate.narrative.blocks[0].children[0]
    assert {ref.entity_kind for ref in copied.entity_refs} == {"component", "asset"}
    assert all(ref.document_id == destination.document_id for ref in copied.entity_refs)
    assert copied.options["picture"]["entity_kind"] == "asset"
    assert copied.options["selection"]["entity_id"] == candidate.components[0].ref.entity_id
    assert copied.options["picture"]["entity_id"] != candidate.components[0].ref.entity_id


def test_unsupported_annotations_and_corrupt_downloads_cannot_mutate_a_spec(monkeypatch):
    from hashlib import sha256

    from spec2gds.spec.spec_format.catalog_import import CatalogClient
    from spec2gds.spec.spec_format.models import AnnotationSchemaEntry

    source, details = release()
    destination = SpecRevision.from_package(SpecPackage.create())
    value = request(destination, details).model_copy(
        update={
            "component_key": sha256(
                source.components[0].vlnv.rsplit(":", 1)[0].encode()
            ).hexdigest()
        }
    )
    client = CatalogClient("http://catalog.invalid")
    raw = source.to_package().to_bytes()
    monkeypatch.setattr(
        client,
        "get",
        lambda path, params=None, binary=False: raw + b"changed" if binary else details,
    )
    with pytest.raises(ValueError, match="digest"):
        client.release(value)
    package = source.to_package()
    package.files["annotations/foreign/ref.json"] = json.dumps(
        source.components[0].ref.model_dump(mode="json")
    ).encode()
    package.manifest = package.manifest.model_copy(
        update={
            "annotation_schemas": [
                *package.manifest.annotation_schemas,
                AnnotationSchemaEntry(
                    namespace="foreign.references", version=1, path_prefix="annotations/foreign"
                ),
            ]
        }
    )
    annotated = SpecRevision.from_package(package)
    before = destination.source_revision_hash
    with pytest.raises(ValueError, match="annotation namespace"):
        prepare_import(destination, annotated, details, value)
    assert destination.source_revision_hash == before
