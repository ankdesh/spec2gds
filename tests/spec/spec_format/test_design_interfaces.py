"""Standalone interface, parameter scope, and circuit preservation contracts."""

import pytest

from spec2gds.spec.activities import SpecAccess
from spec2gds.spec.activities.rtl.codegen import generate_project
from spec2gds.spec.activities.systemc_rtl.codegen import prepare_project
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.circuit_adapter import (
    compile_circuit_sync_operations,
    project_design_to_circuit,
)
from spec2gds.spec.spec_format.edit_access import EditAccessError, SpecEditAccess
from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    ExternalPortEndpointIR,
    InstanceIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.transactions import (
    AddComponentPort,
    CreateHardware,
    SetDesignInterface,
    SpecEditTransaction,
    UpdateParameter,
    UpsertConnection,
    UpsertInstance,
    WirePortInput,
)


def apply(revision, *operations):
    result = SpecEditTransaction(revision.source_revision_hash, operations, "authoring").apply(revision)
    assert result.revision is not None, result.diagnostics
    return result.revision


def parameterized_source():
    revision = SpecRevision.from_package(SpecPackage.create("design_ports_test"))
    revision = apply(revision, CreateHardware("component", "Buffer", "buffer", systemverilog="assign y = a;"), CreateHardware("design", "System", "system"))
    component, design = revision.components[0].ref, revision.designs[0].ref
    revision = apply(revision, UpdateParameter(component, {"name": "WIDTH", "rtl_type": "int unsigned", "value": "8"}),
                     AddComponentPort(component, "a", WirePortInput("in", "WIDTH-1:0")), AddComponentPort(component, "y", WirePortInput("out", "WIDTH-1:0")))
    revision = apply(revision, SetDesignInterface(design,
        ({"name": "a", "direction": "in", "range": "DATA_WIDTH-1:0"}, {"name": "y", "direction": "out", "range": "DATA_WIDTH-1:0"}),
        ({"name": "DATA_WIDTH", "rtl_type": "int unsigned", "value": "8"},)))
    revision = apply(revision,
        UpsertInstance(design, InstanceIR("u", revision.components[0].vlnv, {"WIDTH": "DATA_WIDTH"})),
        UpsertInstance(design, InstanceIR("small", revision.components[0].vlnv, {"WIDTH": "4"})),
        UpsertConnection(design, ConnectionIR("input", "ad_hoc", port_endpoints=(PortEndpointIR("u", "a"),), external_ports=(ExternalPortEndpointIR("a"),))),
        UpsertConnection(design, ConnectionIR("output", "ad_hoc", port_endpoints=(PortEndpointIR("u", "y"),), external_ports=(ExternalPortEndpointIR("y"),))))
    return revision, component, design


def test_end_session_fences_every_participant_and_never_revokes_successor(tmp_path):
    access = SpecEditAccess(tmp_path / "access.sqlite3")
    first = access.acquire("file")
    child = access.acquire("file", first["context_id"], "circuit")
    access.end_session("file", first["context_id"], first["participant_id"])
    for grant in (first, child):
        with pytest.raises(EditAccessError):
            access.renew("file", grant["context_id"], grant["participant_id"])
        assert access.acquire("file", grant["context_id"], grant["participant_id"])["mode"] == "read_only"
    successor = access.acquire("file")
    access.end_session("file", first["context_id"], first["participant_id"])
    access.release("file", first["context_id"], first["participant_id"])
    assert access.status("file", successor["context_id"], successor["participant_id"])["mode"] == "edit"


def test_round_trip_and_distinct_instance_widths():
    revision, component, design = parameterized_source()
    loaded = SpecRevision.from_package(SpecPackage.from_bytes(revision.to_package().to_bytes()))
    assert loaded.source_revision_hash == revision.source_revision_hash
    assert loaded.resolve(design).ports[0].range == "DATA_WIDTH-1:0"
    assert loaded.manifest.required_features == ["design-interface-v1"]
    assert len(loaded.components) == 1  # No hidden boundary Component.
    projection = project_design_to_circuit(loaded, design.entity_id, include_catalog=True)
    definitions = {c["id"]: c for c in projection.document["components"]}
    instances = projection.document["design"]["instances"]
    assert [definitions[i["component_id"]]["terminals"][0]["width"] for i in instances] == [8, 4]
    assert projection.document["design"]["boundary_terminals"][0]["width"] == 8
    operations = compile_circuit_sync_operations(loaded, projection, projection.document)
    saved = apply(loaded, *operations)
    assert saved.resolve(design).ports == loaded.resolve(design).ports
    assert saved.resolve(design).instances == loaded.resolve(design).instances


