import json
import pathlib
import tempfile

import spec2gds.agent_spec.actions as agent_actions
import spec2gds.agent_spec.api.app as agent_api_app
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.repository as agent_repository
import spec2gds.agent_spec.runner as agent_runner
import spec2gds.spec.odt_container.container as odt_container


SYNTHETIC_CONTENT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">DMA Engine</text:h>
      <text:p>Top level DMA behavior.</text:p>
      <text:h text:outline-level="2">Performance Model</text:h>
      <text:p>Performance assumptions.</text:p>
      <text:h text:outline-level="2">Bit Accurate Model</text:h>
      <text:p>Bit accurate assumptions.</text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


UPDATED_CONTENT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">DMA Engine</text:h>
      <text:p>Top level DMA behavior updated.</text:p>
      <text:h text:outline-level="2">Performance Model</text:h>
      <text:p>Performance assumptions.</text:p>
      <text:h text:outline-level="2">Bit Accurate Model</text:h>
      <text:p>Bit accurate assumptions.</text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


def _write_synthetic_odt(path: pathlib.Path) -> None:
    container = odt_container.HybridODTContainer()
    container.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    container.save(str(path))


def _repository(tmpdir: pathlib.Path) -> agent_repository.AgentSpecRepository:
    document_path = tmpdir / "agent_spec.odt"
    sidecar_path = tmpdir / "sidecar"
    _write_synthetic_odt(document_path)
    return agent_repository.AgentSpecRepository(
        str(document_path),
        sidecar_root=str(sidecar_path),
        user_identity="test-user",
    )


def _block_by_title(
    repo: agent_repository.AgentSpecRepository,
    title: str,
) -> agent_models.BlockRecord:
    repo.project_graph()
    for block in repo.graph.blocks.values():
        if block.title == title:
            return block
    raise AssertionError(f"Missing block with title {title}")


def _run_json(
    repo: agent_repository.AgentSpecRepository,
    run_id: str,
    file_name: str,
) -> dict[str, object]:
    path = f"spec_data/agent-spec/runs/{run_id}/{file_name}"
    if path not in repo.container.custom_files:
        raise AssertionError(f"Missing run metadata path: {path}")
    return json.loads(repo.container.extract_file(path).decode("utf-8"))


def test_project_headings_to_blocks_and_tags_drive_actions() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repository(pathlib.Path(tmp))
        registry = agent_actions.create_default_registry()
        dma_block = _block_by_title(repo, "DMA Engine")

        if len(repo.graph.blocks) != 3:
            raise AssertionError(f"Expected 3 heading blocks, got {len(repo.graph.blocks)}")

        repo.set_block_tags(dma_block.block_id, ["ip", "systemc-perf", "systemc-bitaccurate"])
        runner = agent_runner.AgentSpecRunner(repo, registry)
        action_ids = {action.action_id for action in runner.available_actions(dma_block.block_id)}

        if "systemc.perf.pseudo" not in action_ids:
            raise AssertionError(f"Missing performance action from {action_ids}")
        if "systemc.bitaccurate.pseudo" not in action_ids:
            raise AssertionError(f"Missing bit-accurate action from {action_ids}")


def test_yaml_config_disables_action_per_deployment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_path = pathlib.Path(tmp) / "agent-spec.yaml"
        config_path.write_text(
            "actions:\n"
            "  systemc.bitaccurate.pseudo:\n"
            "    enabled: false\n",
            encoding="utf-8",
        )
        registry = agent_actions.create_default_registry(str(config_path))
        action_ids = {action.action_id for action in registry.list_actions()}

        if "systemc.perf.pseudo" not in action_ids:
            raise AssertionError("Expected enabled performance action.")
        if "systemc.bitaccurate.pseudo" in action_ids:
            raise AssertionError("Expected config-disabled bit-accurate action to be hidden.")


