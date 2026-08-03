"""V1.4 API/editor acceptance checks without the legacy ODT production path."""

import inspect
import tempfile
import zipfile
from pathlib import Path

import fastapi
import pytest

from spec2gds.agent_spec.spec_format.testing import build_test_package, write_test_package
from spec2gds.agent_spec.spec_format.cli import main as package_cli
from spec2gds.agent_spec.spec_format.v1_api import (
    ActionInputRequest,
    CircuitLaunchRequest,
    CreateDocumentRequest,
    OpenDocumentRequest,
    ProposalRequest,
    TransactionRequest,
    create_app,
)
from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal


def _endpoints() -> dict[str, object]:
    app = create_app()
    return {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def test_v1_api_create_edit_action_proposal_reopen_and_editor_acceptance() -> None:
    """Exercise the complete source-edit/action/review persistence workflow."""
    endpoints = _endpoints()
    assert "samples" not in endpoints
    editor_html = endpoints["editor"]()
    assert "A2UI Document Editor" in editor_html
    assert "/editor-assets/assets/index-" in editor_html
    assert "/circuit-designer-ui/" not in editor_html
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "acceptance.spec"
        created = endpoints["create_document"](CreateDocumentRequest(path=str(path), document_id="api_acceptance"))
        assert created["source_revision_hash"]
        with pytest.raises(fastapi.HTTPException) as existing:
            endpoints["create_document"](CreateDocumentRequest(path=str(path), document_id="replacement"))
        assert existing.value.status_code == 422
        assert endpoints["editor"]().count('id="root"') == 1

        sample = build_test_package()
        document_id = created["document_id"]

        def local(reference: object) -> dict[str, object]:
            value = reference.model_dump(mode="json")
            value["document_id"] = document_id
            return value

        add_documents = [
            {"type": "upsert_document_xml", "kind": entry.kind, "xml": sample.files[entry.path].decode("utf-8")}
            for entry in sample.manifest.documents
        ]
        mappings = [
            {
                "type": "set_internal_design",
                "component": local(mapping.component),
                "internal_design": local(mapping.internal_design),
            }
            for mapping in sample.manifest.component_compositions
        ]
        entries = [{"type": "add_entry_design", "design": local(entry)} for entry in sample.manifest.entry_designs]
        response = endpoints["transaction"](
            TransactionRequest(expected_source_revision_hash=created["source_revision_hash"], operations=[*add_documents, *mappings, *entries])
        )
        snapshot = response["snapshot"]
        assert response["committed"]
        assert len(snapshot["components"]) == 3
        assert len(snapshot["entry_designs"]) == 2
        a2ui = endpoints["document_a2ui"]()
        assert a2ui["protocol_version"] == "v0.9"
        assert a2ui["catalog_id"] == "urn:spec2gds:a2ui:document:v1"
        assert a2ui["source_revision_hash"] == snapshot["source_revision_hash"]

        design_id = snapshot["entry_designs"][0]["ref"]["entity_id"]
        action = endpoints["action_execution"]("design", design_id, "reference.snapshot_summary", ActionInputRequest())
        assert action["status"] == "succeeded"
        artifact = endpoints["artifacts"]()["artifacts"][0]
        assert endpoints["artifact_lineage"](artifact["artifact_id"])["lineage"][0]["artifact_id"] == artifact["artifact_id"]

        proposal_execution = endpoints["action_execution"]("design", design_id, "reference.narrative_proposal", ActionInputRequest())
        assert proposal_execution["status"] == "succeeded"
        proposal = endpoints["proposals"]()["proposals"][0]
        preview = endpoints["preview_proposal"](
            proposal["proposal_id"], ProposalRequest(expected_source_revision_hash=snapshot["source_revision_hash"])
        )
        assert preview["valid"]
        accepted = endpoints["accept_proposal"](
            proposal["proposal_id"], ProposalRequest(expected_source_revision_hash=snapshot["source_revision_hash"])
        )
        assert accepted["committed"]
        assert accepted["snapshot"]["source_revision_hash"] != snapshot["source_revision_hash"]

        reopened = endpoints["open_document"](OpenDocumentRequest(path=str(path)))
        assert len(reopened["entry_designs"]) == 2
        assert len(endpoints["executions"]()["executions"]) == 2
        assert package_cli(["validate", "--container", str(path)]) == 0


def test_v1_api_rejects_stale_edits_and_legacy_odt_packages() -> None:
    endpoints = _endpoints()
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "v1.spec"
        write_test_package(path)
        opened = endpoints["open_document"](OpenDocumentRequest(path=str(path)))
        with pytest.raises(fastapi.HTTPException) as stale:
            endpoints["transaction"](
                TransactionRequest(expected_source_revision_hash="sha256:" + "0" * 64, operations=[])
            )
        assert stale.value.status_code == 409

        odt = Path(temporary) / "legacy.spec"
        with zipfile.ZipFile(odt, "w") as archive:
            archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
            archive.writestr("content.xml", "<office:document-content/>")
        with pytest.raises(fastapi.HTTPException) as rejected:
            endpoints["open_document"](OpenDocumentRequest(path=str(odt)))
        assert rejected.value.status_code == 422
        assert "legacy ODT" in str(rejected.value.detail)
        assert opened["source_revision_hash"]


def test_v1_api_applies_direct_editor_entity_metadata_and_port_operations(tmp_path: Path) -> None:
    endpoints = _endpoints()
    path = tmp_path / "direct-editor.spec"
    snapshot = endpoints["create_document"](CreateDocumentRequest(path=str(path), document_id="direct_editor"))

    created = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=snapshot["source_revision_hash"],
        operations=[
            {"type": "create_entity", "kind": "component", "name": "timer"},
            {"type": "create_entity", "kind": "design", "name": "timer_top"},
        ],
    ))["snapshot"]
    assert created["components"][0]["vlnv"] == "spec2gds.local:work:timer:1.0"
    assert created["designs"][0]["vlnv"] == "spec2gds.local:work:timer_top:1.0"
    assert created["entry_designs"][0]["ref"] == created["designs"][0]["ref"]
    component = created["components"][0]["ref"]

    edited = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=created["source_revision_hash"],
        operations=[
            {
                "type": "set_entity_metadata",
                "entity": component,
                "display_name": "Timer block",
                "short_description": "Counts cycles",
                "description": "A directly edited component.",
            },
            {
                "type": "add_component_port",
                "component": component,
                "port": {
                    "name": "count",
                    "direction": "out",
                    "left": "31",
                    "right": "0",
                    "description": "Current count",
                },
            },
        ],
    ))["snapshot"]
    a2ui = endpoints["document_a2ui"]()
    component_section = next(
        item["section"]
        for message in a2ui["messages"]
        for item in message.get("updateComponents", {}).get("components", [])
        if item.get("component") == "SpecSection"
        and item.get("section", {}).get("entity_ref") == component
    )
    assert next(item["value"] for item in component_section["facts"] if item["label"] == "Display name") == "Timer block"
    ports = next(
        item["table"]
        for message in a2ui["messages"]
        for item in message.get("updateComponents", {}).get("components", [])
        if item.get("component") == "SpecTable"
        and item.get("table", {}).get("kind") == "component_ports"
    )
    assert ports["rows"][0]["cells"]["left"]["value"] == "31"

    updated = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=edited["source_revision_hash"],
        operations=[{
            "type": "update_component_port",
            "component": component,
            "name": "count",
            "port": {
                "direction": "inout",
                "left": None,
                "right": None,
                "description": "Scalar count",
            },
        }],
    ))["snapshot"]
    assert updated["source_revision_hash"] != edited["source_revision_hash"]

    with pytest.raises(fastapi.HTTPException) as duplicate:
        endpoints["transaction"](TransactionRequest(
            expected_source_revision_hash=updated["source_revision_hash"],
            operations=[{"type": "create_entity", "kind": "component", "name": "timer"}],
        ))
    assert duplicate.value.status_code == 422
    assert "already exists" in str(duplicate.value.detail)

    with pytest.raises(fastapi.HTTPException) as rename:
        endpoints["transaction"](TransactionRequest(
            expected_source_revision_hash=updated["source_revision_hash"],
            operations=[{
                "type": "update_component_port",
                "component": component,
                "name": "count",
                "port": {
                    "name": "renamed",
                    "direction": "out",
                    "left": None,
                    "right": None,
                    "description": "Not allowed",
                },
            }],
        ))
    assert rename.value.status_code == 422
    assert "cannot be changed" in str(rename.value.detail)


