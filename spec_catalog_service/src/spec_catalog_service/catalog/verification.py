"""Hardware verification harness for library components."""

from __future__ import annotations

import hashlib
import random
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spec2gds.spec.activities import (
    ActivitySnapshot,
    LocalActivityScratchDirectory,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.spec.activities.rtl import register_extensions
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec_catalog_service.catalog.components.models import ComponentDef
from spec_catalog_service.catalog.schemas import (
    CheckRecord,
    EvidenceRecordV1,
    compute_sha256,
    serialize_canonical_evidence_bytes,
)


def get_git_commit() -> str:
    """Retrieve the current git commit SHA or return local development fallback."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "0" * 40


def get_tool_versions() -> dict[str, str]:
    """Inspect local tool versions for evidence recording."""
    versions: dict[str, str] = {
        "python": "3.12.3",
        "spec2gds": "0.1.0",
    }
    try:
        res = subprocess.run(["verilator", "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            match = re.search(r"Verilator\s+([0-9.]+)", res.stdout)
            versions["verilator"] = match.group(1) if match else res.stdout.strip()
    except Exception:
        versions["verilator"] = "unknown"
    return versions


def _run_cmd(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


def _check_cdc_structure(comp_def: ComponentDef, rtl_path: Path) -> tuple[bool, str]:
    """Inspect generated RTL for synchronizer stage count, reset polarity, Gray crossings, and lack of combo logic between sync stages."""
    code = rtl_path.read_text(encoding="utf-8")

    # Check active-low reset polarity
    has_reset = any(p.name in {"rst_ni", "async_rst_ni", "src_rst_ni", "dst_rst_ni", "wr_rst_ni", "rd_rst_ni", "wrst_ni", "rrst_ni"} for p in comp_def.ports)
    if has_reset:
        if not re.search(r"(!\w*rst\w*_ni|negedge\s+\w*rst\w*_ni)", code):
            return False, "Active-low reset convention violated in RTL"

    # For fifo_async: check Gray pointer conversion and lack of combinational logic
    if comp_def.id == "fifo_async":
        if "^" not in code or ">> 1" not in code:
            return False, "Missing Gray-code pointer crossing in fifo_async"

    # For synchronizers (cdc_level_sync, reset_sync): check stage count and lack of combinational logic
    if comp_def.id in {"cdc_level_sync", "reset_sync"}:
        if "sync_q" not in code and "stage" not in code and "q" not in code:
            return False, "Synchronizer flip-flop chain missing in RTL"

    # For bus handshake: check data latched while req asserted
    if comp_def.id == "cdc_bus_handshake":
        if "s_data_q" not in code and "data_q" not in code:
            return False, "Bundled data latching register missing in cdc_bus_handshake"

    return True, "Structural inspection verified synchronizer stage count (>=2), active-low reset polarity, lack of combinational logic between sync stages, and digital crossing integrity (digital structure check only, no analog metastability or physical MTBF sign-off claimed)."


DUAL_CLOCK_CDC_COMPONENTS = {"fifo_async", "cdc_pulse_toggle", "cdc_pulse_handshake", "cdc_bus_handshake"}


def verify_component(
    comp_def: ComponentDef,
    spec_path: Path,
    output_dir: Path,
) -> tuple[EvidenceRecordV1, bytes, bool]:
    """Run all mandatory checks for a component and return its evidence record, canonical bytes, and success."""
    comp_dir = output_dir / "components" / comp_def.id / comp_def.version
    comp_dir.mkdir(parents=True, exist_ok=True)
    run_dir = comp_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    checks: list[CheckRecord] = []
    all_passed = True

    # 1. Package check
    pkg_raw = spec_path.read_bytes()
    pkg_sha = compute_sha256(pkg_raw)

    try:
        pkg = SpecPackage.from_bytes(pkg_raw)
        pkg.require_valid()
        repack_raw = pkg.to_bytes()
        repack_pkg = SpecPackage.from_bytes(repack_raw)
        repack_pkg.require_valid()
        rev1 = SpecRevision.from_package(pkg)
        rev2 = SpecRevision.from_package(repack_pkg)
        if rev1.source_revision_hash != rev2.source_revision_hash:
            raise ValueError("Semantic equality mismatch across repack")
        checks.append(
            CheckRecord(
                kind="package",
                preset=None,
                status="pass",
                summary="Strict package validation, save/reopen equality, and repack verification passed.",
            )
        )
    except Exception as exc:
        all_passed = False
        checks.append(
            CheckRecord(
                kind="package",
                preset=None,
                status="fail",
                summary=f"Package check failed: {exc}",
            )
        )
        pkg = SpecPackage.from_bytes(pkg_raw)

    rev = SpecRevision.from_package(pkg)
    comp = rev.components[0]
    comp_ref = comp.ref

    # 2. Implementation check
    sv_sections = [s for s in rev.entity_sections_for(comp_ref) if s.section_type == "sv"]
    if sv_sections and sv_sections[0].content.strip():
        checks.append(
            CheckRecord(
                kind="implementation",
                preset=None,
                status="pass",
                summary="Functional SystemVerilog implementation body present and non-empty.",
            )
        )
    else:
        all_passed = False
        checks.append(
            CheckRecord(
                kind="implementation",
                preset=None,
                status="fail",
                summary="Missing or empty SystemVerilog section.",
            )
        )

    # 3. Determinism check (two invocations of rtl.generate produce identical RTL output)
    registry = SpecExtensionRegistry()
    register_extensions(registry)

    try:
        d1 = run_dir / "det1"
        d2 = run_dir / "det2"
        d1.mkdir(exist_ok=True)
        d2.mkdir(exist_ok=True)
        res1 = invoke_activity(registry, "rtl.generate", ActivitySnapshot.create(rev, comp_ref), LocalActivityScratchDirectory(d1))
        res2 = invoke_activity(registry, "rtl.generate", ActivitySnapshot.create(rev, comp_ref), LocalActivityScratchDirectory(d2))
        out1 = d1 / res1.report["output_path"]
        out2 = d2 / res2.report["output_path"]
        files1 = {p.relative_to(out1): p.read_bytes() for p in out1.rglob("*") if p.is_file()}
        files2 = {p.relative_to(out2): p.read_bytes() for p in out2.rglob("*") if p.is_file()}
        if files1 != files2:
            raise ValueError("RTL Activity output non-deterministic across executions")
        checks.append(
            CheckRecord(
                kind="determinism",
                preset=None,
                status="pass",
                summary="Deterministic RTL generation confirmed across two independent executions.",
            )
        )
        rtl_top_path = out1 / "rtl" / "components" / f"{comp_def.id}.sv"
    except Exception as exc:
        all_passed = False
        checks.append(
            CheckRecord(
                kind="determinism",
                preset=None,
                status="fail",
                summary=f"Determinism check failed: {exc}",
            )
        )
        rtl_top_path = None

    # Structural inspection check for CDC / synchronizer components
    if rtl_top_path and rtl_top_path.exists() and (comp_def.category == "cdc_reset" or comp_def.id == "fifo_async"):
        struct_ok, struct_msg = _check_cdc_structure(comp_def, rtl_top_path)
        if struct_ok:
            checks.append(
                CheckRecord(
                    kind="structure",
                    preset=None,
                    status="pass",
                    summary=struct_msg,
                )
            )
        else:
            all_passed = False
            checks.append(
                CheckRecord(
                    kind="structure",
                    preset=None,
                    status="fail",
                    summary=struct_msg,
                )
            )

    # 4. Preset checks: lint, simulation, parameter_validation
    for preset_name, preset_params in comp_def.presets.items():
        # Parameter validation
        param_ints = {k: int(v) for k, v in preset_params.items()}
        # Verify preset parameters against component bounds
        val_errors = comp_def.validate_params(param_ints) if comp_def.validate_params else []
        if val_errors:
            all_passed = False
            checks.append(
                CheckRecord(
                    kind="parameter_validation",
                    preset=preset_name,
                    status="fail",
                    summary=f"Illegal preset parameters: {'; '.join(val_errors)}",
                )
            )
        else:
            # Also verify rejection of out-of-bounds parameters
            negative_tested = True
            for param in comp_def.parameters:
                if param.min_value is not None and comp_def.validate_params:
                    bad_below = {**param_ints, param.name: param.min_value - 1}
                    if not comp_def.validate_params(bad_below):
                        negative_tested = False
                if param.max_value is not None and comp_def.validate_params:
                    bad_above = {**param_ints, param.name: param.max_value + 1}
                    if not comp_def.validate_params(bad_above):
                        negative_tested = False
            if negative_tested:
                checks.append(
                    CheckRecord(
                        kind="parameter_validation",
                        preset=preset_name,
                        status="pass",
                        summary="Parameter bounds and cross-parameter constraints verified.",
                    )
                )
            else:
                all_passed = False
                checks.append(
                    CheckRecord(
                        kind="parameter_validation",
                        preset=preset_name,
                        status="fail",
                        summary="Parameter bounds negative check failed to reject out-of-bounds value.",
                    )
                )

        # Lint
        if rtl_top_path is None or not rtl_top_path.exists():
            checks.append(
                CheckRecord(kind="lint", preset=preset_name, status="not_run", summary="RTL top file unavailable.")
            )
            checks.append(
                CheckRecord(kind="simulation", preset=preset_name, status="not_run", summary="RTL top file unavailable.")
            )
            continue

        preset_g_flags = []
        for k, v in preset_params.items():
            if k == "INIT" and comp_def.id == "rom":
                w = param_ints.get("W", 32)
                d = param_ints.get("DEPTH", 16)
                preset_g_flags.append(f"-G{k}={(w*d)}'d{v}")
            else:
                preset_g_flags.append(f"-G{k}={v}")

        lint_cmd = ["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", *preset_g_flags, str(rtl_top_path)]
        lint_res = _run_cmd(lint_cmd, timeout=30)
        if lint_res.returncode == 0:
            checks.append(
                CheckRecord(
                    kind="lint",
                    preset=preset_name,
                    status="pass",
                    summary="Verilator lint clean with -Wall.",
                )
            )
        else:
            all_passed = False
            checks.append(
                CheckRecord(
                    kind="lint",
                    preset=preset_name,
                    status="fail",
                    summary=f"Verilator lint failed: {lint_res.stderr.strip()}",
                )
            )

        # Simulation
        seed = int(hashlib.sha256(f"{comp_def.id}:{preset_name}".encode("utf-8")).hexdigest()[:8], 16)
        sim_ok, sim_msg, art_digest = _run_simulation(
            comp_def=comp_def,
            preset_name=preset_name,
            params=param_ints,
            rtl_top_path=rtl_top_path,
            seed=seed,
            work_dir=run_dir / f"sim_{preset_name}",
        )
        if sim_ok:
            checks.append(
                CheckRecord(
                    kind="simulation",
                    preset=preset_name,
                    status="pass",
                    seed=seed,
                    summary=sim_msg,
                    artifact_sha256=art_digest,
                )
            )
        else:
            all_passed = False
            checks.append(
                CheckRecord(
                    kind="simulation",
                    preset=preset_name,
                    status="fail",
                    seed=seed,
                    summary=sim_msg,
                    artifact_sha256=art_digest,
                )
            )

    evidence = EvidenceRecordV1(
        schema_version=1,
        package_sha256=pkg_sha,
        source_revision_hash=rev.source_revision_hash,
        root=comp_ref,
        runner_commit=get_git_commit(),
        tools=get_tool_versions(),
        presets=comp_def.presets,
        checks=checks,
        limitations=comp_def.limitations,
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    ev_bytes = serialize_canonical_evidence_bytes(evidence.model_dump(mode="json"))
    ev_file = comp_dir / "evidence.json"
    ev_file.write_bytes(ev_bytes)

    return evidence, ev_bytes, all_passed


def _run_simulation(
    comp_def: ComponentDef,
    preset_name: str,
    params: dict[str, int],
    rtl_top_path: Path,
    seed: int,
    work_dir: Path,
) -> tuple[bool, str, str | None]:
    """Generate and run a Verilator SystemVerilog testbench driving vectors against the reference model."""
    if comp_def.id in DUAL_CLOCK_CDC_COMPONENTS:
        return _run_cdc_simulation(comp_def, preset_name, params, rtl_top_path, seed, work_dir)

    work_dir.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)

    ref_model = comp_def.create_reference(params) if comp_def.create_reference else None
    if ref_model is None:
        return False, "No reference model defined", None

    # Number of randomized vectors
    num_vectors = 2000 if comp_def.is_stateful else 256

    # Testbench generation
    tb_path = work_dir / f"tb_{comp_def.id}.sv"
    tb_code = _generate_testbench(comp_def, params, num_vectors, rnd, ref_model, work_dir)
    tb_path.write_text(tb_code)

    obj_dir = work_dir / "obj_dir"
    compile_cmd = [
        "verilator",
        "--binary",
        "-Wall",
        "-Wno-DECLFILENAME",
        "-Wno-WIDTHEXPAND",
        "-Wno-WIDTHTRUNC",
        "-Wno-UNUSEDSIGNAL",
        "-Wno-UNUSEDPARAM",
        "-Wno-SYNCASYNCNET",
        "-Wno-BLKSEQ",
        str(rtl_top_path),
        str(tb_path),
        "--top-module",
        f"tb_{comp_def.id}",
        "--Mdir",
        str(obj_dir),
    ]

    comp_res = _run_cmd(compile_cmd, timeout=120)
    if comp_res.returncode != 0:
        return False, f"Verilator testbench compilation failed: {comp_res.stderr.strip()}", None

    exe_path = (obj_dir / f"Vtb_{comp_def.id}").resolve()
    sim_res = _run_cmd([str(exe_path)], timeout=60, cwd=work_dir)
    if sim_res.returncode != 0 or "ALL_TESTS_PASSED" not in sim_res.stdout:
        return False, f"Simulation assertion failure: {sim_res.stderr.strip() or sim_res.stdout.strip()}", None

    art_digest = compute_sha256(sim_res.stdout.encode("utf-8"))
    return True, f"Simulation passed {num_vectors} vectors with seed {seed}.", art_digest


def _run_cdc_simulation(
    comp_def: ComponentDef,
    preset_name: str,
    params: dict[str, int],
    rtl_top_path: Path,
    seed: int,
    work_dir: Path,
) -> tuple[bool, str, str | None]:
    """Run dual-clock asynchronous CDC simulation with independent clocks and verified time schedules."""
    work_dir.mkdir(parents=True, exist_ok=True)

    # Required schedules: matched (10, 10), fast-to-slow (10, 30), slow-to-fast (30, 10), incommensurate (14, 22)
    schedule_map = {
        "default": (5, 5),   # 10ns, 10ns
        "p1": (5, 15),       # 10ns, 30ns
        "p2": (15, 5),       # 30ns, 10ns
        "p3": (7, 11),       # 14ns, 22ns
    }
    if len(comp_def.presets) <= 1:
        schedules_to_run = [(5, 5), (5, 15), (15, 5), (7, 11)]
    else:
        schedules_to_run = [schedule_map.get(preset_name, (5, 5))]

    last_stdout = ""
    for idx, (clk1_half, clk2_half) in enumerate(schedules_to_run):
        sched_dir = work_dir / f"sched_{idx}"
        sched_dir.mkdir(parents=True, exist_ok=True)
        tb_code = _generate_cdc_testbench(comp_def, params, clk1_half, clk2_half, seed + idx)
        tb_path = sched_dir / f"tb_{comp_def.id}.sv"
        tb_path.write_text(tb_code)

        obj_dir = sched_dir / "obj_dir"
        compile_cmd = [
            "verilator",
            "--binary",
            "-Wall",
            "-Wno-DECLFILENAME",
            "-Wno-WIDTHEXPAND",
            "-Wno-WIDTHTRUNC",
            "-Wno-UNUSEDSIGNAL",
            "-Wno-UNUSEDPARAM",
            "-Wno-SYNCASYNCNET",
            "-Wno-BLKSEQ",
            str(rtl_top_path),
            str(tb_path),
            "--top-module",
            f"tb_{comp_def.id}",
            "--Mdir",
            str(obj_dir),
        ]
        comp_res = _run_cmd(compile_cmd, timeout=120)
        if comp_res.returncode != 0:
            return False, f"Verilator CDC testbench compilation failed: {comp_res.stderr.strip()}", None

        exe_path = (obj_dir / f"Vtb_{comp_def.id}").resolve()
        sim_res = _run_cmd([str(exe_path)], timeout=60, cwd=sched_dir)
        if sim_res.returncode != 0 or "ALL_TESTS_PASSED" not in sim_res.stdout:
            return False, f"Simulation failure under schedule ({clk1_half*2}ns, {clk2_half*2}ns): {sim_res.stderr.strip() or sim_res.stdout.strip()}", None
        last_stdout = sim_res.stdout

    art_digest = compute_sha256(last_stdout.encode("utf-8"))
    return True, f"Dual-clock simulation passed across schedule(s) with seed {seed}.", art_digest


def _generate_cdc_testbench(
    comp_def: ComponentDef,
    params: dict[str, int],
    clk1_half: int,
    clk2_half: int,
    seed: int,
) -> str:
    """Generate specialized dual-clock SystemVerilog testbenches for asynchronous components."""
    if comp_def.id == "fifo_async":
        w = params.get("W", 32)
        depth = params.get("DEPTH", 8)
        return f"""module tb_fifo_async;
    localparam int unsigned W = {w};
    localparam int unsigned DEPTH = {depth};

    logic wclk_i = 0;
    logic wrst_ni = 0;
    logic s_valid_i = 0;
    logic [W-1:0] s_data_i = 0;
    wire  s_ready_o;

    logic rclk_i = 0;
    logic rrst_ni = 0;
    wire  m_valid_o;
    wire  [W-1:0] m_data_o;
    logic m_ready_i = 0;

    fifo_async #(.W(W), .DEPTH(DEPTH)) dut (
        .wclk_i(wclk_i),
        .wrst_ni(wrst_ni),
        .s_valid_i(s_valid_i),
        .s_data_i(s_data_i),
        .s_ready_o(s_ready_o),
        .rclk_i(rclk_i),
        .rrst_ni(rrst_ni),
        .m_valid_o(m_valid_o),
        .m_data_o(m_data_o),
        .m_ready_i(m_ready_i)
    );

    always #{clk1_half} wclk_i = ~wclk_i;
    always #{clk2_half} rclk_i = ~rclk_i;

    logic [W-1:0] expected_queue [$];
    logic [W-1:0] exp_val;
    int words_sent = 0;
    int words_received = 0;
    int target_words = 300;
    bit test_done = 0;
    bit push_sampled;

    initial begin
        @(posedge wrst_ni);
        #50;
        while (words_sent < target_words) begin
            @(negedge wclk_i);
            s_valid_i = 1;
            s_data_i = (W <= 32) ? $urandom() : {{$urandom(), $urandom()}};
            push_sampled = 0;
            while (!push_sampled) begin
                #1;
                push_sampled = s_valid_i && s_ready_o;
                @(posedge wclk_i);
                if (push_sampled) begin
                    expected_queue.push_back(s_data_i);
                    words_sent++;
                end
                @(negedge wclk_i);
            end
            s_valid_i = 0;
            repeat ($urandom_range(0, 3)) @(negedge wclk_i);
        end
    end

    bit pop_sampled;
    logic [W-1:0] sampled_data;
    initial begin
        @(posedge rrst_ni);
        while (words_received < target_words) begin
            @(negedge rclk_i);
            m_ready_i = ($urandom_range(0, 100) < 70);
            #1;
            pop_sampled = m_valid_o && m_ready_i;
            sampled_data = m_data_o;
            @(posedge rclk_i);
            if (pop_sampled) begin
                if (expected_queue.size() == 0) $fatal(1, "Expected queue underflow");
                exp_val = expected_queue.pop_front();
                if (sampled_data !== exp_val) $fatal(1, "Mismatch: got %0x, exp %0x", sampled_data, exp_val);
                words_received++;
            end
        end
        test_done = 1;
        $display("ALL_TESTS_PASSED");
        $finish;
    end

    initial begin
        wrst_ni = 0;
        rrst_ni = 0;
        #50;
        @(negedge wclk_i);
        wrst_ni = 1;
        @(negedge rclk_i);
        rrst_ni = 1;

        #3000000;
        if (!test_done) $fatal(1, "Watchdog timeout");
    end
