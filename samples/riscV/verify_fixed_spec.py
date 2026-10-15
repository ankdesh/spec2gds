"""Check the saved fixed-width Spec, its API export, and processor behavior."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from spec2gds.spec.activities.rtl.codegen import generate_project
from spec2gds.spec.activities.view import SpecAccess
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision


def main() -> None:
    evidence = Path(tempfile.mkdtemp(prefix="spec2gds-riscv-fixed-verify-"))
    print(f"Verification evidence: {evidence}", flush=True)
    base = HERE / "base_rtl"
    revision = SpecRevision.from_package(SpecPackage.load(str(HERE / "riscv5_fixed.spec")))
    assert not revision.diagnostics, revision.diagnostics
    assert len(revision.components) == 18
    assert len(revision.designs) == 1
    for component in revision.components:
        assert not component.parameters, component.ref
        for port in component.ports:
            assert port.style == "wire", port
            assert port.width in (None, "", 1) or re.fullmatch(r"\[\d+:\d+\]", str(port.width)), port
    sections = [s for s in revision.entity_sections if s.section_type == "sv"]
    assert len(sections) == 17
    for section in sections:
        code = re.sub(r"//[^\n]*|/\*.*?\*/", "", section.content, flags=re.S)
        assert not re.search(r"\b(parameter|module|endmodule)\b|`include|\$readmem", code), section.parent

    target = revision.entry_designs()[0].ref
    project = generate_project(SpecAccess(revision, target), target)
    assert project.top_module == "riscv5_system"
    assert project.module_count == 18
    assert not project.warnings, project.warnings
    assert "unimplemented_scaffold" not in project.implementation_status.values()
    # Regeneration must agree byte-for-byte with the saved API Activity output.
    api_export = HERE / "rtl/five-stage-risc-v-fixed-widths/riscv5-system-design"
    assert json.loads((api_export / "generation-manifest.json").read_text())["source_revision_hash"] == revision.source_revision_hash
    exported = evidence / "export"
    for relative, content in project.files.items():
        assert (api_export / relative).read_bytes() == content, relative
        destination = exported / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    print("PASS Spec structure, fixed interfaces, self-contained RTL, and API export consistency", flush=True)

    def run(command: list[str], name: str) -> None:
        result = subprocess.run(command, cwd=base, capture_output=True, text=True, timeout=180)
        (evidence / f"{name}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{name} failed:\n{result.stdout}\n{result.stderr}")
        if name.endswith("simulation"):
            print(result.stdout, end="", flush=True)

    flags = ["--Wall", "-Wno-UNUSEDSIGNAL", "--timescale", "1ns/1ps"]
    files = ["-F", str(exported / "rtl/files.f")]
    run(["verilator", "--lint-only", *flags, "--top-module", "riscv5_system", *files], "lint")
    # This bench uses no shared types; omit its unnecessary baseline header.
    program_bench = evidence / "tb_riscv5_top.sv"
    program_bench.write_text((base / "tb/tb_riscv5_top.sv").read_text().replace(
        '`include "riscv_defs.svh"\n', ""))
    run(["verilator", "--binary", "--timing", *flags,
         "--top-module", "tb_riscv5_top",
         "--Mdir", str(evidence / "program"), *files,
         str(program_bench)], "program-build")
    run([str(evidence / "program/Vtb_riscv5_top")], "program-simulation")

    # Namespace the reference in a scratch copy so its global type/enum names
    # do not shadow the self-contained module-local declarations in the Spec.
    # The baseline's arithmetic, timing, parameters and program remain intact.
    reference = evidence / "reference"
    reference.mkdir()
    shared_names = re.compile(r"\b(?:XLEN|REG_ADDR|NREG|ALU_ADD|ALU_MUL|"
                              r"IMM_I|IMM_S|IMM_B|IMM_U|IMM_J|WB_ALU|WB_MEM|WB_PC4|"
                              r"alu_op_t|imm_sel_t|wb_sel_t|ctrl_t|if_id_t|id_ex_t|ex_mem_t|mem_wb_t)\b")
    def namespace_types(content: str) -> str:
        return shared_names.sub(lambda match: "reference_" + match.group(), content)
    (reference / "riscv_defs.svh").write_text(namespace_types((base / "rtl/riscv_defs.svh").read_text()))
    sources = sorted((base / "rtl").rglob("*.sv"))
    names = "|".join(re.escape(path.stem) for path in sources)
    ref_files = []
    for source in sources:
        content = re.sub(r"\bmodule\s+(\w+)", r"module reference_\1", namespace_types(source.read_text()))
        content = re.sub(r"^(\s*)(" + names + r")(?=\s+(?:#\s*\(|\w+\s*\())",
                         r"\1reference_\2", content, flags=re.M)
        destination = reference / ("reference_" + source.name)
        destination.write_text(content)
        ref_files.append(str(destination))

    bench = evidence / "tb_equivalence.sv"
    bench.write_text(r"""module tb_equivalence;
    logic clk, rst_n;
    typedef struct packed {
        logic [31:0] pc, retire_pc, inst, data;
        logic [4:0] rd;
        logic valid, we, redirect;
    } trace_t;
    trace_t fixed_trace, reference_trace;
    riscv5_system dut (
        .i_clk(clk), .i_rst_n(rst_n), .o_pc(fixed_trace.pc),
        .o_retire_pc(fixed_trace.retire_pc), .o_retire_inst(fixed_trace.inst),
        .o_retire_data(fixed_trace.data), .o_retire_rd(fixed_trace.rd),
        .o_retire_valid(fixed_trace.valid), .o_retire_we(fixed_trace.we),
        .o_redirect(fixed_trace.redirect)
    );
    reference_riscv5_top baseline (
        .i_clk(clk), .i_rst_n(rst_n), .o_pc(reference_trace.pc),
        .o_retire_pc(reference_trace.retire_pc), .o_retire_inst(reference_trace.inst),
        .o_retire_data(reference_trace.data), .o_retire_rd(reference_trace.rd),
        .o_retire_valid(reference_trace.valid), .o_retire_we(reference_trace.we),
        .o_redirect(reference_trace.redirect)
    );
    task automatic compare_state;
        if (fixed_trace !== reference_trace) $fatal(1, "Output mismatch at %0t", $time);
        for (int r = 0; r < 32; r++)
            if (dut.u_core.u_regfile.regs[r] !== baseline.u_regfile.regs[r])
                $fatal(1, "Register x%0d mismatch at %0t", r, $time);
        for (int w = 0; w < 256; w++)
            if (dut.u_core.u_dmem.mem[w] !== baseline.u_dmem.mem[w])
                $fatal(1, "Data word %0d mismatch at %0t", w, $time);
    endtask
    initial begin
        clk = 0;
        rst_n = 0;
        #1;
        for (int w = 0; w < 256; w++)
            if (dut.u_core.u_imem.mem[w] !== baseline.u_imem.mem[w])
                $fatal(1, "Instruction image differs at word %0d", w);
        for (int cycle = 0; cycle < 600; cycle++) begin
            if (cycle == 3 || cycle == 153 || cycle == 303) rst_n = 1;
            if (cycle == 150 || cycle == 300) rst_n = 0;
            #4; clk = 1;
            #1; compare_state();
            #4; clk = 0;
            #1; compare_state();
        end
        if (dut.u_core.u_regfile.regs[31] !== 1) $fatal(1, "Program did not finish");
        $display("PASS cycle equivalence: 600 cycles, all outputs, all registers, all data words, three resets");
        $finish;
    end
endmodule
""")
    run(["verilator", "--binary", "--timing", *flags,
         "+incdir+" + str(reference), "--top-module", "tb_equivalence",
         "--Mdir", str(evidence / "equivalence"), *files, *ref_files, str(bench)], "equivalence-build")
    run([str(evidence / "equivalence/Vtb_equivalence")], "equivalence-simulation")
    (evidence / "summary.json").write_text(json.dumps({
        "status": "passed", "spec": str(HERE / "riscv5_fixed.spec"),
        "source_revision_hash": revision.source_revision_hash,
        "components": 18, "designs": 1, "equivalence_cycles": 600,
        "coverage": "Directed program, repeated reset, all outputs/registers/data words; not formal equivalence or ISA compliance",
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
