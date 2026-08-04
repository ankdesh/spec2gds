from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from spec2gds_assistant.agents.circuit_editor import CircuitEditingAgent
from spec2gds_assistant.agents.context import CircuitContextProcessor, SpecContextProcessor
from spec2gds_assistant.agents.spec_editor import SpecEditingAgent
from spec2gds_assistant.a2a_agent import _explicit_spec_proposal_intent
from spec2gds_assistant.config import Settings
from spec2gds_assistant.models import (
    CircuitAgentRequest,
    CircuitProposalDraft,
    SpecAgentRequest,
    SpecProposalDraft,
)


class FakeResponses:
    def __init__(self, draft: CircuitProposalDraft) -> None:
        self.draft = draft
        self.request: dict[str, Any] | None = None

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.draft)


class FakeOpenAI:
    def __init__(self, draft: CircuitProposalDraft) -> None:
        self.responses = FakeResponses(draft)


class FakeSpecResponses:
    def __init__(self, draft: SpecProposalDraft) -> None:
        self.draft = draft
        self.request: dict[str, Any] | None = None

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.draft)


class FakeSpecOpenAI:
    def __init__(self, draft: SpecProposalDraft) -> None:
        self.responses = FakeSpecResponses(draft)


def settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=4200,
        database_path=tmp_path / "assistant.db",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        web_dist_path=tmp_path / "missing",
        circuit_request_timeout_seconds=5,
    )


def test_environment_defaults_are_local_and_use_gpt_4o_mini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ASSISTANT_DATABASE_PATH",
        "ASSISTANT_WEB_DIST_PATH",
        "SPEC2GDS_SERVICE_CONFIG",
        "AI_ASSISTANT_URL",
        "EXTERNAL_ASSISTANT_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    configured = Settings.from_env()
    assert configured.openai_model == "gpt-4o-mini"
    assert configured.database_path.name == "assistant.db"
    assert configured.database_path.parent.name == "data"
    assert configured.web_dist_path.name == "dist"
    assert configured.web_dist_path.parent.name == "web"
    assert configured.spec_editor_service_url == "http://127.0.0.1:8000"
    assert configured.circuit_designer_ui_url == "http://127.0.0.1:4180"


def test_context_processor_describes_semantic_circuit(circuit_snapshot: dict[str, Any]) -> None:
    processed = CircuitContextProcessor().process(
        CircuitAgentRequest(
            user_request="Describe the circuit.",
            snapshot=circuit_snapshot,
            svg=(
                '<svg viewBox="0 0 100 100"><g data-instance-id="producer_0"/>'
                '<path data-net-id="data_net"/></svg>'
            ),
        )
    )
    assert processed.document_id == "fixture_simple"
    assert processed.revision == "1"
    assert "Available component definitions" in processed.text
    assert "producer_0: component=producer" in processed.text
    assert "terminal data: direction=output" in processed.text
    assert 'instance ids=["producer_0"]' in processed.text
    assert 'net ids=["data_net"]' in processed.text


