"""Generated smoke checks exercise inputs without a functional verdict."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from spec2gds.spec.activities import (
    ActivitySnapshot,
    LocalActivityScratchDirectory,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.spec.activities.rtl import register_extensions
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef, sha256_digest
from spec2gds.spec.spec_format.sections import upsert_systemverilog_section
from spec2gds.spec.spec_format.testing import _xml


def _source(ports=(), body="", *, name="example", parameters=(), design=False):
    package = SpecPackage.create("smoke_spec")
    declarations = []
    for port_name, direction, bounds in ports:
        vector = ""
        if bounds:
            left, right = bounds.split(":")
            vector = (
                "<ipxact:vectors><ipxact:vector>"
                f"<ipxact:left>{escape(left)}</ipxact:left>"
                f"<ipxact:right>{escape(right)}</ipxact:right>"
                "</ipxact:vector></ipxact:vectors>"
            )
        declarations.append(
            f"<ipxact:port><ipxact:name>{escape(port_name)}</ipxact:name><ipxact:wire>"
            f"<ipxact:direction>{direction}</ipxact:direction>{vector}"
            "</ipxact:wire></ipxact:port>"
        )
    parameter_xml = "".join(
        '<ipxact:parameter xmlns:rtl="urn:spec2gds:rtl" rtl:type="int unsigned">'
        f"<ipxact:name>{param}</ipxact:name><ipxact:value>{value}</ipxact:value>"
        "</ipxact:parameter>"
        for param, value in parameters
    )
    entry = package.add_document(
        "component", _xml(
            "component", "leaf", name,
            ("<ipxact:model><ipxact:ports>" + "".join(declarations)
             + "</ipxact:ports></ipxact:model>" if ports else "")
            + (f"<ipxact:parameters>{parameter_xml}</ipxact:parameters>" if parameters else ""),
        ),
    )
    target = EntityRef(document_id=package.manifest.document_id,
                       entity_kind="component", entity_id=entry.entity_id)
    if body:
        upsert_systemverilog_section(package, target, body)
    if design:
        entry = package.add_document("design", _xml(
            "design", "top", "top",
            "<ipxact:componentInstances><ipxact:componentInstance>"
            "<ipxact:instanceName>child</ipxact:instanceName>"
            f'<ipxact:componentRef vendor="spec2gds.example" library="demo" name="{name}" version="1.0"/>'
            "</ipxact:componentInstance></ipxact:componentInstances>",
        ))
        target = target.model_copy(update={"entity_kind": "design", "entity_id": entry.entity_id})
    return SpecRevision.from_package(package), target


def _generate(root: Path, source):
    revision, target = source
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    result = invoke_activity(
        registry, "rtl.generate", ActivitySnapshot.create(revision, target),
        LocalActivityScratchDirectory(root),
    )
    return root / result.report["output_path"], result


def _make(project: Path, *arguments, success=True):
    result = subprocess.run(
        ["make", "smoke", *arguments], cwd=project,
        capture_output=True, text=True, timeout=90,
    )
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return result.stdout + result.stderr


def _samples(project: Path):
    return [
        dict(field.split("=", 1) for field in line.split())
        for line in (project / "TEMP_smoke/run.log").read_text().splitlines()
        if line.startswith("sample=")
    ]


def test_smoke_generation_is_deterministic_and_inventory_covers_all_files(tmp_path, monkeypatch):
    source = _source([("data-in", "in", "4:1"), ("wire", "out", "4:1")])
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("Generation must not run simulation"))
    project, report = _generate(tmp_path, source)
    first = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    (project / "TEMP_smoke").mkdir()
    (project / "TEMP_smoke/run.log").write_text("stale")
    _, second = _generate(tmp_path, source)
    assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()} == first
    assert second.report["tree_sha256"] == report.report["tree_sha256"]
    manifest = json.loads((project / "generation-manifest.json").read_text())
    inventory = {item["path"]: item for item in manifest["files"]}
    assert set(inventory) == {p.as_posix() for p in first} - {"generation-manifest.json"}
    assert "sim/smoke_tb.sv" in inventory
    for path, item in inventory.items():
        assert item["sha256"] == sha256_digest((project / path).read_bytes())
    bench = (project / "sim/smoke_tb.sv").read_text()
    assert ".data_in(smoke_io_0)" in bench
    assert ".wire_rtl(smoke_io_1)" in bench
    assert "Unimplemented scaffolds are present" in bench
    assert "CLOCK must name a one-bit input port" in bench


@pytest.mark.extensive
def test_smoke_drives_full_width_patterns_and_prints_settled_outputs(tmp_path):
    # Also exercise parameter defaults, negative bounds, indexed one-bit ports,
    # widths above 64 bits, and a collision with the testbench module ID.
    ports = [
        ("pattern", "in", "WIDTH:1"), ("copied", "out", "WIDTH:1"),
        ("negative", "in", "-1:-4"), ("negative_out", "out", "-1:-4"),
        ("wide", "in", "129:0"), ("wide_out", "out", "129:0"),
        ("clock_index", "in", "5:5"), ("bit_out", "out", "5:5"),
        ("pad", "inout", None),
        ("ascending", "in", "0:3"), ("ascending_out", "out", "0:3"),
    ]
    body = "assign copied=pattern; assign negative_out=negative; assign wide_out=wide; assign bit_out=clock_index; assign ascending_out=ascending;"
    project, _ = _generate(tmp_path, _source(
        ports, body, name="spec2gds_smoke_tb", parameters=[("WIDTH", "4")],
    ))
    output = _make(project)
    assert "Smoke run completed." in output
    assert "Bidirectional port pad is undriven" in output
    assert "No clock supplied" in output
    rows = _samples(project)
    assert len(rows) == 18
    assert rows[0]["time"] == "11ns"
    assert rows[-1]["time"] == "198ns"
    for row in rows:
        for source, sink in [("pattern", "copied"), ("negative", "negative_out"),
                             ("wide", "wide_out"), ("clock_index", "bit_out"),
                             ("ascending", "ascending_out")]:
            assert row[f"in:{source}"] == row[f"out:{sink}"]
    assert [int(row["in:pattern"], 16) for row in rows[:4]] == [0, 15, 5, 10]
    assert int(rows[1]["in:wide"], 16) == (1 << 130) - 1
    assert int(rows[2]["in:wide"], 16) > 1 << 64
    assert len({row["in:wide"] for row in rows}) > 4
    assert "[WIDTH:1] pattern" in (project / "rtl/components/spec2gds_smoke_tb.sv").read_text()


@pytest.mark.extensive
@pytest.mark.parametrize("edge,active", [("posedge", 0), ("negedge", 1)])
def test_smoke_reset_clock_and_two_cycle_sampling(tmp_path, edge, active):
    ports = [("clk", "in", "5:5"), ("rst", "in", None),
             ("data", "in", "7:0"), ("result", "out", "7:0")]
    body = f"""logic [7:0] stage;
