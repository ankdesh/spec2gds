"""Portable functional evaluation of generated projects using real Verilator runs.

Use --project for an already generated (including UI-launched) activity project;
--spec explicitly generates a separate evaluation project. Each stage is reported
independently. Live inference quality is assessed separately from these fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[1] / "tests/evaluation/rtl"


def load_cases(root: Path = FIXTURES) -> dict[str, dict[str, Any]]:
    manifest = json.loads((root / "cases.json").read_text())
    if manifest.get("schema_version") != "spec2gds.rtl-evaluation.v1":
        raise ValueError("Unsupported evaluation manifest.")
    return {case["id"]: case for case in manifest["cases"]}


def _run(command: list[str], cwd: Path, log: Path, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False
        )
        log.write_text(result.stdout + result.stderr)
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "log": str(log),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write_text(str(exc))
        return {
            "status": "unverified" if isinstance(exc, OSError) else "failed",
            "reason": str(exc),
            "log": str(log),
        }


def evaluate_project(
    project: Path,
    case: dict[str, Any],
    output: Path,
    *,
    fixtures: Path = FIXTURES,
    expected_revision: str | None = None,
    benchmark_root: Path | None = None,
) -> dict[str, Any]:
    """Check published inventory, lint, compile and simulate without regenerating."""
    project = project.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "case": case["id"],
        "project": str(project),
        "configuration": case["configuration"],
        "generation": {"status": "failed"},
        "lint": {"status": "unverified"},
        "compilation": {"status": "unverified"},
        "simulation": {"status": "unverified"},
        "bench_adaptation": case["bench_adaptation"],
        "inference_quality": "unverified",
    }
    try:
        manifest = json.loads((project / "generation-manifest.json").read_text())
        if manifest.get("schema_version") not in {
            "spec2gds.rtl-generation.v2",
            "spec2gds.rtl-generation.v3",
        }:
            raise ValueError("Unsupported generated manifest.")
        if expected_revision and manifest.get("source_revision_hash") != expected_revision:
            raise ValueError(
                "The published activity project belongs to a different source revision."
            )
        for entry in manifest["files"]:
            path = (project / entry["path"]).resolve()
            if (
                not path.is_relative_to(project)
                or not path.is_file()
                or (project / entry["path"]).is_symlink()
            ):
                raise ValueError("Missing or unsafe generated inventory path.")
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise ValueError(f"Published file hash mismatch: {entry['path']}")
        report["generation"] = {
            "status": "passed",
            "source_revision_hash": manifest["source_revision_hash"],
            "target": manifest.get("target", manifest.get("design")),
            "implementation_status": manifest.get("implementation_status", {}),
        }
        if benchmark_root:
            references = json.loads((fixtures / "cases.json").read_text())[
                "external_benchmark_references"
            ]
            relative = references.get(case["family"])
            if relative:
                reference = benchmark_root.resolve() / relative
                if not reference.is_dir() or not (reference / "testbench.v").is_file():
                    raise ValueError(f"External benchmark fixture missing: {reference}")
                report["external_benchmark"] = {
                    "root": str(reference),
                    "original_testbench_sha256": "sha256:"
                    + hashlib.sha256((reference / "testbench.v").read_bytes()).hexdigest(),
                    "adaptation": case["bench_adaptation"],
                    "original_parameterized_compatibility": "unverified",
                }
        verilator = shutil.which("verilator")
        if not verilator:
            report["lint"] = {"status": "unverified", "reason": "Verilator is not installed."}
            return report
        top = manifest["top_module"]
        report["lint"] = _run(
            [
                verilator,
                "--lint-only",
                "--timing",
                "-Wno-fatal",
                "--top-module",
                top,
                "-F",
                "rtl/files.f",
            ],
            project,
            output / "lint.log",
            60,
        )
        if report["lint"]["status"] != "passed":
            return report
        bench = (fixtures / case["bench"]).read_text().replace("@@TOP@@", top)
        for name, value in case["configuration"].items():
            bench = bench.replace(f"@@{name.upper()}@@", str(value))
        bench_path = output / "evaluation_tb.sv"
        bench_path.write_text(bench)
        objects = output / "obj"
        report["compilation"] = _run(
            [
                verilator,
                "--binary",
                "--timing",
                "--assert",
                "-Wno-fatal",
                "-j",
                "1",
                "--top-module",
                "evaluation_tb",
                "--Mdir",
                str(objects),
                "-o",
                "evaluation-bin",
                "-F",
                "rtl/files.f",
                str(bench_path),
            ],
            project,
            output / "compilation.log",
            120,
        )
        if report["compilation"]["status"] != "passed":
            return report
        report["simulation"] = _run(
            [str(objects / "evaluation-bin")], project, output / "simulation.log", 30
        )
        if (
            report["simulation"]["status"] == "passed"
            and "EVALUATION_PASS" not in (output / "simulation.log").read_text()
        ):
            report["simulation"] = {
                **report["simulation"],
                "status": "failed",
                "reason": "Self-checking bench did not reach successful completion.",
            }
        return report
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["generation"] = {"status": "failed", "reason": str(exc)}
        return report
    finally:
        (output / "evaluation-report.json").write_text(json.dumps(report, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--case", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path)
    source.add_argument("--spec", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--source-revision")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path)
    args = parser.parse_args()
    try:
        case = load_cases(args.fixtures)[args.case]
    except KeyError:
        parser.error("Unknown evaluation case.")
    project = args.project
    if args.spec:
        from scripts.run_rtl_activity import select_target
        from spec2gds.agent_spec.activities import (
            ActivitySnapshot,
            LocalActivityWorkspace,
            SpecExtensionRegistry,
            invoke_activity,
        )
        from spec2gds.agent_spec.activities.rtl import register_extensions
        from spec2gds.agent_spec.spec_format.ir import SpecRevision

        revision = SpecRevision.load(str(args.spec))
        target = select_target(revision, args.target)
        registry = SpecExtensionRegistry()
        register_extensions(registry)
        result = invoke_activity(
            registry,
            "rtl.generate",
            ActivitySnapshot.create(revision, target.ref),
            LocalActivityWorkspace(args.output.resolve() / "generated"),
        )
        project = args.output.resolve() / "generated" / result.report["output_path"]
    result = evaluate_project(
        project,
        case,
        args.output,
        fixtures=args.fixtures,
        expected_revision=args.source_revision,
        benchmark_root=args.benchmark_root,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["simulation"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
