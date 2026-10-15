#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

trace=true
case "${1:-}" in
  --no-trace) trace=false; shift ;;
  '') ;;
  *) echo "Usage: $0 [--no-trace]" >&2; exit 2 ;;
esac
if (( $# )); then echo "Usage: $0 [--no-trace]" >&2; exit 2; fi
command -v verilator >/dev/null || { echo 'Verilator 5+ is required.' >&2; exit 1; }
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/spec2gds-riscv5.XXXXXX")"
echo "Simulation evidence: ${build_dir}"
sources=(rtl/common/*.sv rtl/core/*.sv rtl/pipe/*.sv rtl/riscv5_top.sv)
# Unconsumed fields in the pipeline/trace records are intentional.
flags=(--Wall -Wno-UNUSEDSIGNAL +incdir+rtl --timescale 1ns/1ps)
verilator --lint-only "${flags[@]}" --top-module riscv5_top \
  "${sources[@]}" 2>&1 | tee "${build_dir}/lint.log"
trace_flags=()
if "$trace"; then trace_flags=(--trace); fi
for top in tb_units tb_riscv5_top; do
  verilator --binary --timing "${flags[@]}" "${trace_flags[@]}" \
    --top-module "$top" --Mdir "${build_dir}/${top}" \
    "${sources[@]}" "tb/${top}.sv" > "${build_dir}/${top}.build.log" 2>&1 || {
      cat "${build_dir}/${top}.build.log" >&2
      exit 1
    }
  run_args=()
  if "$trace" && [[ "$top" == tb_riscv5_top ]]; then
    run_args=("+trace=${build_dir}/riscv5.vcd")
  fi
  "${build_dir}/${top}/V${top}" "${run_args[@]}" | tee "${build_dir}/${top}.log"
done
