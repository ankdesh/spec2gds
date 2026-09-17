"""Generation and behavioral checks for the component-semantics examples."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from spec2gds.agent_spec.activities import (
    ActivityResult,
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.spec_format.ir import SpecRevision

ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class RtlExample:
    """One source package and its expected register latency."""

    name: str
    spec_path: Path
    latency: int


EXAMPLES = (
    RtlExample(
        "one_cycle",
        ROOT / "samples/minimal/single_component_with_rtl.spec",
        1,
    ),
    RtlExample(
        "two_cycle",
        ROOT / "samples/minimal/single_component_with_2cycle_rtl.spec",
        2,
    ),
)


def _registry() -> SpecExtensionRegistry:
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    return registry


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda item: item.name)
def _generate(
    example: RtlExample,
    root: Path,
) -> tuple[SpecRevision, Path, ActivityResult]:
    revision = SpecRevision.load(str(example.spec_path))
    target = revision.entry_designs()[0]
    snapshot = ActivitySnapshot.from_bytes(
        ActivitySnapshot.create(revision, target.ref).to_bytes()
    )
    result = invoke_activity(
        _registry(),
        "rtl.generate",
        snapshot,
        LocalActivityWorkspace(root),
    )
    return revision, root / result.report["output_path"], result


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda item: item.name)
def test_example_package_generates_a_complete_project(
    example: RtlExample,
    tmp_path: Path,
) -> None:
    revision, output, result = _generate(example, tmp_path)
    component = revision.components[0]
    section, = revision.entity_sections_for(component.ref, "sv")
    assert section.content.strip()
    assert "module new_component" not in section.content
    assert "endmodule" not in section.content
    assert not {"input", "output", "inout"}.intersection(section.content.split())

    source = (output / "rtl/components/new_component.sv").read_text()

    assert result.report["generator_version"] == "1.1.2"
    assert [item["section_id"] for item in result.report["source_sections"]] == [
        section.section_id
    ]
    assert source.count("module new_component (") == 1
    assert source.count("input logic clk") == 1
    assert source.count("input logic rst_n") == 1
    assert source.count("input logic [31:0] data_in") == 1
    assert source.count("input logic valid_in") == 1
    assert source.count("output logic [31:0] data_out") == 1
    assert section.content.rstrip() in source
    subprocess.run(["make", "lint"], cwd=output, check=True)


def _testbench(latency: int) -> str:
    first_edge_check = (
        "if (data_out !== 32'h12345678) $fatal(1, \"one-cycle capture failed\");"
        if latency == 1
        else "if (data_out !== 32'h00000000) $fatal(1, \"two-cycle output changed early\");"
    )
    second_edge_check = (
        "if (data_out !== 32'h12345678) $fatal(1, \"one-cycle hold failed\");"
        if latency == 1
        else "if (data_out !== 32'h12345678) $fatal(1, \"two-cycle capture failed\");"
    )
    return f"""`timescale 1ns/1ps
module tb;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic [31:0] data_in = '0;
    logic valid_in = 1'b0;
    logic [31:0] data_out;

    new_component dut (.*);
    always #1 clk = ~clk;

    task automatic tick;
        @(posedge clk);
        #1;
    endtask

    initial begin
        tick();
        if (data_out !== '0) $fatal(1, "reset did not clear output");

        rst_n = 1'b1;
        data_in = 32'h12345678;
        valid_in = 1'b1;
        tick();
        {first_edge_check}

        valid_in = 1'b0;
        data_in = 32'hdeadbeef;
        tick();
        {second_edge_check}

        tick();
        if (data_out !== 32'h12345678) $fatal(1, "invalid cycle did not hold output");
        $display("PASS");
        $finish;
    end
endmodule
"""


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda item: item.name)
def test_example_pipeline_latency(example: RtlExample, tmp_path: Path) -> None:
    _, output, _ = _generate(example, tmp_path / "workspace")
    testbench = tmp_path / "tb.sv"
    testbench.write_text(_testbench(example.latency))
    object_dir = tmp_path / "obj"
    subprocess.run(
        [
            "verilator",
            "--binary",
            "--timing",
            "--language",
            "1800-2017",
            "-Wall",
            "-Wno-fatal",
            "--top-module",
            "tb",
            "--Mdir",
            str(object_dir),
            str(output / "rtl/components/new_component.sv"),
            str(testbench),
        ],
        check=True,
    )
    completed = subprocess.run(
        [str(object_dir / "Vtb")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in completed.stdout
