"""Compound architecture, authority and bounded context acceptance."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from spec2gds.agent_spec.activities.rtl.codegen import generate_project, validate_project
from spec2gds.agent_spec.activities.view import SpecAccess
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal, preview_assistant_proposal
from spec2gds.agent_spec.spec_format.assistant_context_pages import build_context_page
from spec2gds.agent_spec.spec_format.circuit_adapter import project_design_to_circuit
from spec2gds.agent_spec.spec_format.ir import EndpointSliceIR, SpecRevision


def ref(name, kind="component"):
    return {"document_id": "unified", "entity_id": name, "entity_kind": kind}


def proposal(revision, operations):
    return SpecChangeProposal(
        document_id=revision.document_id,
        scope="document",
        proposal_id="compound",
        base_source_revision_hash=revision.source_revision_hash,
        title="Architecture",
        summary="Architecture",
        rationale="Reusable composition",
        operations=operations,
    )


def hierarchy():
    revision = SpecRevision.from_package(SpecPackage.create("unified"))
    ports = [
        {"name": "d", "family": "wire", "direction": "in", "range": "7:0"},
        {"name": "q", "family": "wire", "direction": "out", "range": "7:0"},
    ]
    operations = [
        {
            "type": "set_entity_metadata",
            "entity": ref("parent"),
            "description": "Pass an 8-bit word.\nTwo children carry the low and high halves.",
        },
        {
            "type": "create_entity",
            "kind": "design",
            "name": "inner",
            "entity_id": "inner",
            "entry_design": False,
            "instances": [
                {"name": "lo", "component_vlnv": "spec2gds.local:work:leaf:1.0"},
                {"name": "hi", "component_vlnv": "spec2gds.local:work:leaf:1.0"},
            ],
        },
        {
            "type": "create_entity",
            "kind": "component",
            "name": "parent",
            "entity_id": "parent",
            "ports": ports,
        },
        {
            "type": "create_entity",
            "kind": "component",
            "name": "leaf",
            "entity_id": "leaf",
            "ports": ports,
            "systemverilog": "assign q = d;\n",
        },
        {
            "type": "set_entity_metadata",
            "entity": ref("leaf"),
            "description": "Combinational identity. Outputs follow inputs without a clock or reset.",
        },
        {
            "type": "set_internal_design",
            "component": ref("parent"),
            "internal_design": ref("inner", "design"),
        },
        {
            "type": "upsert_narrative_block",
            "block": {
                "block_id": "requirements",
                "type": "paragraph",
                "text": "Every bit shall pass through unchanged.",
                "entity_refs": [ref("parent"), ref("leaf")],
            },
        },
    ]
    for instance, lsb in [("lo", 0), ("hi", 4)]:
        for port in ["d", "q"]:
            operations.append(
                {
                    "type": "upsert_connection",
                    "design": ref("inner", "design"),
                    "connection": {
                        "name": f"{instance}_{port}",
                        "kind": "ad_hoc",
                        "port_endpoints": [
                            {
                                "instance_name": instance,
                                "port_name": port,
                                "slice": {"lsb": 0, "width": 4},
                            }
                        ],
                        "external_ports": [{"port_name": port, "slice": {"lsb": lsb, "width": 4}}],
                    },
                }
            )
    for index, operation in enumerate(operations):
        operation["operation_id"] = f"op_{index}"
    result = preview_assistant_proposal(revision, proposal(revision, operations))
    assert result["status"] == "valid", result
    return revision, result["_revision"], operations


def access(revision, target):
    return SpecAccess(revision, target)


def test_compound_explanations_composition_and_narrative_are_atomic(tmp_path: Path):
    original, candidate, operations = hierarchy()
    assert not candidate.entry_designs()
    circuit = project_design_to_circuit(candidate, candidate.designs[0].ref.entity_id).document
    assert [terminal["width"] for terminal in circuit["design"]["boundary_terminals"]] == [8, 8]
    assert all(terminal["width"] == 8 for component in circuit["components"] for terminal in component["terminals"])
    assert not original.components
    package = candidate.to_package()
    package.save(tmp_path / "roundtrip.spec")
    loaded = SpecRevision.load(str(tmp_path / "roundtrip.spec"))
    page = build_context_page(loaded, entity_ids=["parent"])
    assert any("Two children" in str(record["value"]) for record in page["records"])
    bad = [
        *operations,
        {
            "operation_id": "bad",
            "type": "upsert_connection",
            "design": ref("inner", "design"),
            "connection": {
                "name": "bad",
                "kind": "ad_hoc",
                "port_endpoints": [{"instance_name": "missing", "port_name": "q"}],
            },
        },
    ]
    assert preview_assistant_proposal(original, proposal(original, bad))["status"] == "invalid"
    assert not original.components


@pytest.mark.parametrize("display_name", ["16-bit Up/Down Counter", "Counter state"])
def test_initial_rtl_validation_uses_stable_identity_after_atomic_display_rename(display_name):
    revision = SpecRevision.from_package(SpecPackage.create("unified"))
    operations = [
        {
            "operation_id": "create_counter",
            "type": "create_entity",
            "kind": "component",
            "name": "up_down_counter",
            "entity_id": "counter",
            "ports": [
                {"name": "d", "family": "wire", "direction": "in"},
                {"name": "q", "family": "wire", "direction": "out"},
            ],
            "systemverilog": "assign q = d;",
        },
        {
            "operation_id": "describe_counter",
            "type": "set_entity_metadata",
            "entity": ref("counter"),
            "display_name": display_name,
            "description": "Combinational passthrough with stored RTL.",
        },
    ]
    result = preview_assistant_proposal(revision, proposal(revision, operations))
    assert result["status"] == "valid", result
    candidate = result["_revision"]
    assert candidate.components[0].display_name == display_name
    assert candidate.components[0].ref.entity_id == "counter"
    sections = candidate.entity_sections_for(candidate.components[0].ref, "sv")
    assert len(sections) == 1
    assert [item["section_id"] for item in result["section_validation"]] == [sections[0].section_id]
    assert not revision.components


def test_reachable_component_generation_and_text_only_authority():
    _, revision, _ = hierarchy()
    parent = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    before = generate_project(access(revision, parent.ref), parent.ref)
    source = before.files["rtl/components/parent.sv"].decode()
    assert before.module_count == 2
    assert "assign lo_d_bits[7:4] = '0;" in source
    assert "assign lo_d_bits[3:0] = d[3:0];" in source
    assert "assign q[7:4] = hi_q_bits[3:0];" in source
    text = [
        {
            "operation_id": "text",
            "type": "set_entity_metadata",
            "entity": ref("leaf"),
            "description": "Proposed future behavior disagrees with current identity RTL.\nKeep both until reviewed.",
        }
    ]
    after_revision = preview_assistant_proposal(revision, proposal(revision, text))["_revision"]
    after = generate_project(access(after_revision, parent.ref), parent.ref)
    assert {path: data for path, data in before.files.items() if path.endswith(".sv")} == {
        path: data for path, data in after.files.items() if path.endswith(".sv")
    }
    assert before.files["generation-manifest.json"] != after.files["generation-manifest.json"]
    leaf = revision.by_vlnv("component", "spec2gds.local:work:leaf:1.0")
    assert generate_project(access(revision, leaf.ref), leaf.ref).module_count == 1


def test_numeric_slices_reject_overlap_bounds_and_widths():
    _, revision, _ = hierarchy()
    parent = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    for replace_from, replace_to, diagnostic in [
        (b"<ipxact:left>7</ipxact:left>", b"<ipxact:left>2</ipxact:left>", "exceeds bounds")
    ]:
        package = revision.to_package()
        entry = next(entry for entry in package.manifest.documents if entry.entity_id == "parent")
        package.files[entry.path] = package.files[entry.path].replace(replace_from, replace_to)
        from spec2gds.agent_spec.spec_format.models import sha256_digest

        package.manifest = package.manifest.model_copy(
            update={
                "documents": [
                    item.model_copy(update={"sha256": sha256_digest(package.files[item.path])})
                    for item in package.manifest.documents
                ]
            }
        )
        changed = SpecRevision.from_package(package)
        errors = validate_project(access(changed, parent.ref), parent.ref).errors
        assert any(diagnostic in error for error in errors), errors


def test_context_pages_are_bounded_lossless_and_revision_bound():
    _, revision, _ = hierarchy()
    large = "// multiline ü description\n" * 7000
    updated = preview_assistant_proposal(
        revision,
        proposal(
            revision,
            [
                {
                    "operation_id": "large",
                    "type": "set_entity_metadata",
                    "entity": ref("leaf"),
                    "description": large,
                }
            ],
        ),
    )["_revision"]
    cursor = None
    fragments = {}
    first_cursor = None
    for _ in range(100):
        page = build_context_page(updated, entity_ids=["leaf"], cursor=cursor)
        assert len(json.dumps(page, ensure_ascii=False).encode()) < 40 * 1024
        for record in page["records"]:
            if record["path"][-1] == "description" and "offset" in record:
                fragments[record["offset"]] = record["value"]
        cursor = page["next_cursor"]
        first_cursor = first_cursor or cursor
        if not page["incomplete"]:
            break
    assert "".join(fragments[offset] for offset in sorted(fragments)) == large
    with pytest.raises(ValueError, match="stale"):
        build_context_page(revision, entity_ids=["leaf"], cursor=first_cursor)
    with pytest.raises(ValueError):
        build_context_page(updated, cursor="invalid")
    with pytest.raises(ValueError):
        build_context_page(updated, entity_ids=["missing"])


@pytest.mark.parametrize(
    "fault, diagnostic",
    [
        ("width", "effective widths"),
        ("overlap", "overlap"),
        ("ascending", "ascending sliced"),
        ("symbolic", "symbolic part-select"),
        ("driver", "no driver"),
    ],
)
def test_slice_validation_diagnostics(fault, diagnostic):
    _, revision, _ = hierarchy()
    inner = revision.designs[0]
    connections = list(inner.connections)
    first = connections[0]
    if fault == "width":
        connections[0] = replace(
            first, port_endpoints=(replace(first.port_endpoints[0], slice=EndpointSliceIR(0, 3)),)
        )
    elif fault == "overlap":
        other = connections[2]
        connections[2] = replace(
            other, external_ports=(replace(other.external_ports[0], slice=EndpointSliceIR(2, 4)),)
        )
    elif fault == "symbolic":
        connections[0] = replace(
            first, port_endpoints=(replace(first.port_endpoints[0], symbolic_slice="WIDTH-1:0"),)
        )
    elif fault == "driver":
        other = connections[1]
        connections[1] = replace(
            other, port_endpoints=(replace(other.port_endpoints[0], port_name="d"),)
        )
    else:
        parent = revision.resolve(
            next(
                component.ref
                for component in revision.components
                if component.ref.entity_id == "parent"
            )
        )
        changed = replace(
            parent, ports=tuple(replace(port, range="0:7", width="[0:7]") for port in parent.ports)
        )
        revision = replace(
            revision,
            components=tuple(
                changed if component.ref == parent.ref else component
                for component in revision.components
            ),
        )
    revision = replace(revision, designs=(replace(inner, connections=tuple(connections)),))
    parent = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    errors = validate_project(access(revision, parent.ref), parent.ref).errors
    assert any(diagnostic in error for error in errors), errors


def test_unrelated_unsupported_entities_and_exact_cli_targets():
    from scripts.run_rtl_activity import select_target

    _, revision, _ = hierarchy()
    operations = [
        {
            "operation_id": "unrelated",
            "type": "create_entity",
            "kind": "component",
            "name": "unsupported",
            "entity_id": "unsupported",
            "ports": [{"name": "p", "family": "wire", "direction": "in", "range": "WIDTH-1:0"}],
        }
    ]
    revision = preview_assistant_proposal(revision, proposal(revision, operations))["_revision"]
    target = select_target(revision, "parent")
    assert select_target(revision, target.vlnv) == target
    project = generate_project(access(revision, target.ref), target.ref)
    assert project.module_count == 2
    assert not any("unsupported.sv" in name for name in project.files)
    assert generate_project(access(revision, target.ref), target.ref).files == project.files
    for selection in [None, "par", "missing"]:
        with pytest.raises(ValueError):
            select_target(revision, selection)


def test_v3_generation_replaces_owned_legacy_manifest(tmp_path):
    from spec2gds.agent_spec.activities import LocalActivityWorkspace

    _, revision, _ = hierarchy()
    target = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    project = generate_project(access(revision, target.ref), target.ref)
    legacy = json.loads(project.files["generation-manifest.json"])
    legacy["schema_version"] = "spec2gds.rtl-generation.v2"
    legacy["design_id"] = legacy.pop("target")["entity_id"]
    legacy.pop("target_vlnv")
    workspace = LocalActivityWorkspace(tmp_path)
    options = {
        "relative_path": "selected",
        "generator_id": "rtl.generate",
        "document_id": revision.document_id,
        "design_id": target.ref.entity_id,
    }
    workspace.replace_directory(
        files={**project.files, "generation-manifest.json": json.dumps(legacy).encode()}, **options
    )
    workspace.replace_directory(files=project.files, **options)
    assert json.loads((tmp_path / "selected/generation-manifest.json").read_text())[
        "schema_version"
    ].endswith("v3")


@pytest.mark.extensive
def test_numeric_slice_hookups_simulate_without_bit_loss(tmp_path):
    import shutil

    from scripts.rtl_evaluation import evaluate_project

    if shutil.which("verilator") is None:
        pytest.skip("Slice simulation requires Verilator")
    _, revision, _ = hierarchy()
    parent = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    project = generate_project(access(revision, parent.ref), parent.ref)
    output = tmp_path / "generated"
    for name, content in project.files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "slice.sv").write_text("""module evaluation_tb;
