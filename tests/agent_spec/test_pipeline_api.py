import hashlib
import json
import pathlib
import tempfile
from unittest import mock

import spec2gds.agent_spec.api.app as agent_api_app
import spec2gds.agent_spec.api.document_app as document_api_app
import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.query as agent_query
import spec2gds.agent_spec.storage.repository as agent_repository


CONTENT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
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
      <text:p><text:a xlink:type="simple" xlink:href="spec://ipxact/dma.xml//*[local-name()='busInterface']">APB interface</text:a></text:p>
      <text:h text:outline-level="2">Register Interface</text:h>
      <text:p>Register behavior.</text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


IPXACT_XML: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2014">
  <ipxact:vendor>acme</ipxact:vendor>
  <ipxact:library>local</ipxact:library>
  <ipxact:name>dma</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:busInterfaces>
    <ipxact:busInterface>
      <ipxact:name>apb_slave</ipxact:name>
      <ipxact:busType vendor="amba.com" library="AMBA4" name="APB" version="r0p0"/>
      <ipxact:abstractionTypes>
        <ipxact:abstractionType vendor="amba.com" library="AMBA4" name="APB_rtl" version="r0p0"/>
      </ipxact:abstractionTypes>
      <ipxact:slave/>
      <ipxact:portMaps>
        <ipxact:portMap>
          <ipxact:logicalPort><ipxact:name>PADDR</ipxact:name></ipxact:logicalPort>
          <ipxact:physicalPort><ipxact:name>paddr_i</ipxact:name></ipxact:physicalPort>
        </ipxact:portMap>
      </ipxact:portMaps>
    </ipxact:busInterface>
  </ipxact:busInterfaces>
</ipxact:component>
"""


def _write_spec(path: pathlib.Path) -> None:
    """Create a small `.spec` document with one embedded IP-XACT payload."""
    container = archive.AgentSpecArchive()
    container.document.set_part("content.xml", CONTENT_XML)
    container.inject_file("spec_data/ipxact/dma.xml", IPXACT_XML, "application/xml+ipxact")
    container.save(str(path))


def _sha256(path: pathlib.Path) -> str:
    """Return a raw SHA-256 digest for read-only checks."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _endpoints(app: object) -> dict[str, object]:
    """Return FastAPI endpoint callables keyed by route name."""
    return {route.name: route.endpoint for route in app.routes if hasattr(route, "endpoint")}


def _open_pipeline(
    endpoints: dict[str, object],
    document_path: pathlib.Path,
    sidecar_path: pathlib.Path,
) -> dict[str, object]:
    """Open a document through the pipeline API."""
    return endpoints["pipeline_open_document"](
        agent_api_app.OpenDocumentRequest(
            path=str(document_path),
            sidecar_root=str(sidecar_path),
            user_identity="pipeline-user",
        )
    )


def _block_by_title(blocks_payload: dict[str, object], title: str) -> dict[str, object]:
    """Return a block summary by visible title."""
    for block in blocks_payload["data"]["blocks"]:
        if block["title"] == title:
            return block
    raise AssertionError(f"Missing block title: {title}")


def _artifact_for(block_id: str, version_id: str) -> agent_models.ArtifactRef:
    """Create valid artifact metadata for writeback tests."""
    return agent_models.ArtifactRef(
        artifact_id="artifact_pipeline_perf",
        artifact_kind="systemc",
        media_type="text/plain",
        summary="Pipeline generated performance model.",
        sha256="sha256:" + "a" * 64,
        external_uri="artifact-store://local/pipeline/perf.txt",
        producer="pipeline.systemc.perf",
        source_trace=agent_models.SourceTrace(
            block_id=block_id,
            version_id=version_id,
        ),
        role="systemc.perf.model",
        created_at=agent_repository.utc_now(),
    )


def test_pipeline_read_context_is_read_only_and_includes_section_data() -> None:
    """Test pipeline discovery/context endpoints do not mutate the `.spec` file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        document_path = tmp_path / "pipeline.spec"
        sidecar_path = tmp_path / "sidecar"
        _write_spec(document_path)
        before_hash = _sha256(document_path)

        app = agent_api_app.create_app()
        endpoints = _endpoints(app)
        open_payload = _open_pipeline(endpoints, document_path, sidecar_path)
        if open_payload["schema_version"] != agent_query.PIPELINE_SCHEMA_VERSION:
            raise AssertionError(f"Unexpected envelope: {open_payload}")

        blocks_payload = endpoints["pipeline_blocks"]()
        performance = _block_by_title(blocks_payload, "Performance Model")
        context_payload = endpoints["pipeline_block_context"](performance["block_id"])

        if context_payload["data"]["selected_version"]["version_id"] != performance["active_version_id"]:
            raise AssertionError(f"Context did not select active version: {context_payload}")
        if not context_payload["data"]["semantic_blocks"]:
            raise AssertionError("Expected section semantic blocks in pipeline context.")
        if not context_payload["data"]["links"]:
            raise AssertionError("Expected section spec links in pipeline context.")
        if _sha256(document_path) != before_hash:
            raise AssertionError("Pipeline read endpoints mutated the .spec file.")


def test_pipeline_raw_ipxact_endpoint_returns_embedded_xml() -> None:
    """Test raw IP-XACT access preserves protocol XML bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        document_path = tmp_path / "pipeline.spec"
        _write_spec(document_path)
        endpoints = _endpoints(agent_api_app.create_app())
        _open_pipeline(endpoints, document_path, tmp_path / "sidecar")

        response = endpoints["pipeline_raw_ipxact"]("spec_data/ipxact/dma.xml")
        if response.body != IPXACT_XML:
            raise AssertionError("Raw IP-XACT endpoint did not return exact embedded XML bytes.")
        if response.media_type != "application/xml+ipxact":
            raise AssertionError(f"Unexpected media type: {response.media_type}")