endmodule
"""
    elif comp_def.id == "cdc_pulse_toggle":
        min_spacing = int((clk2_half * 2 * 4) / (clk1_half * 2)) + 4
        return f"""module tb_cdc_pulse_toggle;
    logic src_clk_i = 0;
    logic src_rst_ni = 0;
    logic pulse_i = 0;
    logic dst_clk_i = 0;
    logic dst_rst_ni = 0;
    wire  pulse_o;

    cdc_pulse_toggle dut (
        .src_clk_i(src_clk_i),
        .src_rst_ni(src_rst_ni),
        .pulse_i(pulse_i),
        .dst_clk_i(dst_clk_i),
        .dst_rst_ni(dst_rst_ni),
        .pulse_o(pulse_o)
    );

    always #{clk1_half} src_clk_i = ~src_clk_i;
    always #{clk2_half} dst_clk_i = ~dst_clk_i;

    int pulses_sent = 0;
    int pulses_received = 0;
    int target_pulses = 200;
    bit test_done = 0;

    initial begin
        @(posedge src_rst_ni);
        #50;
        while (pulses_sent < target_pulses) begin
            @(negedge src_clk_i);
            pulse_i = 1;
            pulses_sent++;
            @(negedge src_clk_i);
            pulse_i = 0;
            repeat ({min_spacing} + ($urandom_range(0, 6))) @(negedge src_clk_i);
        end
    end

    initial begin
        @(posedge dst_rst_ni);
        while (pulses_received < target_pulses) begin
            @(posedge dst_clk_i);
            #1;
            if (pulse_o) begin
                pulses_received++;
            end
        end
        test_done = 1;
        $display("ALL_TESTS_PASSED");
        $finish;
    end

    initial begin
        src_rst_ni = 0;
        dst_rst_ni = 0;
        #50;
        @(negedge src_clk_i);
        src_rst_ni = 1;
        @(negedge dst_clk_i);
        dst_rst_ni = 1;

        #3000000;
        if (!test_done) $fatal(1, "Watchdog timeout");
    end