logic [7:0] d; wire [7:0] q;
@@TOP@@ dut(.d(d),.q(q));
initial begin
  for(int i=0;i<256;i++) begin d=8'(i); #1; if(q !== d) $fatal(1,"Slice hookup lost bits: d=%h q=%h",d,q); end
  $display("EVALUATION_PASS"); $finish;
end
endmodule
""")
    case = {
        "id": "numeric_slice",
        "configuration": {},
        "bench": "slice.sv",
        "bench_adaptation": "Exhaustive eight-bit structured slice identity.",
    }
    report = evaluate_project(output, case, tmp_path / "evaluation", fixtures=fixtures)
    assert report["compilation"]["status"] == "passed", report
    assert report["simulation"]["status"] == "passed", report


def test_selected_context_preserves_narrative_and_entity_ownership():
    _, revision, _ = hierarchy()
    operation = {
        "operation_id": "narrative",
        "type": "upsert_narrative_block",
        "block": {
            "block_id": "notes",
            "type": "section",
            "text": "Implementation notes",
            "children": [
                {
                    "block_id": "parent_note",
                    "type": "paragraph",
                    "text": "Parent-only note",
                    "entity_refs": [ref("parent")],
                }
            ],
        },
    }
    revision = preview_assistant_proposal(revision, proposal(revision, [operation]))["_revision"]
    parent = revision.by_vlnv("component", "spec2gds.local:work:parent:1.0")
    selected = build_context_page(revision, parent.ref, entity_ids=["leaf", "parent_note"])
    records = selected["records"]
    assert any(
        record["path"] == ("entities", 0, "writable") and record["value"] is False
        for record in records
    )
    assert {
        record["value"]
        for record in records
        if record["path"][:2] == ("writable", "entity_refs") and record["path"][-1] == "entity_id"
    } == {"parent", "inner"}
    assert "parent_note" in {
        record["value"]
        for record in records
        if record["path"][:2] == ("writable", "narrative_block_ids")
    }
    assert "requirements" not in {
        record["value"]
        for record in records
        if record["path"][:2] == ("writable", "narrative_block_ids")
    }
    assert any(record["value"] == "Parent-only note" for record in records)
