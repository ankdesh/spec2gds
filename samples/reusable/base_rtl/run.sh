#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v verilator >/dev/null || { echo "Verilator 5+ is required." >&2; exit 1; }

# Keep generated C++ and binaries outside the source tree; preserve evidence.
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/spec2gds-reusable.XXXXXX")"
echo "Simulation evidence: ${build_dir}"
sources=(pwm_channel.sv rgb_led.sv dual_rgb_panel.sv)
verilator --lint-only --Wall --top-module dual_rgb_panel \
  "${sources[@]}" 2>&1 | tee "${build_dir}/lint.log"
verilator --binary --timing --Wall --timescale 1ns/1ps \
  --top-module tb_dual_rgb_panel --Mdir "${build_dir}/obj" \
  "${sources[@]}" tb_dual_rgb_panel.sv > "${build_dir}/build.log" 2>&1 || {
    cat "${build_dir}/build.log" >&2
    exit 1
  }
"${build_dir}/obj/Vtb_dual_rgb_panel" | tee "${build_dir}/simulation.log"