def test_editor_launches_a_design_through_the_circuit_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import spec2gds.agent_spec.spec_format.v1_api as v1_api

    package_path = tmp_path / "launch.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    published: list[dict[str, object]] = []

    def publish(document: dict[str, object], **_: object) -> object:
        published.append(document)
        return type("Launch", (), {
            "document_id": document["document_id"],
            "editor_url": f"http://127.0.0.1:4180?document_id={document['document_id']}",
            "reused_session": False,
        })()

    monkeypatch.setattr(v1_api, "publish_circuit_document", publish)
    result = endpoints["launch_circuit"](CircuitLaunchRequest(
        entity_kind="design",
        entity_id="design_subsystem_internal",
    ))

    assert result["entity_id"] == "design_subsystem_internal"
    assert result["entity_kind"] == "design"
    assert result["editor_url"].startswith("http://127.0.0.1:4180?document_id=")
    assert result["omitted_bus_items"] == ["link0"]
    assert published[0]["protocol_version"] == "circuit-designer.v1"

    component_result = endpoints["launch_circuit"](CircuitLaunchRequest(
        entity_kind="component",
        entity_id="component_leaf",
    ))
    assert component_result["entity_kind"] == "component"
    assert component_result["entity_id"] == "component_leaf"
    assert published[1]["design"]["boundary_terminals"][0]["label"] == "irq_in"