def test_pseudo_pipeline_auto_attaches_artifact_and_persists_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repository(pathlib.Path(tmp))
        block = _block_by_title(repo, "Performance Model")
        repo.set_block_tags(block.block_id, ["systemc-perf"])
        runner = agent_runner.AgentSpecRunner(repo, agent_actions.create_default_registry())

        run = runner.trigger_action(
            "systemc.perf.pseudo",
            block.block_id,
            {"delay_seconds": 0, "output_name": "perf.txt"},
        )

        if run.status != "completed":
            raise AssertionError(f"Unexpected run status: {run}")
        if len(run.produced_artifact_ids) != 1:
            raise AssertionError(f"Expected one produced artifact, got {run.produced_artifact_ids}")
        if len(repo.graph.attachments[block.block_id]) != 1:
            raise AssertionError("Expected one attachment on the source block.")

        artifact_id = run.produced_artifact_ids[0]
        artifact = repo.graph.artifact_refs[artifact_id]
        if artifact.source_trace.block_id != block.block_id:
            raise AssertionError("Artifact trace does not point at source block.")
        if not artifact.external_uri.startswith("file://"):
            raise AssertionError(f"Expected sidecar file URI, got {artifact.external_uri}")
        if f"spec_data/agent-spec/artifacts/{artifact_id}.json" not in repo.container.custom_files:
            raise AssertionError("Artifact metadata was not embedded in ODT.")

        writeback_paths = [
            path
            for path in repo.container.custom_files
            if path.startswith("spec_data/agent-spec/writebacks/")
        ]
        if len(writeback_paths) != 1:
            raise AssertionError(f"Expected one writeback record, got {writeback_paths}")
        writeback = json.loads(repo.container.extract_file(writeback_paths[0]).decode("utf-8"))
        if writeback["status"] != "auto_applied":
            raise AssertionError(f"Expected auto_applied writeback, got {writeback}")


def test_rerun_appends_attachment_without_overwrite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repository(pathlib.Path(tmp))
        block = _block_by_title(repo, "Performance Model")
        repo.set_block_tags(block.block_id, ["systemc-perf"])
        runner = agent_runner.AgentSpecRunner(repo, agent_actions.create_default_registry())

        first = runner.trigger_action("systemc.perf.pseudo", block.block_id, {"delay_seconds": 0})
        second = runner.trigger_action("systemc.perf.pseudo", block.block_id, {"delay_seconds": 0})

        attachments = repo.graph.attachments[block.block_id]
        if len(attachments) != 2:
            raise AssertionError(f"Expected two attachments, got {attachments}")
        if first.produced_artifact_ids[0] == second.produced_artifact_ids[0]:
            raise AssertionError("Rerun reused an artifact id instead of appending a new artifact.")


def test_malformed_artifact_gets_feedback_status_without_attachment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repository(pathlib.Path(tmp))
        block = _block_by_title(repo, "Performance Model")
        repo.set_block_tags(block.block_id, ["systemc-perf"])
        registry = agent_actions.create_default_registry()

        def bad_handler(context: agent_models.ActionRunContext) -> agent_models.ActionResult:
            selected = context.snapshot.selected_versions[0]
            artifact = agent_models.ArtifactRef(
                artifact_id="bad_artifact",
                artifact_kind="systemc",
                media_type="text/plain",
                summary="bad",
                sha256="not-a-sha",
                external_uri="ftp://invalid/location",
                producer=context.action.action_id,
                source_trace=agent_models.SourceTrace(
                    block_id=selected.block_id,
                    version_id=selected.version_id,
                ),
                role=context.action.action_id,
                created_at=agent_repository.utc_now(),
            )
            return agent_models.ActionResult(artifacts=[artifact])

        registry.register(
            agent_models.ActionSpec(
                action_id="systemc.bad",
                title="Bad SystemC",
                summary="Returns malformed artifact metadata.",
                version="0.1.0",
                provider="test",
                required_tags=["systemc-perf"],
                output_roles=["systemc.bad"],
            ),
            bad_handler,
        )
        runner = agent_runner.AgentSpecRunner(repo, registry)
        run = runner.trigger_action("systemc.bad", block.block_id, {"delay_seconds": 0})

        if run.status != "completed":
            raise AssertionError(f"Malformed metadata should not crash the run: {run}")
        if run.produced_artifact_ids:
            raise AssertionError("Malformed artifact should not be attached.")
        if repo.graph.attachments.get(block.block_id):
            raise AssertionError("Malformed artifact created an attachment.")

        writeback_paths = [
            path
            for path in repo.container.custom_files
            if path.startswith("spec_data/agent-spec/writebacks/")
        ]
        writeback = json.loads(repo.container.extract_file(writeback_paths[0]).decode("utf-8"))
        if writeback["status"] != "needs_human_feedback":
            raise AssertionError(f"Expected needs_human_feedback, got {writeback}")


