from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError
from spec2gds_runtime import LogSettings

from spec2gds_assistant.a2a_agent import _explicit_spec_proposal_intent
from spec2gds_assistant.agents.circuit_editor import (
    INSTRUCTIONS as CIRCUIT_INSTRUCTIONS,
)
from spec2gds_assistant.agents.circuit_editor import (
    CircuitEditingAgent,
)
from spec2gds_assistant.agents.context import CircuitContextProcessor, SpecContextProcessor
from spec2gds_assistant.agents.spec_editor import (
    PROPOSAL_INSTRUCTIONS as SPEC_PROPOSAL_INSTRUCTIONS,
)
from spec2gds_assistant.agents.spec_editor import (
    SpecEditingAgent,
)
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
        port=6013,
        database_path=tmp_path / "assistant.db",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        web_dist_path=tmp_path / "missing",
        circuit_request_timeout_seconds=5,
    )


def test_environment_defaults_are_lan_accessible_and_use_gpt_4o_mini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ASSISTANT_DATABASE_PATH",
        "ASSISTANT_WEB_DIST_PATH",
        "SPEC2GDS_SERVICE_CONFIG",
        "SPEC2GDS_PUBLIC_HOST",
        "AI_ASSISTANT_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPEC2GDS_PUBLIC_HOST", "design-host.test")
    configured = Settings.from_env()
    assert configured.openai_model == "gpt-4o-mini"
    assert configured.database_path.name == "assistant.db"
    assert configured.database_path.parent.name == "data"
    assert configured.web_dist_path.name == "dist"
    assert configured.web_dist_path.parent.name == "web"
    assert configured.host == "0.0.0.0"
    assert configured.port == 6013
    assert configured.spec_editor_service_url == "http://design-host.test:6010"
    assert configured.circuit_designer_ui_url == "http://design-host.test:6012"


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
    assert "COMPONENT DEFINITIONS" in processed.text
    assert "CIRCUIT OBJECT MODEL" in processed.text
    assert "complete definition" in processed.text
    assert "producer_0: component=producer" in processed.text
    assert "terminal data: direction=output" in processed.text
    assert "VALID ENDPOINT CATALOG" in processed.text
    assert "instance endpoint producer_0.data" in processed.text
    assert '"instance_id":"producer_0"' in processed.text
    assert "add_boundary_terminal" in processed.text
    assert 'instance ids=["producer_0"]' in processed.text
    assert 'net ids=["data_net"]' in processed.text


def test_circuit_prompt_maps_simple_requests_to_supported_operations() -> None:
    assert '"create/add/place a component"' in CIRCUIT_INSTRUCTIONS
    assert "add_component followed by add_instance" in CIRCUIT_INSTRUCTIONS
    assert "add_boundary_terminal" in CIRCUIT_INSTRUCTIONS
    assert "create_net with all requested endpoints" in CIRCUIT_INSTRUCTIONS
    assert "VALID ENDPOINT CATALOG" in CIRCUIT_INSTRUCTIONS


def test_circuit_draft_supports_components_ports_and_connections() -> None:
    draft = CircuitProposalDraft.model_validate(
        {
            "supported": True,
            "title": "Add and connect a block",
            "summary": "Define, place, expose, and connect one block.",
            "rationale": "Covers the common logical editing operations.",
            "assumptions": [],
            "unsupported_reason": None,
            "operations": [
                {
                    "operation_id": "add_filter_definition",
                    "type": "add_component",
                    "component": {
                        "id": "filter",
                        "label": "Filter",
                        "origin": "local",
                        "editable": True,
                        "terminals": [
                            {
                                "id": "data_in",
                                "label": "Data in",
                                "direction": "input",
                                "width": 8,
                                "category": "port",
                            }
                        ],
                        "parameters": [],
                        "appearance": {
                            "renderer_key": "default",
                            "properties": [],
                        },
                    },
                },
                {
                    "operation_id": "place_filter",
                    "type": "add_instance",
                    "instance": {
                        "id": "filter_0",
                        "label": "Filter 0",
                        "component_id": "filter",
                        "parameter_values": [],
                    },
                },
                {
                    "operation_id": "add_data_input",
                    "type": "add_boundary_terminal",
                    "terminal": {
                        "id": "data_in",
                        "label": "Data in",
                        "direction": "input",
                        "width": 8,
                        "category": "port",
                    },
                },
                {
                    "operation_id": "connect_data_input",
                    "type": "create_net",
                    "net": {
                        "id": "data_in_net",
                        "label": "Data input",
                        "endpoints": [
                            {
                                "kind": "boundary",
                                "terminal_id": "data_in",
                                "slice": None,
                            },
                            {
                                "kind": "instance",
                                "instance_id": "filter_0",
                                "terminal_id": "data_in",
                                "slice": None,
                            },
                        ],
                    },
                },
            ],
        }
    )
    serialized = draft.model_dump(mode="json", exclude_none=True)
    assert [operation["type"] for operation in serialized["operations"]] == [
        "add_component",
        "add_instance",
        "add_boundary_terminal",
        "create_net",
    ]
    assert serialized["operations"][0]["component"]["appearance"]["properties"] == {}
    assert serialized["operations"][1]["instance"]["parameter_values"] == {}