def test_production_v1_api_has_no_heading_block_or_odt_route_dependency() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}
    assert not any("block" in path or "/runs" in path for path in paths)
    import spec2gds.agent_spec.api.__main__ as production_entry

    source = inspect.getsource(production_entry)
    assert "document_app" not in source
    assert "v1_api" in source


def test_server_and_editor_commands_forward_development_options(monkeypatch, capsys) -> None:
    """Keep the documented public commands wired to the shared app factory."""
    import uvicorn
    import spec2gds.agent_spec.api.__main__ as production_entry

    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: calls.append((app, options)))

    production_entry.server_main(["--host", "0.0.0.0", "--port", "8080", "--reload"])
    production_entry.editor_main(["--port", "8765"])

    assert calls == [
        (
            "spec2gds.agent_spec.spec_format.v1_api:create_app",
            {"factory": True, "host": "0.0.0.0", "port": 8080, "reload": True},
        ),
        (
            "spec2gds.agent_spec.spec_format.v1_api:create_app",
            {"factory": True, "host": "127.0.0.1", "port": 8765, "reload": False},
        ),
    ]
    output = capsys.readouterr().out
    assert "spec2gds server: http://0.0.0.0:8080" in output
    assert "spec2gds editor: http://127.0.0.1:8765/editor" in output


def test_spec_assistant_preview_apply_provenance_and_idempotence(tmp_path: Path) -> None:
    package_path = tmp_path / "assistant.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    target = next(
        item["ref"]
        for item in opened["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    proposal = SpecChangeProposal(
        proposal_id="proposal_component_description",
        document_id=opened["document_id"],
        target=target,
        base_source_revision_hash=opened["source_revision_hash"],
        title="Clarify leaf behavior",
        summary="Add a source description.",
        rationale="The component intent should be explicit.",
        assumptions=[],
        operations=[
            {
                "operation_id": "describe_leaf",
                "type": "set_entity_metadata",
                "entity": target,
                "description": "Produces a demo-link payload for its connected target.",
            }
        ],
    )

    context = endpoints["assistant_context"](
        opened["document_id"], "component", "component_leaf"
    )
    assert context["target"] == target
    assert any(
        item["entity_kind"] == "design"
        for item in context["read_only"]["dependency_refs"]
    ) is False
    subsystem_context = endpoints["assistant_context"](
        opened["document_id"], "component", "component_subsystem"
    )
    assert (
        subsystem_context["writable"]["owned_internal_design"]["ref"]["entity_id"]
        == "design_subsystem_internal"
    )
    before = endpoints["document_snapshot"]()["source_revision_hash"]
    preview = endpoints["assistant_proposal_preview"](proposal)
    assert preview["status"] == "valid"
    assert preview["candidate_source_revision_hash"] != before
    assert endpoints["document_snapshot"]()["source_revision_hash"] == before
    assert preview["diff"]

    applied = endpoints["assistant_proposal_apply"](proposal)
    assert applied["status"] == "applied"
    assert not applied["idempotent_replay"]
    assert applied["source_revision_hash"] != before
    replay = endpoints["assistant_proposal_apply"](proposal)
    assert replay["idempotent_replay"]
    conflicting_replay = proposal.model_copy(
        update={
            "operations": [
                {
                    "operation_id": "describe_leaf_differently",
                    "type": "set_entity_metadata",
                    "entity": target,
                    "description": "A different operation set under the same proposal ID.",
                }
            ]
        }
    )
    with pytest.raises(fastapi.HTTPException) as conflict:
        endpoints["assistant_proposal_apply"](conflicting_replay)
    assert conflict.value.status_code == 409

    changes = endpoints["assistant_changes"]()["assistant_changes"]
    assert len(changes) == 1
    assert changes[0]["proposal_id"] == proposal.proposal_id
    assert changes[0]["decision"] == "accepted"
    reopened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    assert reopened["source_revision_hash"] == applied["source_revision_hash"]
    assert endpoints["assistant_changes"]()["assistant_changes"] == changes


