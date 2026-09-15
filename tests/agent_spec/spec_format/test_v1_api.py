"""V1.4 API/editor acceptance checks for the current deterministic format."""

import inspect
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path

import fastapi
import pytest

from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal
from spec2gds.agent_spec.spec_format.cli import main as package_cli
from spec2gds.agent_spec.spec_format.models import EntityRef
from spec2gds.agent_spec.spec_format.testing import build_test_package, write_test_package
from spec2gds.agent_spec.spec_format.v1_api import (
    ActivityExecutionRequest,
    AssistantLaunchRequest,
    CircuitLaunchRequest,
    CircuitSourceSyncRequest,
    CreateDirectoryRequest,
    CreateDocumentRequest,
    OpenDocumentRequest,
    TransactionRequest,
    create_app,
)


def _endpoints() -> dict[str, object]:
    app = create_app()
    return {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def test_v1_api_create_edit_action_proposal_reopen_and_editor_acceptance() -> None:
    """Exercise the complete source-edit/action/review persistence workflow."""
    endpoints = _endpoints()
    assert "samples" not in endpoints
    services = endpoints["services"]()
    assert services["services"]["ai_assistant"]["ui_url"].endswith(":6013")
    assert services["services"]["circuit_designer"]["service_url"].endswith(
        "/api/circuit-designer/v1"
    )
    editor_html = endpoints["editor"]()
    assert "A2UI Document Editor" in editor_html
    assert "/editor-assets/assets/index.js" in editor_html
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
        assert a2ui["catalog_id"] == "urn:spec2gds:a2ui:document:v2"
        assert a2ui["source_revision_hash"] == snapshot["source_revision_hash"]

        design_id = snapshot["entry_designs"][0]["ref"]["entity_id"]
        assert endpoints["entity_actions"]("design", design_id)["actions"] == []
        catalog_ids = {item["activity_id"] for item in endpoints["activities"]()["activities"]}
        assert catalog_ids == {"rtl.generate", "systemc.generate_at_skeleton"}
        available = endpoints["entity_activities"]("design", design_id)["activities"]
        assert {item["definition"]["activity_id"] for item in available} == catalog_ids

        reopened = endpoints["open_document"](OpenDocumentRequest(path=str(path)))
        assert len(reopened["entry_designs"]) == 2
        assert endpoints["executions"]()["executions"] == []
        assert package_cli(["validate", "--container", str(path)]) == 0


def test_v1_api_rejects_stale_edits_and_unsupported_packages() -> None:
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

        odt = Path(temporary) / "unsupported.spec"
        with zipfile.ZipFile(odt, "w") as archive:
            archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
            archive.writestr("content.xml", "<office:document-content/>")
        with pytest.raises(fastapi.HTTPException) as rejected:
            endpoints["open_document"](OpenDocumentRequest(path=str(odt)))
        assert rejected.value.status_code == 422
        assert "Unsupported package mimetype" in str(rejected.value.detail)
        assert opened["source_revision_hash"]


def test_v1_api_browses_server_local_directories(tmp_path: Path) -> None:
    endpoints = _endpoints()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "not-a-directory.txt").write_text("ignored", encoding="utf-8")

    listing = endpoints["filesystem_directories"](str(tmp_path))

    assert listing["path"] == str(tmp_path.resolve())
    assert listing["parent"] == str(tmp_path.resolve().parent)
    assert listing["separator"] == os.sep
    assert listing["roots"]
    assert [item["name"] for item in listing["directories"]] == ["Alpha", "beta"]
    assert all(Path(item["path"]).is_absolute() for item in listing["directories"])

    created = endpoints["create_directory"](
        CreateDirectoryRequest(parent=str(tmp_path), name="New project")
    )
    assert created["path"] == str((tmp_path / "New project").resolve())
    assert (tmp_path / "New project").is_dir()

    with pytest.raises(fastapi.HTTPException) as invalid:
        endpoints["create_directory"](
            CreateDirectoryRequest(parent=str(tmp_path), name="CON.txt")
        )
    assert invalid.value.status_code == 422

    with pytest.raises(fastapi.HTTPException) as missing:
        endpoints["filesystem_directories"](str(tmp_path / "missing"))
    assert missing.value.status_code == 422