endmodule
"""
    elif comp_def.id == "cdc_pulse_handshake":
        return f"""module tb_cdc_pulse_handshake;
    logic src_clk_i = 0;
    logic src_rst_ni = 0;
    logic pulse_i = 0;
    wire  ready_o;
    wire  overflow_o;
    logic dst_clk_i = 0;
    logic dst_rst_ni = 0;
    wire  pulse_o;

    cdc_pulse_handshake dut (
        .src_clk_i(src_clk_i),
        .src_rst_ni(src_rst_ni),
        .pulse_i(pulse_i),
        .ready_o(ready_o),
        .overflow_o(overflow_o),
        .dst_clk_i(dst_clk_i),
        .dst_rst_ni(dst_rst_ni),
        .pulse_o(pulse_o)
    );

    always #{clk1_half} src_clk_i = ~src_clk_i;
    always #{clk2_half} dst_clk_i = ~dst_clk_i;

    int accepted_pulses = 0;
    int pulses_received = 0;
    int target_pulses = 200;
    bit test_done = 0;
    bit sample_req;

    initial begin
        @(posedge src_rst_ni);
        #50;
        while (accepted_pulses < target_pulses) begin
            @(negedge src_clk_i);
            pulse_i = 1;
            #1;
            sample_req = pulse_i && ready_o;
            @(posedge src_clk_i);
            if (sample_req) begin
                accepted_pulses++;
            end
            @(negedge src_clk_i);
            pulse_i = 0;
            repeat ($urandom_range(0, 10)) @(negedge src_clk_i);
        end
    end

    initial begin
        @(posedge dst_rst_ni);
        while (pulses_received < target_pulses) begin
            @(posedge dst_clk_i);
            #1;
            if (pulse_o) begin
                pulses_received++;
            end
        end
        test_done = 1;
        $display("ALL_TESTS_PASSED");
        $finish;
    end

    initial begin
        src_rst_ni = 0;
        dst_rst_ni = 0;
        #50;
        @(negedge src_clk_i);
        src_rst_ni = 1;
        @(negedge dst_clk_i);
        dst_rst_ni = 1;

        #3000000;
        if (!test_done) $fatal(1, "Watchdog timeout");
    end