def test_circuit_proposal_schema_has_no_open_objects() -> None:
    """Circuit response schema stays within OpenAI's supported JSON Schema subset."""
    schema = to_strict_json_schema(CircuitProposalDraft)
    open_objects: list[str] = []
    one_of_paths: list[str] = []

    def visit(value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" and value.get("additionalProperties") is not False:
                open_objects.append(path)
            if "oneOf" in value:
                one_of_paths.append(path)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(schema)
    assert open_objects == []
    assert one_of_paths == []


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


async def test_agent_logs_owned_openai_request_and_response_boundaries(
    tmp_path: Path,
    circuit_snapshot: dict[str, Any],
) -> None:
    draft = CircuitProposalDraft.model_validate({
        "supported": False, "title": "Unsupported", "summary": "No change",
        "rationale": "Outside scope", "assumptions": [],
        "unsupported_reason": "Not supported", "operations": [],
    })
    log_file = tmp_path / "combined.jsonl"
    configured = dataclasses.replace(
        settings(tmp_path),
        logging=LogSettings(True, "debug", log_file, 100_000, "127.0.0.1", 6014),
    )
    await CircuitEditingAgent(configured, client=FakeOpenAI(draft)).propose(
        CircuitAgentRequest(user_request="Inspect this circuit.", snapshot=circuit_snapshot)
    )
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert [record["event"] for record in records] == ["request", "response"]
    assert "Inspect this circuit." in json.dumps(records[0]["details"])


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
        "scope": "entity",
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
    assert "PLAIN-LANGUAGE TASK MAPPING" in processed.text
    assert "upsert_component_port" in processed.text
    assert processed.scope == "entity"


def test_document_spec_context_exposes_only_top_level_creation() -> None:
    processed = SpecContextProcessor().process(
        SpecAgentRequest(
            user_request="Summarize the architecture.",
            context={
                "scope": "document",
                "document_id": "demo",
                "source_revision_hash": "sha256:base",
                "target": None,
                "rendered_context": {
                    "document_id": "demo",
                    "source_revision_hash": "sha256:base",
                    "target": None,
                    "text": "SEMANTIC SPECIFICATION\ncomponent:timer",
                },
                "available_references": {
                    "components": [
                        {
                            "name": "timer",
                            "vlnv": "spec2gds.local:work:timer:1.0",
                        }
                    ]
                },
                "diagnostics": [],
            },
        )
    )
    assert processed.scope == "document"
    assert "WRITABLE BOUNDARY: create new top-level components or designs only" in processed.text
    assert "existing entities and their contents are read-only" in processed.text
    assert "EXISTING REFERENCES" in processed.text
    assert "spec2gds.local:work:timer:1.0" in processed.text
    assert "component:timer" in processed.text


async def test_document_spec_context_creates_design_proposal_with_initial_instances(
    tmp_path: Path,
) -> None:
    draft = SpecProposalDraft.model_validate(
        {
            "supported": True,
            "title": "Create a replicated design",
            "summary": "Add ten instances of asd1.",
            "rationale": "The requested top-level design groups the replicas.",
            "assumptions": ["The phrase asd 1 refers to the unique asd1 component."],
            "unsupported_reason": None,
            "operations": [
                {
                    "operation_id": "create_replicated_design",
                    "type": "create_entity",
                    "kind": "design",
                    "name": "asd1_array",
                    "instances": [
                        {
                            "name": f"asd1_{index}",
                            "component_vlnv": "spec2gds.local:work:asd1:1.0",
                        }
                        for index in range(1, 11)
                    ],
                }
            ],
        }
    )
    client = FakeSpecOpenAI(draft)
    result = await SpecEditingAgent(
        settings(tmp_path), client=client  # type: ignore[arg-type]
    ).respond(
        SpecAgentRequest(
            user_request="Add a design with 10 instances of asd 1.",
            proposal_requested=True,
            context={
                "scope": "document",
                "document_id": "demo",
                "source_revision_hash": "sha256:base",
                "target": None,
                "rendered_context": {
                    "document_id": "demo",
                    "source_revision_hash": "sha256:base",
                    "target": None,
                    "text": (
                        "COMPONENT asd1\n"
                        "VLNV: spec2gds.local:work:asd1:1.0"
                    ),
                },
                "diagnostics": [],
            },
        )
    )
    assert not isinstance(result, str)
    assert result.scope == "document"
    assert result.target is None
    assert result.operations[0]["type"] == "create_entity"
    assert len(result.operations[0]["instances"]) == 10
    assert str(result.operations[0]["entity_id"]).startswith("design_asd1_array_")


def test_spec_prompt_maps_simple_entity_bound_requests() -> None:
    assert '"create/add a port" means upsert_component_port' in SPEC_PROPOSAL_INSTRUCTIONS
    assert '"create/add a component" means upsert_instance' in SPEC_PROPOSAL_INSTRUCTIONS
    assert '"create a net" means upsert_connection' in SPEC_PROPOSAL_INSTRUCTIONS
    assert "the only supported operation is create_entity" in SPEC_PROPOSAL_INSTRUCTIONS


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
    """Spec response schema stays within OpenAI's supported JSON Schema subset."""
    schema = to_strict_json_schema(SpecProposalDraft)
    open_objects: list[str] = []
    one_of_paths: list[str] = []

    def visit(value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" and value.get("additionalProperties") is not False:
                open_objects.append(path)
            if "oneOf" in value:
                one_of_paths.append(path)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(schema)
    assert open_objects == []
    assert one_of_paths == []


def test_explicit_proposal_language_is_distinct_from_exploration() -> None:
    assert _explicit_spec_proposal_intent("Turn this into a proposal.")
    assert _explicit_spec_proposal_intent("Please propose the changes we discussed.")
    assert _explicit_spec_proposal_intent("Add a design with 10 instances of asd 1.")
    assert _explicit_spec_proposal_intent("Create a component named timer.")
    assert _explicit_spec_proposal_intent("Could you please make a design named cluster?")
    assert not _explicit_spec_proposal_intent("Update me on the current architecture.")
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
        {
            "type": "create_entity",
            "kind": "design",
            "name": "new_design",
            "instances": [{"name": "u0", "component_vlnv": "v:l:c:1"}],
        },
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
        {
            "type": "upsert_connection",
            "design": design,
            "connection": {
                "name": "link",
                "kind": "interface",
                "interface_endpoints": [
                    {"instance_name": "u0", "interface_name": "apb"},
                    {"instance_name": "u1", "interface_name": "apb"},
                ],
                "hierarchy_interfaces": [],
            },
        },
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


def test_spec_component_ports_reject_unknown_shape_and_invalid_custom_kind() -> None:
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
                    "operation_id": "invalid_port",
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


def test_spec_connections_reject_mixed_endpoint_families() -> None:
    design = {
        **spec_context()["target"],
        "entity_kind": "design",
        "entity_id": "design-demo",
    }
    with pytest.raises(ValidationError, match="interface_endpoints|extra_forbidden"):
        SpecProposalDraft.model_validate(
            {
                "supported": True,
                "title": "Invalid ad-hoc connection",
                "summary": "Mix endpoint families.",
                "rationale": "Regression coverage.",
                "assumptions": [],
                "unsupported_reason": None,
                "operations": [
                    {
                        "operation_id": "invalid_connection",
                        "type": "upsert_connection",
                        "design": design,
                        "connection": {
                            "name": "link",
                            "kind": "ad_hoc",
                            "interface_endpoints": [
                                {"instance_name": "u0", "interface_name": "port1"},
                                {"instance_name": "u1", "interface_name": "port1"},
                            ],
                            "port_endpoints": [],
                            "external_ports": [],
                        },
                    }
                ],
            }
        )
