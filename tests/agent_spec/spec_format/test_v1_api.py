"""V1.4 API/editor acceptance checks without the legacy ODT production path."""

import inspect
import tempfile
import zipfile
from pathlib import Path

import fastapi
import pytest

from spec2gds.agent_spec.spec_format.samples import build_v1_sample, write_v1_sample
from spec2gds.agent_spec.spec_format.cli import main as package_cli
from spec2gds.agent_spec.spec_format.v1_api import (
    ActionInputRequest,
    CreateDocumentRequest,
    OpenDocumentRequest,
    ProposalRequest,
    TransactionRequest,
    create_app,
)


def _endpoints() -> dict[str, object]:
    app = create_app()
    return {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def test_v1_api_create_edit_action_proposal_reopen_and_editor_acceptance() -> None:
    """Exercise the complete source-edit/action/review persistence workflow."""
    endpoints = _endpoints()
    samples = endpoints["samples"]()["samples"]
    assert len(samples) == 11
    assert samples[0]["name"] == "V1 Demo"
    assert all(Path(sample["path"]).is_file() for sample in samples)
    assert {sample["name"] for sample in samples[1:]} == {
        "Hardware · Apb Gpio",
        "Hardware · Apb I2C Slave",
        "Hardware · Apb Timer",
        "Hardware · Cv Hpdcache Csrs",
        "Hardware · Cv Hpdcache Interface",
        "Hardware · Cvfpu Readme",
        "SystemC · Fifo Backpressure Hw Spec",
        "SystemC · Pipelined Alu Hw Spec",
        "SystemC · Simple Pipeline Hw Spec",
        "SystemC · Switch Arbitration Hw Spec",
    }
    editor_html = endpoints["editor"]()
    assert "A2UI Document Editor" in editor_html
    assert "/editor-assets/assets/index-" in editor_html
    assert "/circuit-designer-ui/" not in editor_html
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "acceptance.spec"
        created = endpoints["create_document"](CreateDocumentRequest(path=str(path), document_id="api_acceptance"))
        assert created["source_revision_hash"]
        assert endpoints["editor"]().count('id="root"') == 1

        sample = build_v1_sample()
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
        write_v1_sample(path)
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