def test_rtl_top_declares_parameters_ports_and_explicit_overrides():
    revision, component, design = parameterized_source()
    project = generate_project(SpecAccess(revision), design)
    source = b"\n".join(project.files.values()).decode()
    assert "DATA_WIDTH" in source and ".WIDTH(DATA_WIDTH)" in source and ".WIDTH(4)" in source
    assert "input" in source and "output" in source
    cycle = prepare_project(SpecAccess(revision), design)
    assert cycle.top_ports == (("a", "in", 8), ("y", "out", 8))
    assert b".WIDTH(DATA_WIDTH)" in b"\n".join(cycle.source_files.values())


@pytest.mark.parametrize("values", [{"UNKNOWN": "4"}, {"WIDTH": "NO_SUCH_VALUE"}])
def test_invalid_override_preserves_saved_revision(values):
    revision, component, design = parameterized_source()
    before = revision.source_revision_hash
    result = SpecEditTransaction(before, (UpsertInstance(design, InstanceIR("u", revision.components[0].vlnv, values)),), "authoring").apply(revision)
    assert result.revision is None
    assert revision.source_revision_hash == before


def test_duplicate_and_unknown_ports_rejected():
    revision, component, design = parameterized_source()
    result = SpecEditTransaction(revision.source_revision_hash, (SetDesignInterface(design,
        ({"name": "a", "direction": "in"}, {"name": "a", "direction": "out"}), ()),), "authoring").apply(revision)
    assert result.revision is None


def test_top_level_boundary_rename_updates_connections_without_losing_expressions():
    from spec2gds.spec.spec_format.design_interfaces import read_interface
    revision, component, design = parameterized_source()
    interface = read_interface(revision.to_package().files, design)
    ports = tuple({**p.model_dump(), "name": "input_a" if p.name == "a" else p.name} for p in interface.ports)
    renamed = apply(revision, SetDesignInterface(design, ports, tuple(p.model_dump() for p in interface.parameters), (("a", "input_a"),)))
    assert renamed.resolve(design).connections[0].external_ports[0].port_name == "input_a"
    assert renamed.resolve(design).ports[0].range == "DATA_WIDTH-1:0"


def test_parameter_override_width_conflict_is_atomic():
    revision, component, design = parameterized_source()
    result = SpecEditTransaction(revision.source_revision_hash, (UpsertInstance(design, InstanceIR("u", revision.components[0].vlnv, {"WIDTH": "3"})),), "authoring").apply(revision)
    assert result.revision is None
    assert "incompatible port widths" in " ".join(result.diagnostics)


def test_instance_overrides_use_declared_ipxact_parameter_identity():
    from lxml import etree
    revision, component, design = parameterized_source()
    package = revision.to_package()
    entry = next(e for e in package.manifest.documents if e.entity_id == component.entity_id)
    root = etree.fromstring(package.files[entry.path])
    root.xpath("./*[local-name()='parameters']/*[local-name()='parameter']")[0].set("parameterId", "buffer_width_identity")
    package.add_document("component", etree.tostring(root))
    # Rewrite the source references to the deliberately different parameter ID.
    entry = next(e for e in package.manifest.documents if e.entity_id == design.entity_id)
    root = etree.fromstring(package.files[entry.path])
    for value in root.xpath(".//*[local-name()='configurableElementValue']"):
        value.set("referenceId", "buffer_width_identity")
    package.add_document("design", etree.tostring(root))
    revision = SpecRevision.from_package(package)
    assert dict(revision.resolve(design).instances[0].parameter_values) == {"WIDTH": "DATA_WIDTH"}
    saved = apply(revision, UpsertInstance(design, revision.resolve(design).instances[0]))
    assert b'referenceId="buffer_width_identity"' in saved.to_package().files[entry.path]


@pytest.mark.parametrize("values", [None, 1, "WIDTH", [1], [["WIDTH"]], [["WIDTH", "8", "extra"]], {"WIDTH": 8}, {1: "8", "WIDTH": "8"}])
def test_malformed_instance_parameter_values_report_validation_error(values):
    with pytest.raises(ValueError, match="named expressions"):
        InstanceIR("u", "example:library:Buffer:1.0", values)


def test_child_defaults_cannot_capture_parent_parameters():
    from dataclasses import replace

    from spec2gds.spec.spec_format.design_interfaces import instance_interface
    revision, component, design = parameterized_source()
    child = revision.components[0]
    child = replace(child, parameters=(replace(child.parameters[0], value="DATA_WIDTH"),))
    revision = replace(revision, components=(child,))
    with pytest.raises(ValueError, match="DATA_WIDTH"):
        instance_interface(revision, revision.resolve(design), revision.resolve(design).instances[0])