def test_v1_api_enqueues_and_persists_rtl_activity(tmp_path: Path, monkeypatch) -> None:
    """Run the product RTL Activity through the durable HTTP host contract."""
    config_path = Path(__file__).parents[3] / "config" / "services.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["public_host"] = "127.0.0.1"
    config["activities"]["workspace_root"] = str(tmp_path / "generated")
    local_config = tmp_path / "services.json"
    local_config.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("SPEC2GDS_SERVICE_CONFIG", str(local_config))

    app = create_app()
    endpoints = {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}
    path = tmp_path / "activity.spec"
    created = endpoints["create_document"](CreateDocumentRequest(
        path=str(path),
        document_id="activity_api",
        title="Activity API",
    ))
    created = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=created["source_revision_hash"],
        operations=[
            {"type": "create_entity", "kind": "component", "name": "leaf"},
            {"type": "create_entity", "kind": "design", "name": "top"},
        ],
    ))["snapshot"]
    created = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=created["source_revision_hash"],
        operations=[{
            "type": "upsert_instance",
            "design": created["designs"][0]["ref"],
            "instance": {"name": "dut", "component_vlnv": created["components"][0]["vlnv"]},
        }],
    ))["snapshot"]
    target = created["entry_designs"][0]["ref"]
    available = endpoints["entity_activities"]("design", target["entity_id"])["activities"]
    rtl = next(item for item in available if item["definition"]["activity_id"] == "rtl.generate")
    assert rtl["availability"]["available"]

    with pytest.raises(fastapi.HTTPException) as stale:
        endpoints["launch_activity"](
            "design",
            target["entity_id"],
            "rtl.generate",
            ActivityExecutionRequest(expected_source_revision_hash="sha256:" + "0" * 64),
        )
    assert stale.value.status_code == 409

    execution = endpoints["launch_activity"](
        "design",
        target["entity_id"],
        "rtl.generate",
        ActivityExecutionRequest(expected_source_revision_hash=created["source_revision_hash"]),
    )
    for _ in range(100):
        execution = endpoints["execution"](execution["execution_id"])
        if execution["status"] in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.02)
    assert execution["status"] == "succeeded", execution
    assert Path(execution["workspace_output_path"]).is_dir()
    assert execution["artifact_ids"]
    assert endpoints["artifacts"]()["artifacts"][0]["producer_action_id"] == "rtl.generate"

    endpoints["open_document"](OpenDocumentRequest(path=str(path)))
    persisted = endpoints["executions"]()["executions"]
    assert any(item["execution_id"] == execution["execution_id"] for item in persisted)
    app.state.activity_jobs.close()


def test_v1_api_reports_extension_load_diagnostics(tmp_path: Path, monkeypatch) -> None:
    config_path = Path(__file__).parents[3] / "config" / "services.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["activities"]["workspace_root"] = str(tmp_path / "generated")
    config["activities"]["extension_modules"] = ["missing_activity_plugin:register"]
    local_config = tmp_path / "services.json"
    local_config.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("SPEC2GDS_SERVICE_CONFIG", str(local_config))

    app = create_app()
    endpoints = {
        route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")
    }
    catalog = endpoints["activities"]()
    assert {item["activity_id"] for item in catalog["activities"]} == {
        "rtl.generate",
        "systemc.generate_at_skeleton",
    }
    assert len(catalog["diagnostics"]) == 1
    assert "missing_activity_plugin" in str(catalog["diagnostics"][0])
    app.state.activity_jobs.close()


