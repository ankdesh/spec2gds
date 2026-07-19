"""Phase 0 circuit-designer contract and SpecIR projection tests."""

import ast
import json
from pathlib import Path

import pydantic
import pytest

from spec2gds.agent_spec.circuit_designer.contracts import (
    CircuitDesignerProtocol,
    CircuitEndpointRef,
    CircuitGraphSnapshot,
    CircuitNet,
    CommandBatch,
    SetLayoutDirectionCommand,
    SourceRef,
)
from spec2gds.agent_spec.circuit_designer.projection import project_catalog, project_design
from spec2gds.agent_spec.circuit_designer.schema import schema_bytes
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.samples import build_v1_sample


def _revision() -> SpecRevision:
    return SpecRevision.from_package(build_v1_sample())


def test_internal_design_projects_instances_terminals_and_multi_endpoint_nets() -> None:
    revision = _revision()
    design = revision.by_vlnv("design", "spec2gds.example:demo:subsystem_internal:1.0")
    graph = project_design(revision, design)

    assert graph.protocol_version == "circuit-designer.v1"
    assert graph.design.id == "design_subsystem_internal"
    assert [node.label for node in graph.nodes] == ["leaf0", "sink0"]
    assert graph.nets[0].label == "link0"
    assert [endpoint.terminal_id for endpoint in graph.nets[0].endpoints] == [
        "instance:leaf0:interface:link",
        "instance:sink0:interface:link",
    ]
    assert graph.capabilities.edit_topology is False
    assert graph.layout is None
    assert CircuitGraphSnapshot.model_validate_json(graph.model_dump_json()) == graph


def test_catalog_projects_all_designs_and_explicit_entries() -> None:
    catalog = project_catalog(_revision())

    assert len(catalog.designs) == 3
    assert catalog.entry_design_ids == ("design_top_a", "design_top_b")
    assert catalog.source_revision_hash.startswith("sha256:")


def test_contract_rejects_unknown_endpoint_and_duplicate_net_endpoint() -> None:
    revision = _revision()
    design = revision.by_vlnv("design", "spec2gds.example:demo:subsystem_internal:1.0")
    graph = project_design(revision, design)
    bad_net = CircuitNet(
        id="bad",
        label="bad",
        kind="interface",
        endpoints=(CircuitEndpointRef(terminal_id="missing"), CircuitEndpointRef(terminal_id=graph.terminals[0].id)),
        source_ref=SourceRef(source_id="bad", kind="connection"),
    )
    with pytest.raises(pydantic.ValidationError, match="unknown terminal"):
        CircuitGraphSnapshot.model_validate({**graph.model_dump(mode="json"), "nets": [bad_net.model_dump(mode="json")]})

    with pytest.raises(pydantic.ValidationError, match="same terminal twice"):
        CircuitNet(
            id="duplicate",
            label="duplicate",
            kind="interface",
            endpoints=(CircuitEndpointRef(terminal_id="a"), CircuitEndpointRef(terminal_id="a")),
            source_ref=SourceRef(source_id="duplicate", kind="connection"),
        )


def test_command_union_round_trips_by_discriminator() -> None:
    batch = CommandBatch(
        batch_id="batch_1",
        expected_source_revision_hash="sha256:" + "0" * 64,
        commands=(SetLayoutDirectionCommand(command_id="command_1", design_id="design_1", direction="DOWN"),),
    )
    parsed = CommandBatch.model_validate_json(batch.model_dump_json())
    assert parsed.commands[0].type == "set_layout_direction"
    assert parsed == batch


def test_schema_export_is_deterministic_and_contains_public_roots() -> None:
    first = schema_bytes()
    second = schema_bytes()
    assert first == second
    parsed = json.loads(first)
    assert parsed["title"] == "CircuitDesignerProtocol"
    assert {"catalog", "graph", "batch", "preview", "lease", "proposal"}.issubset(parsed["properties"])
    assert "CircuitGraphSnapshot" in parsed["$defs"]
    assert CircuitDesignerProtocol.model_json_schema(mode="validation") == CircuitDesignerProtocol.model_json_schema(mode="validation")
    checked_in = Path(__file__).resolve().parents[3] / "circuit-designer" / "schema" / "circuit-designer.v1.schema.json"
    assert checked_in.read_bytes() == first


def test_contract_module_does_not_import_specir_or_ipxact() -> None:
    contract_path = Path(__file__).resolve().parents[3] / "spec2gds" / "agent_spec" / "circuit_designer" / "contracts.py"
    tree = ast.parse(contract_path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith("spec2gds.agent_spec.spec_format") for name in imported)