always @({edge} clk) begin
    if (rst == 1'b{active}) begin stage <= '0; result <= '0; end
    else begin stage <= data; result <= stage; end
end"""
    project, _ = _generate(tmp_path, _source(ports, body))
    _make(project, "CLOCK=clk", "RESET=rst", f"RESET_ACTIVE={active}")
    rows = _samples(project)
    assert len(rows) == 20
    assert rows[-1]["time"] == "220ns"
    assert [row["phase"] for row in rows[:2]] == ["reset", "reset"]
    assert all(int(row["out:result"], 16) == 0 for row in rows[:2])
    assert all(int(row["in:rst"], 16) == active for row in rows[:2])
    assert all(int(row["in:rst"], 16) == 1 - active for row in rows[2:])
    assert all(int(row["in:clk"], 16) == 0 for row in rows)
    stimulus = [row for row in rows if row["phase"] == "stimulus"]
    for before, after in zip(stimulus, stimulus[1:]):
        assert after["out:result"] == before["in:data"]
    assert rows[-1]["out:result"] == stimulus[-1]["in:data"]
    # The runner must produce the same observations without rebuilding.
    first_log = (project / "TEMP_smoke/run.log").read_bytes()
    _make(project, "CLOCK=clk", "RESET=rst", f"RESET_ACTIVE={active}")
    assert (project / "TEMP_smoke/run.log").read_bytes() == first_log
    for options, message in [
        (["CLOCK=missing"], "CLOCK must name a one-bit input port"),
        (["CLOCK=result"], "CLOCK must name a one-bit input port"),
        (["CLOCK=data"], "CLOCK must name a one-bit input port"),
        (["RESET=result"], "RESET must name a one-bit input port"),
        (["CLOCK=clk", "RESET=clk"], "CLOCK and RESET must name different"),
        (["RESET_ACTIVE=2"], "RESET_ACTIVE must be 0 or 1"),
    ]:
        assert message in _make(project, *options, success=False)
    _make(project, "CLOCK=clk")
    assert len(_samples(project)) == 18
    assert all(row["phase"] != "reset" for row in _samples(project))


@pytest.mark.extensive
def test_smoke_portless_design_reports_limits_and_never_exercises_children(tmp_path):
    project, result = _generate(tmp_path, _source(
        [("data", "in", "7:0"), ("output_data", "out", "7:0")], design=True,
    ))
    output = _make(project)
    assert "No external stimulus or input/output observation is possible." in output
    assert "Unimplemented scaffolds are present" in output
    assert "in:data=" not in output
    assert list((project / "sim").iterdir()) == [project / "sim/smoke_tb.sv"]
    assert "unimplemented_scaffold" in result.report["implementation_status"].values()
    assert len(_samples(project)) == 18
    # All runtime artifacts stay in TEMP_smoke, and clean preserves source files.
    assert not (project / "obj_dir").exists()
    subprocess.run(["make", "clean-smoke"], cwd=project, check=True)
    assert not (project / "TEMP_smoke").exists()
    assert (project / "sim/smoke_tb.sv").is_file()


@pytest.mark.extensive
def test_smoke_rejects_early_finish_and_propagates_compilation_failure(tmp_path):
    project, _ = _generate(tmp_path, _source(body="initial begin #1; $finish; end"))
    output = _make(project, success=False)
    assert "Smoke run completed." not in output
    assert (project / "TEMP_smoke/build.log").is_file()
    # A source edit must invalidate the cached binary and retain compiler errors.
    (project / "sim/smoke_tb.sv").write_text("invalid SystemVerilog\n")
    assert "%Error" in _make(project, success=False)
    assert "%Error" in (project / "TEMP_smoke/build.log").read_text()