def test_v1_api_applies_direct_editor_entity_metadata_and_port_operations(tmp_path: Path) -> None:
    endpoints = _endpoints()
    with pytest.raises(fastapi.HTTPException) as unnamed:
        endpoints["create_document"](CreateDocumentRequest(
            path=str(tmp_path / "unnamed.spec"),
            title="   ",
        ))
    assert unnamed.value.status_code == 422
    assert "name is required" in str(unnamed.value.detail)

    path = tmp_path / "direct-editor.spec"
    snapshot = endpoints["create_document"](CreateDocumentRequest(
        path=str(path),
        document_id="direct_editor",
        title="Direct Editor",
    ))
    assert snapshot["narrative"]["title"] == "Direct Editor"

    created = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=snapshot["source_revision_hash"],
        operations=[
            {"type": "set_document_title", "title": "Timer Specification"},
            {"type": "create_entity", "kind": "component", "name": "timer"},
            {"type": "create_entity", "kind": "design", "name": "timer_top"},
        ],
    ))["snapshot"]
    assert created["components"][0]["vlnv"] == "spec2gds.local:work:timer:1.0"
    assert created["document_id"] == "direct_editor"
    assert created["narrative"]["title"] == "Timer Specification"
    assert created["designs"][0]["vlnv"] == "spec2gds.local:work:timer_top:1.0"
    assert created["entry_designs"][0]["ref"] == created["designs"][0]["ref"]
    component = created["components"][0]["ref"]

    created = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=created["source_revision_hash"],
        operations=[{
            "type": "upsert_instance",
            "design": created["designs"][0]["ref"],
            "instance": {
                "name": "timer0",
                "component_vlnv": "spec2gds.local:work:timer:1.0",
            },
        }],
    ))["snapshot"]
    assert created["designs"][0]["instances"] == [{
        "name": "timer0",
        "component_vlnv": "spec2gds.local:work:timer:1.0",
    }]

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
                    "family": "wire",
                    "display_name": "Count",
                    "direction": "out",
                    "range": "31:0",
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
    document_root = next(
        item
        for message in a2ui["messages"]
        for item in message.get("updateComponents", {}).get("components", [])
        if item.get("component") == "SpecDocument"
    )
    assert document_root["title"] == "Timer Specification"
    ports = next(
        item["table"]
        for message in a2ui["messages"]
        for item in message.get("updateComponents", {}).get("components", [])
        if item.get("component") == "SpecTable"
        and item.get("table", {}).get("kind") == "component_ports"
    )
    assert ports["rows"][0]["cells"]["family"]["value"] == "wire"
    assert ports["rows"][0]["cells"]["range"]["value"] == "31:0"
    assert ports["rows"][0]["cells"]["display_name"]["value"] == "Count"
    assert ports["title"] == "Ports"

    updated = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=edited["source_revision_hash"],
        operations=[{
            "type": "update_component_port",
            "component": component,
            "name": "count",
            "port": {
                "family": "wire",
                "display_name": "Count",
                "direction": "inout",
                "range": None,
                "description": "Scalar count",
            },
        }],
    ))["snapshot"]
    assert updated["source_revision_hash"] != edited["source_revision_hash"]

    updated = endpoints["transaction"](TransactionRequest(
        expected_source_revision_hash=updated["source_revision_hash"],
        operations=[
            {
                "type": "add_component_port",
                "component": component,
                "port": {
                    "name": "service",
                    "family": "transactional",
                    "display_name": "Service",
                    "description": "Submits work.",
                    "initiative": "provides",
                    "kind": "custom",
                    "custom_kind": "timer_service",
                    "bus_width": "DATA_WIDTH",
                },
            },
            {
                "type": "add_component_port",
                "component": component,
                "port": {
                    "name": "response",
                    "family": "structured",
                    "display_name": "Response",
                    "description": "Packed response aggregate.",
                    "direction": "out",
                },
            },
        ],
    ))["snapshot"]
    assert {port["style"] for port in updated["components"][0]["ports"]} == {
        "wire", "transactional", "structured",
    }

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
                    "family": "wire",
                    "display_name": "",
                    "direction": "out",
                    "range": None,
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
    registrations: list[dict[str, object]] = []

    def publish(document: dict[str, object], **_: object) -> object:
        published.append(document)
        return type("Launch", (), {
            "document_id": document["document_id"],
            "editor_url": f"http://127.0.0.1:6012?document_id={document['document_id']}",
            "reused_session": False,
        })()

    monkeypatch.setattr(v1_api, "publish_circuit_document", publish)
    def register(*_: object, **kwargs: object) -> None:
        registrations.append(kwargs)

    monkeypatch.setattr(v1_api, "register_circuit_source_binding", register)
    result = endpoints["launch_circuit"](CircuitLaunchRequest(
        entity_kind="design",
        entity_id="design_subsystem_internal",
    ))

    assert result["entity_id"] == "design_subsystem_internal"
    assert result["entity_kind"] == "design"
    assert result["editor_url"].startswith("http://127.0.0.1:6012?document_id=")
    assert result["omitted_bus_items"] == ["link0"]
    assert result["omitted_ports"] == []
    assert published[0]["protocol_version"] == "circuit-designer.v1"
    assert result["source_binding"]["writable"] is True
    base_source_revision_hash = result["source_binding"]["base_source_revision_hash"]
    candidate = json.loads(json.dumps(published[0]))
    preview = endpoints["preview_circuit_source"](
        CircuitSourceSyncRequest(
            request_id="preview_layout",
            base_source_revision_hash=base_source_revision_hash,
            candidate_document=candidate,
        ),
        authorization=f"Bearer {registrations[0]['token']}",
    )
    assert preview["accepted"] is True
    committed = endpoints["commit_circuit_source"](
        CircuitSourceSyncRequest(
            request_id="commit_layout",
            base_source_revision_hash=base_source_revision_hash,
            candidate_document=candidate,
        ),
        authorization=f"Bearer {registrations[0]['token']}",
    )
    assert committed["accepted"] is True
    assert committed["source_revision_hash"] != base_source_revision_hash
    replayed = endpoints["commit_circuit_source"](
        CircuitSourceSyncRequest(
            request_id="commit_layout",
            base_source_revision_hash=base_source_revision_hash,
            candidate_document=candidate,
        ),
        authorization=f"Bearer {registrations[0]['token']}",
    )
    assert replayed == committed
    replayed_preview = endpoints["preview_circuit_source"](
        CircuitSourceSyncRequest(
            request_id="commit_layout",
            base_source_revision_hash=base_source_revision_hash,
            candidate_document=candidate,
        ),
        authorization=f"Bearer {registrations[0]['token']}",
    )
    assert replayed_preview == committed
    stale = endpoints["preview_circuit_source"](
        CircuitSourceSyncRequest(
            request_id="stale_layout",
            base_source_revision_hash=base_source_revision_hash,
            candidate_document=candidate,
        ),
        authorization=f"Bearer {registrations[0]['token']}",
    )
    assert stale["accepted"] is False
    assert stale["diagnostics"][0]["code"] == "source_revision_conflict"

    component_result = endpoints["launch_circuit"](CircuitLaunchRequest(
        entity_kind="component",
        entity_id="component_leaf",
    ))
    assert component_result["entity_kind"] == "component"
    assert component_result["entity_id"] == "component_leaf"
    assert published[1]["design"]["boundary_terminals"] == []
    assert published[1]["design"]["instances"][0]["label"] == "leaf"
    assert component_result["source_binding"]["writable"] is False
    assert published[1]["components"][0]["terminals"][0]["label"] == "irq_in"