def test_input_snapshot_is_immutable_after_active_version_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _repository(pathlib.Path(tmp))
        block = _block_by_title(repo, "DMA Engine")
        repo.set_block_tags(block.block_id, ["systemc-perf"])
        runner = agent_runner.AgentSpecRunner(repo, agent_actions.create_default_registry())

        first_version = repo.active_version(block.block_id).version_id
        first_run = runner.trigger_action("systemc.perf.pseudo", block.block_id, {"delay_seconds": 0})

        repo.container.document.set_part("content.xml", UPDATED_CONTENT_XML)
        repo.project_graph()
        latest_version = repo.graph.blocks[block.block_id].versions[-1].version_id
        if latest_version == first_version:
            raise AssertionError("Expected content edit to create a new block version.")
        repo.set_active_version(block.block_id, latest_version)
        second_run = runner.trigger_action("systemc.perf.pseudo", block.block_id, {"delay_seconds": 0})

        first_snapshot = _run_json(repo, first_run.run_id, "input_snapshot.json")
        second_snapshot = _run_json(repo, second_run.run_id, "input_snapshot.json")
        first_snapshot_version = first_snapshot["selected_versions"][0]["version_id"]
        second_snapshot_version = second_snapshot["selected_versions"][0]["version_id"]

        if first_snapshot_version != first_version:
            raise AssertionError("First run snapshot changed after active version update.")
        if second_snapshot_version != latest_version:
            raise AssertionError("Second run did not capture the latest selected version.")


def test_server_owned_write_guard_rejects_out_of_band_file_change() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        repo = _repository(tmp_path)
        document_path = tmp_path / "agent_spec.odt"
        block = _block_by_title(repo, "Performance Model")
        repo.set_block_tags(block.block_id, ["systemc-perf"])

        document_path.write_bytes(document_path.read_bytes() + b"external-change")
        try:
            repo.save()
        except RuntimeError:
            return
        raise AssertionError("Expected server-owned write guard to reject external ODT mutation.")


def test_local_api_opens_document_discovers_action_and_runs_pseudo_pipeline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        document_path = tmp_path / "agent_spec.odt"
        sidecar_path = tmp_path / "sidecar"
        _write_synthetic_odt(document_path)
        app = agent_api_app.create_app()
        endpoint_by_name = {
            route.name: route.endpoint
            for route in app.routes
            if hasattr(route, "endpoint")
        }

        open_data = endpoint_by_name["open_document"](
            agent_api_app.OpenDocumentRequest(
                path=str(document_path),
                sidecar_root=str(sidecar_path),
                user_identity="api-user",
            )
        )
        blocks = open_data["blocks"]
        performance_block = next(block for block in blocks if block["title"] == "Performance Model")

        endpoint_by_name["set_tags"](
            performance_block["block_id"],
            agent_api_app.TagUpdateRequest(tags=["systemc-perf"]),
        )

        actions_data = endpoint_by_name["block_actions"](performance_block["block_id"])
        action_ids = {action["action_id"] for action in actions_data["actions"]}
        if "systemc.perf.pseudo" not in action_ids:
            raise AssertionError(f"Missing pseudo action from API result: {action_ids}")

        run_data = endpoint_by_name["run_action"](
            performance_block["block_id"],
            "systemc.perf.pseudo",
            agent_api_app.RunActionRequest(parameters={"delay_seconds": 0, "output_name": "api-perf.txt"}),
        )
        if run_data["status"] != "completed" or len(run_data["produced_artifact_ids"]) != 1:
            raise AssertionError(f"Unexpected run response: {run_data}")

        reloaded = agent_repository.AgentSpecRepository(str(document_path), sidecar_root=str(sidecar_path))
        reloaded.project_graph()
        artifact_id = run_data["produced_artifact_ids"][0]
        if artifact_id not in reloaded.graph.artifact_refs:
            raise AssertionError("API run did not persist artifact metadata into ODT.")

        events_data = endpoint_by_name["events"]()
        event_types = [event["event_type"] for event in events_data["events"]]
        if "run.writeback.applied" not in event_types:
            raise AssertionError(f"Missing writeback-applied event: {event_types}")

        state_data = endpoint_by_name["blocks"]()
        attachments = state_data["attachments"].get(performance_block["block_id"], [])
        if not attachments:
            raise AssertionError(f"API state did not expose artifact attachments: {state_data}")
