#!/usr/bin/env bash
# Run complementary test tiers; preserve the existing per-project full suites.
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

tier="fundamental"
dry_run=false
browser_tests=true
if [[ "${1:-}" == fundamental || "${1:-}" == extensive || "${1:-}" == all ]]; then
  tier="$1"
  shift
fi
for option in "$@"; do
  case "${option}" in
    --dry-run) dry_run=true ;;
    --no-browser) browser_tests=false ;;
    --help|-h)
      cat <<'HELP'
Usage: scripts/test-all.sh [fundamental|extensive|all] [--no-browser] [--dry-run]

fundamental (default): fast Python and all Circuit/Assistant unit/API tests.
extensive: remaining Python toolchain/CLI tests, Harness integration and browser tests.
all: both tiers, without repeating the fundamental tests.

--no-browser: leave browser suites to their existing dedicated commands.
--dry-run: print commands without building or running tests.

Run scripts/setup-all.sh first. Extensive requires Verilator 5.x and GNU Make;
optional SystemC/CIRCT tests keep their existing configuration-based skips.
No model API key is required. See docs/development.md for prerequisites and scope.
HELP
      exit 0 ;;
    *) echo "Unknown argument: ${option}. Use --help." >&2; exit 2 ;;
  esac
done

failed_checks=()
started_at=$SECONDS
run_check() {
  local label="$1" result
  shift
  printf '\n>>> %s\n' "${label}"
  printf '    '
  printf '%q ' "$@"
  printf '\n'
  if "${dry_run}"; then return 0; fi
  if "$@"; then return 0; else result=$?; fi
  failed_checks+=("${label} (exit ${result})")
  return "${result}"
}

run_fundamental() {
  run_check "Python fundamentals" uv run --no-sync python -m pytest -q --strict-markers \
    tests testplan-service/tests -m 'not extensive' || true
  run_check "Circuit Designer units" npm --prefix circuit-designer test || true
  run_check "Assistant units" npm --prefix ai-assistant test || true
}

run_extensive() {
  local assistant_ready=false
  # CLI and Harness checks consume built Assistant code.
  if run_check "Build Assistant" npm --prefix ai-assistant run build; then
    assistant_ready=true
    run_check "Python extensive" uv run --no-sync python -m pytest -q --strict-markers \
      tests testplan-service/tests -m extensive || true
    run_check "Harness integration" npm --prefix ai-assistant run test:harness || true
  else
    echo "Skipping dependent Python/Assistant checks because the Assistant build failed." >&2
  fi
  if "${browser_tests}"; then
    if run_check "Build Circuit Designer and editor" npm --prefix circuit-designer run build; then
      run_check "Circuit Designer browser" npm --prefix circuit-designer run test:e2e || true
      run_check "Spec Editor browser" npm --prefix circuit-designer run test:e2e:editor || true
      # Reuse the React/Playwright dependencies and Chromium installed by setup.
      if "${assistant_ready}"; then
        run_check "Assistant browser" env \
          "AI_ASSISTANT_UI_TEST_DEPS=${AI_ASSISTANT_UI_TEST_DEPS:-${ASSISTANT_UI_TEST_DEPS:-${PROJECT_ROOT}/circuit-designer}}" \
          "PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-${PROJECT_ROOT}/circuit-designer/.playwright-browsers}" \
          npm --prefix ai-assistant run test:ui || true
      fi
    else
      echo "Skipping browser checks because the frontend build failed." >&2
    fi
  fi
}

if [[ "${tier}" == fundamental || "${tier}" == all ]]; then run_fundamental; fi
if [[ "${tier}" == extensive || "${tier}" == all ]]; then run_extensive; fi

if (( ${#failed_checks[@]} )); then
  printf '\nFailed checks:\n'
  printf '  - %s\n' "${failed_checks[@]}"
  exit 1
fi
if "${dry_run}"; then
  printf '\nDry run complete; no checks executed.\n'
else
  printf '\n%s tier passed in %s seconds.\n' "${tier}" "$((SECONDS - started_at))"
fi