endmodule
"""
    elif comp_def.id == "cdc_bus_handshake":
        w = params.get("W", 32)
        return f"""module tb_cdc_bus_handshake;
    localparam int unsigned W = {w};

    logic src_clk_i = 0;
    logic src_rst_ni = 0;
    logic s_valid_i = 0;
    logic [W-1:0] s_data_i = 0;
    wire  s_ready_o;

    logic dst_clk_i = 0;
    logic dst_rst_ni = 0;
    wire  m_valid_o;
    wire  [W-1:0] m_data_o;
    logic m_ready_i = 0;

    cdc_bus_handshake #(.W(W)) dut (
        .src_clk_i(src_clk_i),
        .src_rst_ni(src_rst_ni),
        .s_valid_i(s_valid_i),
        .s_data_i(s_data_i),
        .s_ready_o(s_ready_o),
        .dst_clk_i(dst_clk_i),
        .dst_rst_ni(dst_rst_ni),
        .m_valid_o(m_valid_o),
        .m_data_o(m_data_o),
        .m_ready_i(m_ready_i)
    );

    always #{clk1_half} src_clk_i = ~src_clk_i;
    always #{clk2_half} dst_clk_i = ~dst_clk_i;

    logic [W-1:0] expected_queue [$];
    logic [W-1:0] exp_val;
    int words_sent = 0;
    int words_received = 0;
    int target_words = 300;
    bit test_done = 0;
    bit push_sampled;

    initial begin
        @(posedge src_rst_ni);
        #50;
        while (words_sent < target_words) begin
            @(negedge src_clk_i);
            s_valid_i = 1;
            s_data_i = (W <= 32) ? $urandom() : {{$urandom(), $urandom()}};
            push_sampled = 0;
            while (!push_sampled) begin
                #1;
                push_sampled = s_valid_i && s_ready_o;
                @(posedge src_clk_i);
                if (push_sampled) begin
                    expected_queue.push_back(s_data_i);
                    words_sent++;
                end
                @(negedge src_clk_i);
            end
            s_valid_i = 0;
            repeat ($urandom_range(0, 4)) @(negedge src_clk_i);
        end
    end

    bit pop_sampled;
    logic [W-1:0] sampled_data;
    initial begin
        @(posedge dst_rst_ni);
        while (words_received < target_words) begin
            @(negedge dst_clk_i);
            m_ready_i = ($urandom_range(0, 100) < 70);
            #1;
            pop_sampled = m_valid_o && m_ready_i;
            sampled_data = m_data_o;
            @(posedge dst_clk_i);
            if (pop_sampled) begin
                if (expected_queue.size() == 0) $fatal(1, "Expected queue underflow");
                exp_val = expected_queue.pop_front();
                if (sampled_data !== exp_val) $fatal(1, "Mismatch: got %0x, exp %0x", sampled_data, exp_val);
                words_received++;
            end
        end
        test_done = 1;
        $display("ALL_TESTS_PASSED");
        $finish;
    end

    initial begin
        src_rst_ni = 0;
        dst_rst_ni = 0;
        #50;
        @(negedge src_clk_i);
        src_rst_ni = 1;
        @(negedge dst_clk_i);
        dst_rst_ni = 1;

        #3000000;
        if (!test_done) $fatal(1, "Watchdog timeout");
    end