def test_resolver_probe_names_do_not_shadow_design_parameters():
    from dataclasses import replace

    from spec2gds.spec.spec_format.design_interfaces import instance_interface, resolve_ports
    revision, component, design = parameterized_source()
    parent = revision.resolve(design)
    parent = replace(parent, parameters=(replace(parent.parameters[0], name="__spec_parameter_0"),))
    revision = replace(revision, designs=(parent,))
    instance = replace(parent.instances[0], parameter_values={"WIDTH": "__spec_parameter_0"})
    assert resolve_ports(instance_interface(revision, parent, instance))["a"]["width"] == 8


def test_new_connection_rejects_incompatible_effective_instance_widths():
    revision, component, design = parameterized_source()
    connection = ConnectionIR("incompatible", "ad_hoc", port_endpoints=(PortEndpointIR("u", "y"), PortEndpointIR("small", "a")))
    result = SpecEditTransaction(revision.source_revision_hash, (UpsertConnection(design, connection),), "authoring").apply(revision)
    assert result.revision is None
    assert any("width" in message for message in result.diagnostics)


@pytest.mark.parametrize("kind", ["rtl", "cycle"])
def test_parameterized_generated_modules_compile(tmp_path, kind):
    import subprocess
    from dataclasses import asdict

    revision, _, design = parameterized_source()
    interface = revision.resolve(design)
    ports = tuple({"name": p.name, "direction": p.direction, "range": p.range} for p in interface.ports)
    revision = apply(revision, SetDesignInterface(design, (*ports,
        {"name": "b", "direction": "in", "range": "3:0"}, {"name": "z", "direction": "out", "range": "3:0"}),
        tuple(asdict(p) for p in interface.parameters)),
        UpsertConnection(design, ConnectionIR("small_input", "ad_hoc", port_endpoints=(PortEndpointIR("small", "a"),), external_ports=(ExternalPortEndpointIR("b"),))),
        UpsertConnection(design, ConnectionIR("small_output", "ad_hoc", port_endpoints=(PortEndpointIR("small", "y"),), external_ports=(ExternalPortEndpointIR("z"),))))
    project = generate_project(SpecAccess(revision), design) if kind == "rtl" else prepare_project(SpecAccess(revision), design)
    files = project.files if kind == "rtl" else project.source_files
    sources = []
    for path, content in files.items():
        if path.endswith(".sv"):
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            sources.append(str(target))
    for width in (8, 16):
        result = subprocess.run(["verilator", "--lint-only", "-Wno-fatal", "--top-module", project.top_module,
                                 "--Mdir", str(tmp_path / "obj"), f"-GDATA_WIDTH={width}", *sources], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "WIDTHTRUNC" not in result.stderr and "WIDTHEXPAND" not in result.stderr


def test_cyclic_design_parameters_do_not_replace_source():
    revision = SpecRevision.from_package(SpecPackage.create("cycles"))
    revision = apply(revision, CreateHardware("design", "System", "system"))
    design = revision.designs[0].ref
    result = SpecEditTransaction(revision.source_revision_hash, (SetDesignInterface(design, (), (
        {"name": "FIRST", "rtl_type": "int", "value": "SECOND"},
        {"name": "SECOND", "rtl_type": "int", "value": "FIRST"},
    )),), "authoring").apply(revision)
    assert result.revision is None


def test_unknown_required_feature_is_rejected():
    from spec2gds.spec.spec_format.models import SpecManifest

    with pytest.raises(ValueError, match="unsupported"):
        SpecManifest(document_id="unsupported", required_features=["future-interface-v9"])


def test_matching_parameter_names_do_not_forward_implicitly():
    revision = SpecRevision.from_package(SpecPackage.create("no_forwarding"))
    revision = apply(revision, CreateHardware("component", "Buffer", "buffer"), CreateHardware("design", "System", "system"))
    component, design = revision.components[0].ref, revision.designs[0].ref
    revision = apply(revision, UpdateParameter(component, {"name": "WIDTH", "rtl_type": "int", "value": "4"}),
                     AddComponentPort(component, "a", WirePortInput("in", "WIDTH-1:0")),
                     SetDesignInterface(design, (), ({"name": "WIDTH", "rtl_type": "int", "value": "16"},)),
                     UpsertInstance(design, InstanceIR("u", revision.components[0].vlnv)))
    projection = project_design_to_circuit(revision, design.entity_id)
    definition = next(c for c in projection.document["components"] if c["id"] == projection.document["design"]["instances"][0]["component_id"])
    assert definition["terminals"][0]["width"] == 4
    assert ".WIDTH(WIDTH)" not in b"\n".join(generate_project(SpecAccess(revision), design).files.values()).decode()