def test_spec_assistant_rejects_stale_and_cross_boundary_operations(tmp_path: Path) -> None:
    package_path = tmp_path / "assistant-boundary.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    component = next(
        item["ref"]
        for item in opened["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    bus = opened["bus_definitions"][0]["ref"]
    crossing = SpecChangeProposal(
        proposal_id="proposal_crossing",
        document_id=opened["document_id"],
        target=component,
        base_source_revision_hash=opened["source_revision_hash"],
        title="Cross boundary",
        summary="Invalid shared edit.",
        rationale="Test ownership.",
        operations=[
            {
                "operation_id": "edit_bus",
                "type": "update_bus_definition",
                "bus_definition": bus,
                "properties": {"broadcast": True},
            }
        ],
    )
    preview = endpoints["assistant_proposal_preview"](crossing)
    assert preview["status"] == "invalid"
    assert "ownership boundary" in preview["diagnostics"][0]

    forbidden_payloads = (
        {
            "operation_id": "rename_identity",
            "type": "set_entity_metadata",
            "entity": component,
            "vlnv": "example.org:changed:identity:2.0",
        },
        {
            "operation_id": "raw_xml",
            "type": "upsert_document_xml",
            "xml": "<component/>",
        },
        {
            "operation_id": "unknown_reference",
            "type": "set_entity_metadata",
            "entity": {
                **component,
                "entity_id": "component_missing",
            },
            "description": "invalid",
        },
    )
    for index, operation in enumerate(forbidden_payloads):
        forbidden = crossing.model_copy(
            update={
                "proposal_id": f"proposal_forbidden_{index}",
                "operations": [operation],
            }
        )
        assert endpoints["assistant_proposal_preview"](forbidden)["status"] == "invalid"

    stale = crossing.model_copy(
        update={
            "proposal_id": "proposal_stale",
            "base_source_revision_hash": "sha256:" + "0" * 64,
            "operations": [
                {
                    "operation_id": "describe",
                    "type": "set_entity_metadata",
                    "entity": component,
                    "description": "stale",
                }
            ],
        }
    )
    assert endpoints["assistant_proposal_preview"](stale)["status"] == "stale"
    with pytest.raises(fastapi.HTTPException) as rejected:
        endpoints["assistant_proposal_apply"](stale)
    assert rejected.value.status_code == 409


def test_document_projection_uses_semantic_row_ids() -> None:
    endpoints = _endpoints()
    with tempfile.TemporaryDirectory() as temporary:
        package_path = Path(temporary) / "projection.spec"
        write_test_package(package_path)
        endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
        batch = endpoints["document_a2ui"]()
    tables = [
        component["table"]
        for message in batch["messages"]
        for component in message.get("updateComponents", {}).get("components", [])
        if component.get("component") == "SpecTable"
    ]
    row_ids = [row["row_id"] for table in tables for row in table["rows"]]
    assert row_ids
    assert not any(row_id.endswith(("-0", "-1", "-2")) for row_id in row_ids)
