import hashlib
import pathlib
import tempfile

import spec2gds.agent_spec.api.app as action_api
import spec2gds.agent_spec.models as models
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.storage.repository as repository


CONTENT = b'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.3"><office:body><office:text><text:h text:outline-level="1">DMA Engine</text:h><text:p>DMA behavior.</text:p><text:h text:outline-level="2">Performance Model</text:h><text:p>Model behavior.</text:p></office:text></office:body></office:document-content>'''


def _write(path: pathlib.Path) -> None:
    document = archive.AgentSpecArchive()
    document.document.set_part("content.xml", CONTENT)
    document.save(str(path))


def _endpoints(app: object) -> dict[str, object]:
    return {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def _artifact(block_id: str, version_id: str) -> models.ArtifactRef:
    return models.ArtifactRef(
        artifact_id="artifact_perf",
        artifact_kind="systemc",
        media_type="text/plain",
        summary="Generated model",
        sha256="sha256:" + "a" * 64,
        external_uri="artifact-store://local/model.txt",
        producer="test-executor",
        source_trace=models.SourceTrace(block_id=block_id, version_id=version_id),
        role="systemc.perf.model",
        created_at=repository.utc_now(),
    )


def test_action_launch_dispatch_and_executor_completion() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "action.spec"
        _write(path)
        endpoints = _endpoints(action_api.create_app())
        opened = endpoints["open_document"](action_api.OpenDocumentRequest(path=str(path)))
        block_id = opened["blocks"][0]["block_id"]
        actions = endpoints["actions"]()["actions"]
        assert {action["action_id"] for action in actions} == {"systemc.perf", "systemc.bitaccurate", "agent_spec.delayed_report"}
        checked = endpoints["preconditions"](block_id, "systemc.perf", action_api.ActionInputsRequest(inputs={"output_name": "perf.txt"}))
        assert checked["can_execute"]
        launch = endpoints["launch"](block_id, "systemc.perf", action_api.ActionInputsRequest(inputs={"output_name": "perf.txt"}))
        assert launch["run"]["status"] == "running"
        assert launch["completion_url"].endswith("/completion")
        selected = launch["snapshot"]["selected_versions"][0]
        completed = endpoints["completion"](
            launch["run"]["run_id"],
            action_api.ExecutorCompletionRequest(outcome="succeeded", artifacts=[_artifact(block_id, selected["version_id"])], report={"summary": "Complete", "details": "OK"}),
        )
        assert completed["status"] == "completed"
        detail = endpoints["run"](launch["run"]["run_id"])
        assert detail["data"]["report"]["review_required"] is False
        assert detail["data"]["a2ui_messages"]


def test_invalid_report_completes_with_review_required_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "action.spec"
        _write(path)
        endpoints = _endpoints(action_api.create_app())
        opened = endpoints["open_document"](action_api.OpenDocumentRequest(path=str(path)))
        block_id = opened["blocks"][0]["block_id"]
        launch = endpoints["launch"](block_id, "systemc.perf", action_api.ActionInputsRequest(inputs={}))
        completed = endpoints["completion"](launch["run"]["run_id"], action_api.ExecutorCompletionRequest(outcome="succeeded", report={}))
        assert completed["status"] == "completed"
        detail = endpoints["run"](launch["run"]["run_id"])
        assert detail["data"]["report"]["review_required"] is True


def test_runs_survive_document_switch_and_aggregate_globally() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        first_path = pathlib.Path(tmp) / "first.spec"
        second_path = pathlib.Path(tmp) / "second.spec"
        _write(first_path)
        _write(second_path)
        endpoints = _endpoints(action_api.create_app())
        first = endpoints["open_document"](action_api.OpenDocumentRequest(path=str(first_path)))
        block_id = first["blocks"][0]["block_id"]
        launch = endpoints["launch"](block_id, "systemc.perf", action_api.ActionInputsRequest(inputs={}))
        selected = launch["snapshot"]["selected_versions"][0]

        endpoints["open_document"](action_api.OpenDocumentRequest(path=str(second_path)))
        completed = endpoints["completion"](
            launch["run"]["run_id"],
            action_api.ExecutorCompletionRequest(
                outcome="succeeded",
                artifacts=[_artifact(block_id, selected["version_id"])],
                report={"summary": "Complete", "details": "OK"},
            ),
        )
        assert completed["status"] == "completed"
        all_runs = endpoints["runs"]()["runs"]
        assert any(item["run"]["run_id"] == launch["run"]["run_id"] for item in all_runs)


def test_legacy_labels_are_removed_on_save() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "legacy.spec"
        _write(path)
        container = archive.AgentSpecArchive(str(path))
        container.inject_file("spec_data/agent-spec/graph.json", b'{"version": 1, "blocks": {}, "active_versions": {}, "artifact_refs": {}, "attachments": {}, "tags": ["legacy"]}', "application/json")
        container.save(str(path))
        repo = repository.AgentSpecRepository(str(path))
        repo.project_graph()
        repo.save()
        reloaded = archive.AgentSpecArchive(str(path))
        graph = reloaded.extract_file("spec_data/agent-spec/graph.json")
        assert b'"tags"' not in graph