def test_pipeline_writeback_attaches_valid_artifact_and_updates_context() -> None:
    """Test explicit pipeline writeback persists artifact and trace metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        document_path = tmp_path / "pipeline.spec"
        sidecar_path = tmp_path / "sidecar"
        _write_spec(document_path)
        endpoints = _endpoints(agent_api_app.create_app())
        _open_pipeline(endpoints, document_path, sidecar_path)
        performance = _block_by_title(endpoints["pipeline_blocks"](), "Performance Model")

        run = endpoints["pipeline_start_run"](
            agent_api_app.PipelineRunRequest(
                pipeline_id="pipeline.systemc.perf",
                block_id=performance["block_id"],
            )
        )
        run_detail = endpoints["pipeline_run"](run["run_id"])
        selected = run_detail["data"]["input_snapshot"]["selected_versions"][0]
        artifact = _artifact_for(performance["block_id"], selected["version_id"])
        completed = endpoints["pipeline_submit_outputs"](
            run["run_id"],
            agent_api_app.PipelineOutputRequest(
                artifacts=[artifact],
                allowed_output_roles=["systemc.perf.model"],
            ),
        )

        if completed["status"] != "completed":
            raise AssertionError(f"Unexpected completed run: {completed}")
        if completed["produced_artifact_ids"] != [artifact.artifact_id]:
            raise AssertionError(f"Artifact was not accepted: {completed}")

        context = endpoints["pipeline_block_context"](performance["block_id"])
        artifact_ids = {item["artifact_id"] for item in context["data"]["artifacts"]}
        if artifact.artifact_id not in artifact_ids:
            raise AssertionError(f"Context did not expose attached artifact: {context}")

        reloaded = archive.AgentSpecArchive(str(document_path))
        if f"spec_data/agent-spec/artifacts/{artifact.artifact_id}.json" not in reloaded.custom_files:
            raise AssertionError("Artifact metadata was not embedded in the .spec document.")


def test_pipeline_writeback_rejects_malformed_artifact_without_attachment() -> None:
    """Test malformed pipeline artifacts produce review diagnostics."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        document_path = tmp_path / "pipeline.spec"
        sidecar_path = tmp_path / "sidecar"
        _write_spec(document_path)
        endpoints = _endpoints(agent_api_app.create_app())
        _open_pipeline(endpoints, document_path, sidecar_path)
        performance = _block_by_title(endpoints["pipeline_blocks"](), "Performance Model")

        run = endpoints["pipeline_start_run"](
            agent_api_app.PipelineRunRequest(
                pipeline_id="pipeline.systemc.perf",
                block_id=performance["block_id"],
            )
        )
        run_detail = endpoints["pipeline_run"](run["run_id"])
        selected = run_detail["data"]["input_snapshot"]["selected_versions"][0]
        bad_artifact = _artifact_for(performance["block_id"], selected["version_id"])
        bad_artifact.sha256 = "not-a-sha"
        completed = endpoints["pipeline_submit_outputs"](
            run["run_id"],
            agent_api_app.PipelineOutputRequest(
                artifacts=[bad_artifact],
                allowed_output_roles=["systemc.perf.model"],
            ),
        )

        if completed["produced_artifact_ids"]:
            raise AssertionError(f"Malformed artifact should not be attached: {completed}")
        if not completed["diagnostics"]:
            raise AssertionError("Malformed artifact should produce writeback diagnostics.")
        writebacks = endpoints["pipeline_runs"]()["data"]["writebacks"]
        if writebacks[-1]["status"] != "needs_human_feedback":
            raise AssertionError(f"Expected needs_human_feedback writeback: {writebacks}")


def test_editor_snapshot_route_uses_shared_query_service() -> None:
    """Test the UI read endpoint is backed by the shared query service."""
    with tempfile.TemporaryDirectory() as tmp:
        document_path = pathlib.Path(tmp) / "editor.spec"
        _write_spec(document_path)
        endpoints = _endpoints(document_api_app.create_app())
        original = agent_query.AgentSpecQueryService.editor_snapshot

        with mock.patch.object(
            agent_query.AgentSpecQueryService,
            "editor_snapshot",
            autospec=True,
            side_effect=lambda service: original(service),
        ) as wrapped:
            snapshot = endpoints["document_snapshot"](str(document_path))

        if not wrapped.called:
            raise AssertionError("Editor snapshot endpoint did not use the shared query service.")
        if not snapshot["document"]["blocks"]:
            raise AssertionError("Editor snapshot did not return semantic blocks.")