async def test_agent_uses_structured_output_and_returns_review_artifact(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    draft = CircuitProposalDraft.model_validate(
        {
            "supported": True,
            "title": "Add a consumer",
            "summary": "Add one consumer to the circuit.",
            "rationale": "The request asks for another sink.",
            "assumptions": ["The consumer component is the intended sink."],
            "unsupported_reason": None,
            "operations": [
                {
                    "operation_id": "add_consumer_1",
                    "type": "add_instance",
                    "instance": {
                        "id": "consumer_1",
                        "label": "Consumer 1",
                        "component_id": "consumer",
                        "parameter_values": {},
                    },
                }
            ],
        }
    )
    client = FakeOpenAI(draft)
    agent = CircuitEditingAgent(settings(tmp_path), client=client)  # type: ignore[arg-type]
    artifact = await agent.propose(
        CircuitAgentRequest(
            user_request="Add another consumer.",
            snapshot=circuit_snapshot,
        )
    )
    assert artifact.proposal_id.startswith("proposal_")
    assert artifact.document_id == "fixture_simple"
    assert artifact.batch.expected_revision == "1"
    assert client.responses.request is not None
    assert client.responses.request["model"] == "gpt-4o-mini"
    assert client.responses.request["text_format"] is CircuitProposalDraft
    assert client.responses.request["store"] is False


async def test_agent_requires_an_api_key_without_an_injected_client(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    agent = CircuitEditingAgent(settings(tmp_path))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await agent.propose(
            CircuitAgentRequest(user_request="Add a consumer.", snapshot=circuit_snapshot)
        )


def spec_context() -> dict[str, Any]:
    target = {
        "document_id": "demo",
        "entity_kind": "component",
        "entity_id": "component-demo",
    }
    return {
        "document_id": "demo",
        "source_revision_hash": "sha256:base",
        "target": target,
        "writable": {
            "entity": {
                "name": "demo_component",
                "description": "Current text",
                "ports": [{
                    "name": "service",
                    "style": "transactional",
                    "display_name": "Service",
                    "description": "Submits work.",
                    "initiative": "provides",
                    "kind": "custom",
                    "custom_kind": "demo_service",
                    "bus_width": "DATA_WIDTH",
                }],
            },
            "entity_refs": [target],
            "sections": [{"section_id": "component-component-demo"}],
            "linked_narrative": [{"block_id": "owned-note", "text": "Owned"}],
        },
        "read_only": {
            "dependency_refs": [
                {
                    "document_id": "demo",
                    "entity_kind": "bus_definition",
                    "entity_id": "bus-apb",
                }
            ],
            "usages": [{"entity_kind": "design", "entity_id": "soc"}],
            "shared_narrative": [{"block_id": "shared-note", "text": "Shared"}],
            "omitted_item_counts": {"usages": 3},
        },
        "available_references": {"components": [{"entity_id": "component-demo"}]},
        "diagnostics": [],
    }


def test_spec_context_processor_labels_write_and_read_boundaries() -> None:
    processed = SpecContextProcessor().process(
        SpecAgentRequest(
            user_request="Explore a clearer description.",
            context=spec_context(),
            conversation_summary="Earlier we discussed latency.",
            recent_messages=[{"role": "user", "content": "Keep the APB interface."}],
        )
    )
    assert processed.document_id == "demo"
    assert processed.revision == "sha256:base"
    assert "WRITABLE BOUNDARY" in processed.text
    assert "READ-ONLY SURROUNDING CONTEXT" in processed.text
    assert "shared-note" in processed.text
    assert '"usages": 3' in processed.text
    assert '"custom_kind": "demo_service"' in processed.text
    assert "OLDER CONVERSATION SUMMARY" in processed.text
    assert "Keep the APB interface" in processed.text


async def test_spec_agent_decodes_structured_proposal_for_review(tmp_path: Path) -> None:
    draft = SpecProposalDraft.model_validate(
        {
            "supported": True,
            "title": "Clarify the component",
            "summary": "Update the display text.",
            "rationale": "The existing wording is ambiguous.",
            "assumptions": ["The interface remains unchanged."],
            "unsupported_reason": None,
            "operations": [
                {
                    "operation_id": "set_component_text",
                    "type": "set_entity_metadata",
                    "entity": spec_context()["target"],
                    "display_name": "Demo peripheral",
                    "description": "A deterministic demonstration peripheral.",
                }
            ],
        }
    )
    client = FakeSpecOpenAI(draft)
    agent = SpecEditingAgent(settings(tmp_path), client=client)  # type: ignore[arg-type]
    artifact = await agent.respond(
        SpecAgentRequest(
            user_request="Prepare the description proposal.",
            context=spec_context(),
            proposal_requested=True,
        )
    )
    assert not isinstance(artifact, str)
    assert artifact.kind == "spec_change_proposal"
    assert artifact.schema_version == "1.0"
    assert artifact.target.entity_id == "component-demo"
    assert artifact.base_source_revision_hash == "sha256:base"
    assert artifact.operations[0]["type"] == "set_entity_metadata"
    assert client.responses.request is not None
    assert client.responses.request["model"] == "gpt-4o-mini"
    assert client.responses.request["text_format"] is SpecProposalDraft
    assert client.responses.request["store"] is False


def test_spec_proposal_schema_has_no_open_objects() -> None:
    """OpenAI Structured Outputs requires additionalProperties=false everywhere."""
    schema = to_strict_json_schema(SpecProposalDraft)
    open_objects: list[str] = []

    def visit(value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" and value.get("additionalProperties") is not False:
                open_objects.append(path)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(schema)
    assert open_objects == []


def test_explicit_proposal_language_is_distinct_from_exploration() -> None:
    assert _explicit_spec_proposal_intent("Turn this into a proposal.")
    assert _explicit_spec_proposal_intent("Please propose the changes we discussed.")
    assert not _explicit_spec_proposal_intent("Explore three possible interface designs.")


def test_every_spec_operation_variant_decodes() -> None:
    ref = spec_context()["target"]
    design = {**ref, "entity_kind": "design", "entity_id": "design-demo"}
    bus = {**ref, "entity_kind": "bus_definition", "entity_id": "bus-demo"}
    abstraction = {
        **ref,
        "entity_kind": "abstraction_definition",
        "entity_id": "abstraction-demo",
    }
    narrative = {**ref, "entity_kind": "narrative_block", "entity_id": "note"}
    block = {
        "block_id": "note",
        "type": "paragraph",
        "text": "Updated narrative.",
        "inlines": [],
        "children": [],
        "ordered": False,
        "rows": [],
        "asset_id": "",
        "alt_text": "",
        "caption": "",
        "entity_refs": [ref],
        "renderer_id": "",
        "options": [],
    }
    operations = [
        {"type": "set_entity_metadata", "entity": ref, "description": "Text"},
        {"type": "upsert_parameter", "entity": ref, "parameter": {"name": "DEPTH", "value": "4"}},
        {"type": "delete_parameter", "entity": ref, "name": "DEPTH"},
        {
            "type": "upsert_component_port",
            "component": ref,
            "port": {
                "name": "irq",
                "family": "wire",
                "display_name": "Interrupt",
                "description": "Interrupt request.",
                "direction": "out",
                "range": None,
            },
        },
        {
            "type": "upsert_component_port",
            "component": ref,
            "port": {
                "name": "service",
                "family": "transactional",
                "display_name": "Service",
                "description": "Submits work.",
                "initiative": "provides",
                "kind": "custom",
                "custom_kind": "demo_service",
                "bus_width": "DATA_WIDTH",
            },
        },
        {
            "type": "upsert_component_port",
            "component": ref,
            "port": {
                "name": "response",
                "family": "structured",
                "display_name": "Response",
                "description": "Packed response aggregate.",
                "direction": "in",
            },
        },
        {"type": "delete_component_port", "component": ref, "name": "irq"},
        {"type": "upsert_bus_interface", "component": ref, "interface": {"name": "apb", "role": "target", "bus_vlnv": "v:l:b:1", "abstraction_vlnv": "v:l:a:1", "port_maps": []}},
        {"type": "delete_bus_interface", "component": ref, "name": "apb"},
        {"type": "upsert_channel", "component": ref, "channel": {"name": "fabric", "interfaces": ["a", "b"]}},
        {"type": "delete_channel", "component": ref, "name": "fabric"},
        {"type": "upsert_instance", "design": design, "instance": {"name": "u0", "component_vlnv": "v:l:c:1"}},
        {"type": "delete_instance", "design": design, "instance_name": "u0"},
        {"type": "reorder_instances", "design": design, "instance_names": ["u0"]},
        {"type": "upsert_connection", "design": design, "connection": {"name": "link", "kind": "interface", "interface_endpoints": [], "port_endpoints": [], "external_ports": [], "hierarchy_interfaces": []}},
        {"type": "delete_connection", "design": design, "connection_name": "link"},
        {"type": "reorder_connections", "design": design, "kind": "interface", "connection_names": ["link"]},
        {"type": "set_internal_design", "component": ref, "internal_design": design},
        {"type": "clear_internal_design", "component": ref},
        {"type": "update_bus_definition", "bus_definition": bus, "properties": {"broadcast": True}},
        {"type": "set_abstraction_bus_type", "abstraction_definition": abstraction, "bus_vlnv": "v:l:b:1"},
        {"type": "upsert_abstraction_port", "abstraction_definition": abstraction, "port": {"name": "PADDR", "style": "wire", "qualifiers": [], "on_system": []}},
        {"type": "delete_abstraction_port", "abstraction_definition": abstraction, "name": "PADDR"},
        {"type": "upsert_narrative_block", "block": block, "parent_block_id": None, "index": 0},
        {"type": "delete_narrative_block", "block_id": "note"},
        {"type": "reorder_narrative_blocks", "block_ids": ["note"], "parent_block_id": None},
        {"type": "set_narrative_entity_links", "block_id": "note", "entity_refs": [narrative]},
    ]
    decoded = SpecProposalDraft.model_validate(
        {
            "supported": True,
            "title": "All operations",
            "summary": "Decode every operation variant.",
            "rationale": "Contract coverage.",
            "assumptions": [],
            "unsupported_reason": None,
            "operations": [
                {"operation_id": f"operation_{index}", **operation}
                for index, operation in enumerate(operations)
            ],
        }
    )
    assert [operation.type for operation in decoded.operations] == [
        operation["type"] for operation in operations
    ]


def test_spec_component_ports_reject_the_legacy_shape_and_invalid_custom_kind() -> None:
    ref = spec_context()["target"]
    envelope = {
        "supported": True,
        "title": "Port update",
        "summary": "Update one port.",
        "rationale": "Contract validation.",
        "assumptions": [],
        "unsupported_reason": None,
    }
    with pytest.raises(ValidationError, match="family"):
        SpecProposalDraft.model_validate(
            {
                **envelope,
                "operations": [{
                    "operation_id": "legacy_port",
                    "type": "upsert_component_port",
                    "component": ref,
                    "port": {
                        "name": "irq",
                        "style": "wire",
                        "direction": "out",
                    },
                }],
            }
        )
    with pytest.raises(ValidationError, match="custom kind name"):
        SpecProposalDraft.model_validate(
            {
                **envelope,
                "operations": [{
                    "operation_id": "invalid_custom_port",
                    "type": "upsert_component_port",
                    "component": ref,
                    "port": {
                        "name": "service",
                        "family": "transactional",
                        "initiative": "requires",
                        "kind": "custom",
                        "custom_kind": None,
                    },
                }],
            }
        )