def test_editor_launches_ai_assistant_with_configured_url_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_path = tmp_path / "assistant-launch.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    component = next(
        item["ref"]
        for item in opened["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    request = AssistantLaunchRequest(
        entity_kind="component",
        entity_id=component["entity_id"],
    )

    monkeypatch.setenv("AI_ASSISTANT_URL", "http://127.0.0.1:4400/")
    preferred = endpoints["launch_assistant"](request)
    assert preferred["assistant_url"].startswith("http://127.0.0.1:4400/launch/spec?")
    assert preferred["target"] == component

    document_launch = endpoints["launch_document_assistant"]()
    assert document_launch["assistant_url"].startswith(
        "http://127.0.0.1:4400/launch/spec-document?"
    )
    assert document_launch["document_id"] == opened["document_id"]
    assert document_launch["scope"] == "document"

    context = endpoints["assistant_document_context"](opened["document_id"])
    assert context["scope"] == "document"
    assert context["target"] is None
    assert context["rendered_context"]["snapshot_id"].startswith("sha256:")
    assert "SEMANTIC SPECIFICATION" in context["rendered_context"]["text"]


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
    monkeypatch.setenv("SPEC2GDS_PUBLIC_HOST", "design-host.test")

    production_entry.server_main(["--host", "0.0.0.0", "--port", "8080", "--reload"])
    production_entry.editor_main(["--port", "8765"])

    assert calls == [
        (
            "spec2gds.agent_spec.spec_format.v1_api:create_app",
                {"factory": True, "host": "0.0.0.0", "port": 8080, "reload": True, "access_log": False},
        ),
        (
            "spec2gds.agent_spec.spec_format.v1_api:create_app",
                {"factory": True, "host": "0.0.0.0", "port": 8765, "reload": False, "access_log": False},
        ),
    ]
    output = capsys.readouterr().out
    assert "spec2gds server: http://design-host.test:8080" in output
    assert "spec2gds editor: http://design-host.test:8765/editor" in output


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
            },
            {
                "operation_id": "add_leaf_service",
                "type": "upsert_component_port",
                "component": target,
                "port": {
                    "name": "assistant_service",
                    "family": "transactional",
                    "display_name": "Assistant service",
                    "description": "Exercises the shared port mutation helper.",
                    "initiative": "provides",
                    "kind": "tlm_port",
                    "custom_kind": None,
                    "bus_width": "32",
                },
            },
        ],
    )

    context = endpoints["assistant_context"](
        opened["document_id"], "component", "component_leaf"
    )
    assert context["target"] == target
    leaf_reference = next(
        item
        for item in context["available_references"]["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    assert {port["name"] for port in leaf_reference["ports"]} >= {"irq", "irq_in"}
    assert {interface["name"] for interface in leaf_reference["interfaces"]} == {"link"}
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
    leaf = next(item for item in reopened["components"] if item["ref"]["entity_id"] == "component_leaf")
    assistant_port = next(item for item in leaf["ports"] if item["name"] == "assistant_service")
    assert (assistant_port["style"], assistant_port["initiative"], assistant_port["bus_width"]) == (
        "transactional", "provides", "32",
    )
    assert endpoints["assistant_changes"]()["assistant_changes"] == changes


def test_document_assistant_creates_design_with_initial_instances(tmp_path: Path) -> None:
    package_path = tmp_path / "assistant-document.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    component = next(
        item for item in opened["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    proposal = SpecChangeProposal(
        proposal_id="proposal_replicated_design",
        document_id=opened["document_id"],
        scope="document",
        target=None,
        base_source_revision_hash=opened["source_revision_hash"],
        title="Create replicated design",
        summary="Add ten instances of the existing leaf component.",
        rationale="Exercise document-scoped creation as one atomic change.",
        assumptions=[],
        operations=[
            {
                "operation_id": "create_replicated_design",
                "type": "create_entity",
                "kind": "design",
                "name": "replicated_leaf",
                "entity_id": "design_replicated_leaf_fixed",
                "instances": [
                    {
                        "name": f"leaf_{index}",
                        "component_vlnv": component["vlnv"],
                    }
                    for index in range(1, 11)
                ],
            }
        ],
    )

    context = endpoints["assistant_document_context"](opened["document_id"])
    assert context["scope"] == "document"
    assert context["writable"]["document_operations"] == ["create_entity"]
    before = endpoints["document_snapshot"]()["source_revision_hash"]
    preview = endpoints["assistant_proposal_preview"](proposal)
    assert preview["status"] == "valid"
    assert preview["candidate_source_revision_hash"] != before
    assert endpoints["document_snapshot"]()["source_revision_hash"] == before
    assert preview["diff"]
    assert "replicated_leaf" in str(preview["candidate_sections"])

    applied = endpoints["assistant_proposal_apply"](proposal)
    assert applied["status"] == "applied"
    reopened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    design = next(
        item for item in reopened["designs"]
        if item["ref"]["entity_id"] == "design_replicated_leaf_fixed"
    )
    assert len(design["instances"]) == 10
    assert {item["component_vlnv"] for item in design["instances"]} == {
        component["vlnv"]
    }

    forbidden = proposal.model_copy(
        update={
            "proposal_id": "proposal_forbidden_document_edit",
            "base_source_revision_hash": reopened["source_revision_hash"],
            "operations": [
                {
                    "operation_id": "edit_existing",
                    "type": "set_entity_metadata",
                    "entity": component["ref"],
                    "description": "Not permitted from document scope.",
                }
            ],
        }
    )
    rejected = endpoints["assistant_proposal_preview"](forbidden)
    assert rejected["status"] == "invalid"
    assert "may only create top-level" in rejected["diagnostics"][0]
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
    design = opened["designs"][0]["ref"]
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

    mixed_connection = crossing.model_copy(
        update={
            "proposal_id": "proposal_mixed_connection",
            "target": EntityRef.model_validate(design),
            "operations": [
                {
                    "operation_id": "connect_wrong_endpoint_family",
                    "type": "upsert_connection",
                    "design": design,
                    "connection": {
                        "name": "invalid_link",
                        "kind": "ad_hoc",
                        "interface_endpoints": [
                            {"instance_name": "leaf0", "interface_name": "link"},
                            {"instance_name": "leaf1", "interface_name": "link"},
                        ],
                        "port_endpoints": [],
                        "external_ports": [],
                        "hierarchy_interfaces": [],
                    },
                }
            ],
        }
    )
    mixed_preview = endpoints["assistant_proposal_preview"](mixed_connection)
    assert mixed_preview["status"] == "invalid"
    assert "cannot contain interface endpoints" in mixed_preview["diagnostics"][0]

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


def test_spec_assistant_port_edits_match_direct_editor_boundaries(tmp_path: Path) -> None:
    package_path = tmp_path / "assistant-port-profile.spec"
    write_test_package(package_path)
    endpoints = _endpoints()
    opened = endpoints["open_document"](OpenDocumentRequest(path=str(package_path)))
    leaf = next(
        item["ref"]
        for item in opened["components"]
        if item["ref"]["entity_id"] == "component_leaf"
    )
    composite = next(
        item["ref"]
        for item in opened["components"]
        if item["ref"]["entity_id"] == "component_subsystem"
    )

    def proposal(
        proposal_id: str,
        target: dict[str, object],
        port: dict[str, object],
    ) -> SpecChangeProposal:
        return SpecChangeProposal(
            proposal_id=proposal_id,
            document_id=opened["document_id"],
            target=target,
            base_source_revision_hash=opened["source_revision_hash"],
            title="Port proposal",
            summary="Exercise the shared port profile.",
            rationale="Assistant and direct edits must enforce the same rules.",
            operations=[{
                "operation_id": f"{proposal_id}_operation",
                "type": "upsert_component_port",
                "component": target,
                "port": port,
            }],
        )

    structured = endpoints["assistant_proposal_preview"](
        proposal(
            "proposal_structured_port",
            leaf,
            {
                "name": "response",
                "family": "structured",
                "display_name": "Response",
                "description": "Packed response aggregate.",
                "direction": "in",
            },
        )
    )
    assert structured["status"] == "valid"

    family_change = endpoints["assistant_proposal_preview"](
        proposal(
            "proposal_family_change",
            leaf,
            {
                "name": "irq",
                "family": "structured",
                "display_name": None,
                "description": None,
                "direction": "out",
            },
        )
    )
    assert family_change["status"] == "invalid"
    assert "family cannot be changed" in family_change["diagnostics"][0]

    composite_edit = endpoints["assistant_proposal_preview"](
        proposal(
            "proposal_composite_port",
            composite,
            {
                "name": "boundary",
                "family": "wire",
                "display_name": None,
                "description": None,
                "direction": "inout",
                "range": None,
            },
        )
    )
    assert composite_edit["status"] == "invalid"
    assert "source-bound Circuit Designer boundary workflow" in composite_edit["diagnostics"][0]


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