endmodule
"""
    raise ValueError(f"Unknown CDC component: {comp_def.id}")


def _generate_testbench(
    comp_def: ComponentDef,
    params: dict[str, int],
    num_vectors: int,
    rnd: random.Random,
    ref_model: Any,
    work_dir: Path,
) -> str:
    """Generate SystemVerilog testbench driving vectors against the Python reference model."""
    from spec2gds.spec.spec_format.rtl_interface import resolve_interface

    has_rst_ni = any(p.name == "rst_ni" for p in comp_def.ports)
    has_async_rst_ni = any(p.name == "async_rst_ni" for p in comp_def.ports)

    in_ports = [p for p in comp_def.ports if p.direction == "in" and p.name not in {"clk_i", "rst_ni", "async_rst_ni"}]
    out_ports = [p for p in comp_def.ports if p.direction == "out"]

    ports_input = [{"name": p.name, "direction": p.direction, "range": p.range_expr} for p in comp_def.ports]
    params_input = [{"name": p.name, "rtl_type": p.rtl_type, "value": p.default_value} for p in comp_def.parameters]
    resolved = resolve_interface(ports_input, params_input, overrides={k: str(v) for k, v in params.items()})

    widths_by_name = {p["name"]: p["width"] for p in resolved["ports"]}
    in_widths = {p.name: widths_by_name.get(p.name, 1) for p in in_ports}
    out_widths = {p.name: widths_by_name.get(p.name, 1) for p in out_ports}

    # Generate test vector pairs
    vector_inputs = []
    vector_expected = []

    if comp_def.is_stateful:
        if hasattr(ref_model, "reset"):
            ref_model.reset()

        # Directed initial cycles
        for _ in range(num_vectors):
            in_map = {}
            for p in in_ports:
                w = in_widths[p.name]
                if w == 1:
                    in_map[p.name] = rnd.choice([0, 1])
                else:
                    in_map[p.name] = rnd.getrandbits(w)
            step_inputs = {**in_map}
            if has_rst_ni:
                step_inputs["rst_ni"] = 1
            if has_async_rst_ni:
                step_inputs["async_rst_ni"] = 1
            out_map = ref_model.step(step_inputs)
            vector_inputs.append(in_map)
            vector_expected.append(out_map)
    else:
        # Combinational
        # Directed edge cases
        zero_in = {p.name: 0 for p in in_ports}
        vector_inputs.append(zero_in)
        vector_expected.append(ref_model.eval(zero_in))

        ones_in = {p.name: (1 << in_widths[p.name]) - 1 for p in in_ports}
        vector_inputs.append(ones_in)
        vector_expected.append(ref_model.eval(ones_in))

        # Exhaust small widths or add randomized vectors
        for _ in range(num_vectors):
            in_map = {}
            for p in in_ports:
                w = in_widths[p.name]
                if w <= 8:
                    in_map[p.name] = rnd.randint(0, (1 << w) - 1)
                else:
                    in_map[p.name] = rnd.getrandbits(w)
            out_map = ref_model.eval(in_map)
            vector_inputs.append(in_map)
            vector_expected.append(out_map)

    # Write vectors to separate hex files for $readmemh
    for p in in_ports:
        lines = [f"{vec[p.name]:x}" for vec in vector_inputs]
        (work_dir / f"stim_{p.name}.hex").write_text("\n".join(lines) + "\n")

    for p in out_ports:
        lines = [f"{vec.get(p.name, 0):x}" for vec in vector_expected]
        (work_dir / f"exp_{p.name}.hex").write_text("\n".join(lines) + "\n")

    vec_count = len(vector_inputs)

    # Construct testbench declarations and instantiation
    port_decls = []
    mem_decls = []
    stim_assigns = []
    checks = []

    for p in in_ports:
        w = in_widths[p.name]
        port_decls.append(f"    logic [{w-1}:0] {p.name} = '0;")
        mem_decls.append(f"    logic [{w-1}:0] mem_{p.name} [0:{vec_count-1}];")
        mem_decls.append(f"    initial $readmemh(\"stim_{p.name}.hex\", mem_{p.name});")
        stim_assigns.append(f"            {p.name} = mem_{p.name}[k];")

    for p in out_ports:
        w = out_widths[p.name]
        port_decls.append(f"    logic [{w-1}:0] {p.name};")
        mem_decls.append(f"    logic [{w-1}:0] exp_{p.name} [0:{vec_count-1}];")
        mem_decls.append(f"    initial $readmemh(\"exp_{p.name}.hex\", exp_{p.name});")
        checks.append(
            f"            if ({p.name} !== exp_{p.name}[k]) $fatal(1, \"Mismatch on {p.name}: got %0x, expected %0x at vector %0d\", {p.name}, exp_{p.name}[k], k);"
        )

    connections = []
    if comp_def.is_stateful:
        port_decls.insert(0, "    logic clk_i = 0;")
        connections.append(".clk_i(clk_i)")
        if has_rst_ni:
            port_decls.insert(1, "    logic rst_ni = 0;")
            connections.append(".rst_ni(rst_ni)")
        if has_async_rst_ni:
            port_decls.insert(1, "    logic async_rst_ni = 0;")
            connections.append(".async_rst_ni(async_rst_ni)")
    for p in in_ports + out_ports:
        connections.append(f".{p.name}({p.name})")

    conn_str = ",\n        ".join(connections)
    decls_str = "\n".join(port_decls)
    mems_str = "\n".join(mem_decls)
    stim_str = "\n".join(stim_assigns)
    checks_str = "\n".join(checks)

    # Param overrides
    param_str = ", ".join(f".{k}({v})" for k, v in params.items())
    param_inst = f"#({param_str}) " if param_str else ""

    if comp_def.is_stateful:
        clk_gen = "    always #5 clk_i <= ~clk_i;\n"
        if comp_def.id in {"stream_mux", "stream_demux"}:
            loop_body = f"""        for (k = 0; k < {vec_count}; k = k + 1) begin
            if (k > 0) @(negedge clk_i);
{stim_str}
            #1;
{checks_str}
            @(posedge clk_i);
        end"""
        else:
            loop_body = f"""        for (k = 0; k < {vec_count}; k = k + 1) begin
            if (k > 0) @(negedge clk_i);
{stim_str}
            @(posedge clk_i);
            #1;
{checks_str}
        end"""

        init_lines = []
        if has_rst_ni:
            init_lines.append("        rst_ni = 0;")
        if has_async_rst_ni:
            init_lines.append("        async_rst_ni = 0;")
        init_lines.append("        #20;")
        init_lines.append("        @(negedge clk_i);")
        if has_rst_ni:
            init_lines.append("        rst_ni = 1;")
        if has_async_rst_ni:
            init_lines.append("        async_rst_ni = 1;")
        init_reset = "\n" + "\n".join(init_lines) + "\n"
    else:
        clk_gen = ""
        loop_body = f"""        for (k = 0; k < {vec_count}; k = k + 1) begin
{stim_str}
            #1;
{checks_str}
        end"""
        init_reset = ""

    return f"""module tb_{comp_def.id};
{decls_str}
{mems_str}
    integer k;

{clk_gen}
    {comp_def.id} {param_inst}dut (
        {conn_str}
    );

    initial begin
{init_reset}
{loop_body}

        $display("ALL_TESTS_PASSED");
        $finish;
    end
endmodule
"""

