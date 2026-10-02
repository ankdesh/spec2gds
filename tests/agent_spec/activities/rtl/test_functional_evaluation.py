"""Self-checking benches must reject broken designs, independent of names/text."""

import math
import shutil

import pytest

from scripts.rtl_evaluation import evaluate_project, load_cases
from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import RtlGenerationReport, register_extensions
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal, preview_assistant_proposal
from spec2gds.agent_spec.spec_format.ir import SpecRevision

CASES = load_cases()
pytestmark = pytest.mark.skipif(
    shutil.which("verilator") is None, reason="Functional evaluation requires Verilator"
)


def reference_body(case, broken=False):
    """Test-only concrete implementations; never passed to a model or production."""
    width = case["configuration"].get("width", 8)
    family = case["family"]
    if family == "adder":
        return (
            f"assign {{cout,sum}} = {{1'b0,a}}+{{1'b0,b}}+{{{{{width}{{1'b0}}}},cin}};"
            if not broken
            else "assign sum=a^b^{WIDTH{cin}}; assign cout=1'b0;".replace("WIDTH", str(width))
        )
    if family == "counter":
        return (
            "always @(posedge clk) if(reset) count <= '0; else if(up_down) count <= count+1'b1; else count <= count-1'b1;"
            if not broken
            else "always @(posedge clk) count <= '0;"
        )
    if family == "priority":
        return "always_comb begin index='0; valid=|request; for(int i=0;i<8;i++) if(request[i]) index=3'(i); end"
    if family == "fifo":
        depth = case["configuration"]["depth"]
        address = int(math.log2(depth))
        body = f"""
localparam int A={address}, W={width}, D={depth};
logic [W-1:0] mem [0:D-1];
logic [A:0] wbin, rbin, wgray, rgray;
logic [A:0] rmeta, rsync, wmeta, wsync;
wire [A:0] wnext = wbin + {{{{A{{1'b0}}}},(winc && !wfull)}};
wire [A:0] rnext = rbin + {{{{A{{1'b0}}}},(rinc && !rempty)}};
wire [A:0] wgray_next = (wnext>>1)^wnext;
wire [A:0] rgray_next = (rnext>>1)^rnext;
always @(posedge wclk or negedge wrstn) begin
  if(!wrstn) begin rmeta<='0; rsync<='0; end
  else begin rmeta<=rgray; rsync<=rmeta; end
end
always @(posedge rclk or negedge rrstn) begin
  if(!rrstn) begin wmeta<='0; wsync<='0; end
  else begin wmeta<=wgray; wsync<=wmeta; end
end
always @(posedge wclk or negedge wrstn) begin
  if(!wrstn) begin wbin<='0; wgray<='0; wfull<=0; end
  else begin
    if(winc && !wfull) mem[wbin[A-1:0]]<=wdata;
    wbin<=wnext;
    wgray <= wgray_next;
    wfull <= (wgray_next == {{~rsync[A:A-1],rsync[A-2:0]}});
  end
end
always @(posedge rclk or negedge rrstn) begin
  if(!rrstn) begin rbin<='0; rgray<='0; rempty<=1; rdata<='0; end
  else begin
    if(rinc && !rempty) rdata<=mem[rbin[A-1:0]];
    rbin<=rnext; rgray<=rgray_next; rempty<=(rgray_next==wsync);
  end
end
"""
        if broken:
            # The reviewed single-write bug: register Gray from the old pointer
            # only during transfers; idle clocks never publish the last write.
            body = body.replace(
                "wgray <= wgray_next;", "if(winc && !wfull) wgray <= (wbin>>1)^wbin;"
            )
        return body
    raise ValueError(family)


def ports_for(case):
    width = case["configuration"].get("width", 8)
    families = {
        "adder": [
            ("a", "in", width),
            ("b", "in", width),
            ("cin", "in", 1),
            ("sum", "out", width),
            ("cout", "out", 1),
        ],
        "counter": [
            ("clk", "in", 1),
            ("reset", "in", 1),
            ("up_down", "in", 1),
            ("count", "out", width),
        ],
        "fifo": [
            ("wclk", "in", 1),
            ("rclk", "in", 1),
            ("wrstn", "in", 1),
            ("rrstn", "in", 1),
            ("winc", "in", 1),
            ("rinc", "in", 1),
            ("wdata", "in", width),
            ("rdata", "out", width),
            ("wfull", "out", 1),
            ("rempty", "out", 1),
        ],
        "priority": [("request", "in", 8), ("index", "out", 3), ("valid", "out", 1)],
        "pipeline": [
            ("clk", "in", 1),
            ("reset", "in", 1),
            ("din", "in", width),
            ("dout", "out", width),
        ],
    }
    return [
        {
            "name": name,
            "family": "wire",
            "direction": direction,
            **({"range": f"{bits - 1}:0"} if bits > 1 else {}),
        }
        for name, direction, bits in families[case["family"]]
    ]


