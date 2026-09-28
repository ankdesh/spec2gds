"""Contract and compiler acceptance checks for the native SystemC Activity."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecAccess,
    SpecExtensionRegistry,
    activity_availability,
    invoke_activity,
)
from spec2gds.agent_spec.activities.systemc_rtl import register_extensions
from spec2gds.agent_spec.activities.systemc_rtl.codegen import prepare_project
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.sections import (
    delete_entity_section,
    upsert_systemverilog_section,
)

_ROOT = Path(__file__).parents[4]
_ONE = _ROOT / "samples/minimal/single_component_with_rtl.spec"
_TWO = _ROOT / "samples/minimal/single_component_with_2cycle_rtl.spec"


def _prepared(path: Path):
    revision = SpecRevision.load(str(path))
    target = revision.entry_designs()[0].ref
    return prepare_project(SpecAccess(revision, target), target)


def _revision_with_body(body: str) -> SpecRevision:
    original = SpecRevision.load(str(_ONE))
    package = original.to_package()
    upsert_systemverilog_section(package, original.components[0].ref, body)
    return SpecRevision.from_package(package)


def test_activity_is_separate_design_scoped_generator() -> None:
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    definition = registry.activity("systemc.generate_cycle_accurate").definition
    assert definition.scopes.entity_kinds == ("design",)
    assert definition.requires_workspace_output


@pytest.mark.parametrize("path, instances", [(_ONE, 1), (_TWO, 2)])
def test_existing_clocked_examples_assemble_without_rtl_generator(
    path: Path, instances: int
) -> None:
    prepared = _prepared(path)
    assert prepared.component_count == 1
    assert prepared.instance_count == instances
    assert len(prepared.source_sections) == 1
    source = "\n".join(item.decode("utf-8") for item in prepared.source_files.values())
    assert "always_ff @(posedge clk or negedge rst_n)" in source
    assert source.count("always_ff") == 1
    assert "module spec_component_" in source
    assert "module spec_design_" in source


def test_missing_compiler_is_an_availability_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIRCT_PREFIX", raising=False)
    revision = SpecRevision.load(str(_ONE))
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = activity_availability(
        registry,
        "systemc.generate_cycle_accurate",
        ActivitySnapshot.create(revision, target),
    )
    assert not result.available
    assert "CIRCT_PREFIX" in result.diagnostics[0]


@pytest.mark.parametrize(
    ("content", "diagnostic"),
    [
        (None, "no SystemVerilog body"),
        ("assign data_out = 32'hxxxx_xxxx;\n", "X/Z or unknown-valued"),
    ],
)
def test_unsupported_source_is_rejected_before_output(
    content: str | None, diagnostic: str, tmp_path: Path
) -> None:
    original = SpecRevision.load(str(_ONE))
    package = original.to_package()
    leaf = original.components[0]
    delete_entity_section(package, leaf.ref, "sv")
    if content is not None:
        upsert_systemverilog_section(package, leaf.ref, content)
    revision = SpecRevision.from_package(package)
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    snapshot = ActivitySnapshot.create(revision, target)
    availability = activity_availability(registry, "systemc.generate_cycle_accurate", snapshot)
    assert not availability.available
    assert diagnostic in " ".join(availability.diagnostics)
    with pytest.raises(ValueError, match="unavailable"):
        invoke_activity(
            registry, "systemc.generate_cycle_accurate", snapshot,
            LocalActivityWorkspace(tmp_path),
        )
    assert not list(tmp_path.rglob("generation-manifest.json"))


@pytest.mark.skipif(not os.environ.get("CIRCT_PREFIX"), reason="CIRCT_PREFIX not configured")
def test_unsupported_circt_operation_is_rejected_before_output(tmp_path: Path) -> None:
    revision = _revision_with_body("assign data_out = data_in / 32'd3;\n")
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    availability = activity_availability(
        registry, "systemc.generate_cycle_accurate", ActivitySnapshot.create(revision, target)
    )
    assert not availability.available
    assert "comb.divu" in " ".join(availability.diagnostics)
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(not os.environ.get("CIRCT_PREFIX"), reason="CIRCT_PREFIX not configured")
def test_slang_error_points_to_stored_section() -> None:
    revision = _revision_with_body("assign data_out = ;\n")
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    availability = activity_availability(
        registry, "systemc.generate_cycle_accurate", ActivitySnapshot.create(revision, target)
    )
    assert not availability.available
    assert revision.entity_sections[0].source_path in " ".join(availability.diagnostics)


@pytest.mark.skipif(not os.environ.get("CIRCT_PREFIX"), reason="CIRCT_PREFIX not configured")
@pytest.mark.parametrize("path", [_ONE, _TWO])
def test_pinned_circt_accepts_clocked_examples(path: Path) -> None:
    from spec2gds.agent_spec.activities.systemc_rtl.codegen import _compile

    header, versions = _compile(_prepared(path))
    assert b"SC_MODULE" in header
    assert "circt" in versions


@pytest.mark.skipif(not os.environ.get("CIRCT_PREFIX"), reason="CIRCT_PREFIX not configured")
def test_regeneration_is_deterministic_and_isolated_from_verilog(tmp_path: Path) -> None:
    revision = SpecRevision.load(str(_ONE))
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    snapshot = ActivitySnapshot.create(revision, target)
    workspace = LocalActivityWorkspace(tmp_path)
    rtl_marker = tmp_path / "rtl" / revision.document_id / target.entity_id / "manual.sv"
    rtl_marker.parent.mkdir(parents=True)
    rtl_marker.write_text("module manual; endmodule\n")
    first = invoke_activity(registry, "systemc.generate_cycle_accurate", snapshot, workspace)
    output = tmp_path / first.report["output_path"]
    first_files = {p.relative_to(output).as_posix(): p.read_bytes()
                   for p in output.rglob("*") if p.is_file()}
    manifest = json.loads(first_files["generation-manifest.json"])
    assert manifest["generator_id"] == "systemc.generate_cycle_accurate"
    assert manifest["source_revision_hash"] == revision.source_revision_hash
    assert manifest["source_sections"]
    (output / "stale.cpp").write_text("stale")
    second = invoke_activity(registry, "systemc.generate_cycle_accurate", snapshot, workspace)
    assert second.report["tree_sha256"] == first.report["tree_sha256"]
    assert {p.relative_to(output).as_posix(): p.read_bytes()
            for p in output.rglob("*") if p.is_file()} == first_files
    assert rtl_marker.read_text() == "module manual; endmodule\n"


@pytest.mark.skipif(
    not os.environ.get("CIRCT_PREFIX") or not shutil.which("g++"),
    reason="CIRCT_PREFIX and a SystemC-capable C++ compiler are required",
)
@pytest.mark.parametrize("path, first_edge", [(_ONE, 0x12345678), (_TWO, 0)])
def test_native_systemc_matches_clocked_sample_behavior(
    path: Path, first_edge: int, tmp_path: Path
) -> None:
    revision = SpecRevision.load(str(path))
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = invoke_activity(
        registry,
        "systemc.generate_cycle_accurate",
        ActivitySnapshot.create(revision, target),
        LocalActivityWorkspace(tmp_path),
    )
    project = tmp_path / result.report["output_path"]
    component = next(project.glob("source/spec_component_*.sv")).stem
    bench = f"""