def build_reference(case, tmp_path, broken=False):
    revision = SpecRevision.from_package(SpecPackage.create("functional"))
    target = {
        "document_id": "functional",
        "entity_kind": "component",
        "entity_id": "implementation",
    }
    operations = [
        {
            "type": "create_entity",
            "kind": "component",
            "name": "implementation",
            "entity_id": "implementation",
            "ports": ports_for(case),
        }
    ]
    if case["family"] != "pipeline":
        operations[0]["systemverilog"] = reference_body(case, broken)
    else:
        internal = {**target, "entity_kind": "design", "entity_id": "composition"}
        operations.extend(
            [
                {
                    "type": "create_entity",
                    "kind": "component",
                    "name": "register",
                    "entity_id": "register",
                    "ports": ports_for(case),
                    "systemverilog": "always @(posedge clk) if(reset) dout<='0; else dout<=din;",
                },
                {
                    "type": "create_entity",
                    "kind": "design",
                    "name": "composition",
                    "entity_id": "composition",
                    "entry_design": False,
                    "instances": [
                        {"name": "first", "component_vlnv": "spec2gds.local:work:register:1.0"},
                        {"name": "second", "component_vlnv": "spec2gds.local:work:register:1.0"},
                    ],
                },
                {"type": "set_internal_design", "component": target, "internal_design": internal},
            ]
        )
        for signal in ["clk", "reset"]:
            operations.append(
                {
                    "type": "upsert_connection",
                    "design": internal,
                    "connection": {
                        "name": signal,
                        "kind": "ad_hoc",
                        "external_ports": [signal],
                        "port_endpoints": [
                            {"instance_name": instance, "port_name": signal}
                            for instance in ["first", "second"]
                        ],
                    },
                }
            )
        for name, endpoints, boundary in [
            ("input", [("first", "din")], ["din"]),
            ("stage", [("first", "dout"), ("second", "din")], []),
            ("output", [("second", "dout")], ["dout"]),
        ]:
            operations.append(
                {
                    "type": "upsert_connection",
                    "design": internal,
                    "connection": {
                        "name": name,
                        "kind": "ad_hoc",
                        "external_ports": boundary,
                        "port_endpoints": [
                            {"instance_name": inst, "port_name": port} for inst, port in endpoints
                        ],
                    },
                }
            )
    for i, operation in enumerate(operations):
        operation["operation_id"] = f"op_{i}"
    proposal = SpecChangeProposal(
        scope="document",
        document_id="functional",
        proposal_id="test-reference",
        base_source_revision_hash=revision.source_revision_hash,
        title="Test-only reference",
        summary="Test fixture",
        rationale="Check bench effectiveness",
        operations=operations,
    )
    preview = preview_assistant_proposal(revision, proposal)
    assert preview["status"] == "valid", preview
    revision = preview["_revision"]
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = invoke_activity(
        registry,
        "rtl.generate",
        ActivitySnapshot.create(revision, revision.components[0].ref),
        LocalActivityWorkspace(tmp_path / "workspace"),
    )
    return tmp_path / "workspace" / result.report["output_path"], result


@pytest.mark.parametrize("case", list(CASES.values()), ids=list(CASES))
def test_concrete_configurations_compile_and_simulate(case, tmp_path):
    project, result = build_reference(case, tmp_path)
    report = evaluate_project(
        project,
        case,
        tmp_path / "evaluation",
        expected_revision=result.report["source_revision_hash"],
    )
    assert report["generation"]["status"] == "passed", report
    assert report["lint"]["status"] == "passed", report
    assert report["compilation"]["status"] == "passed", report
    assert report["simulation"]["status"] == "passed", report
    assert report["inference_quality"] == "unverified"


@pytest.mark.parametrize("case_id", ["adder_8", "counter_16", "fifo_8_16"])
def test_broken_implementations_fail_functional_checks(case_id, tmp_path):
    case = CASES[case_id]
    project, _ = build_reference(case, tmp_path, broken=True)
    report = evaluate_project(project, case, tmp_path / "evaluation")
    assert report["compilation"]["status"] == "passed", report
    assert report["simulation"]["status"] == "failed", report
    if case["family"] == "fifo":
        assert (
            "single accepted write never became visible"
            in (tmp_path / "evaluation/simulation.log").read_text()
        )


def test_report_reads_legacy_and_rejects_wrong_source_revision(tmp_path):
    project, result = build_reference(CASES["adder_8"], tmp_path)
    legacy = {**result.report, "schema_version": "spec2gds.rtl-generation-report.v2"}
    legacy["design"] = legacy.pop("target")
    legacy["design_vlnv"] = legacy.pop("target_vlnv")
    legacy.pop("implementation_status")
    parsed = RtlGenerationReport.model_validate(legacy)
    assert parsed.target.entity_id == result.report["target"]["entity_id"]
    report = evaluate_project(
        project, CASES["adder_8"], tmp_path / "evaluation", expected_revision="sha256:stale"
    )
    assert report["generation"]["status"] == "failed"
    assert report["simulation"]["status"] == "unverified"