#include <systemc>
#include "design.h"
int sc_main(int, char**) {{
  sc_core::sc_clock clk("clk", 10, sc_core::SC_NS, 0.5, 5, sc_core::SC_NS, false);
  sc_core::sc_signal<bool> rst_n, valid_in;
  sc_core::sc_signal<sc_dt::sc_uint<32>> data_in, data_out;
  {component} dut("dut");
  dut.clk(clk); dut.rst_n(rst_n); dut.data_in(data_in);
  dut.valid_in(valid_in); dut.data_out(data_out);
  rst_n.write(true); valid_in.write(false); data_in.write(0);
  sc_core::sc_start(1, sc_core::SC_NS);
  rst_n.write(false);
  sc_core::sc_start(1, sc_core::SC_NS);
  if (data_out.read().to_uint() != 0) return 1;
  rst_n.write(true); valid_in.write(true); data_in.write(0x12345678);
  sc_core::sc_start(10, sc_core::SC_NS);
  if (data_out.read().to_uint() != {first_edge}u) return 2;
  valid_in.write(false); data_in.write(0xdeadbeef);
  sc_core::sc_start(10, sc_core::SC_NS);
  if (data_out.read().to_uint() != 0x12345678u) return 3;
  sc_core::sc_start(10, sc_core::SC_NS);
  if (data_out.read().to_uint() != 0x12345678u) return 4;
  rst_n.write(false);
  sc_core::sc_start(1, sc_core::SC_NS);
  if (data_out.read().to_uint() != 0u) return 5;
  return 0;
}}
"""
    bench_path = tmp_path / "bench.cpp"
    bench_path.write_text(bench)
    executable = tmp_path / "bench"
    subprocess.run(
        ["g++", "-std=c++17", "-I", str(project / "include"), str(bench_path),
         "-lsystemc", "-o", str(executable)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(
    not os.environ.get("CIRCT_PREFIX") or not shutil.which("g++"),
    reason="CIRCT_PREFIX and a SystemC-capable C++ compiler are required",
)
def test_native_systemc_handles_slices_and_concatenation(tmp_path: Path) -> None:
    revision = _revision_with_body("""
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) data_out <= '0;
  else if (valid_in) data_out <= {data_in[15:0], data_in[31:16]};
end
""")
    target = revision.entry_designs()[0].ref
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = invoke_activity(
        registry, "systemc.generate_cycle_accurate",
        ActivitySnapshot.create(revision, target), LocalActivityWorkspace(tmp_path),
    )
    project = tmp_path / result.report["output_path"]
    component = next(project.glob("source/spec_component_*.sv")).stem
    bench = f"""
#include <systemc>
#include "design.h"
int sc_main(int, char**) {{
  sc_core::sc_clock clk("clk", 10, sc_core::SC_NS, 0.5, 5, sc_core::SC_NS, false);
  sc_core::sc_signal<bool> rst_n, valid_in;
  sc_core::sc_signal<sc_dt::sc_uint<32>> data_in, data_out;
  {component} dut("dut");
  dut.clk(clk); dut.rst_n(rst_n); dut.data_in(data_in);
  dut.valid_in(valid_in); dut.data_out(data_out);
  rst_n.write(false);
  sc_core::sc_start(2, sc_core::SC_NS);
  rst_n.write(true); valid_in.write(true); data_in.write(0x12345678);
  sc_core::sc_start(10, sc_core::SC_NS);
  return data_out.read().to_uint() == 0x56781234u ? 0 : 1;
}}
"""
    bench_path = tmp_path / "slices_bench.cpp"
    bench_path.write_text(bench)
    executable = tmp_path / "slices_bench"
    subprocess.run(
        ["g++", "-std=c++17", "-I", str(project / "include"),
         str(bench_path), "-lsystemc", "-o", str(executable)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run([str(executable)], check=True, capture_output=True, text=True)
