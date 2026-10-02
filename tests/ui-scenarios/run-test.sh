#!/usr/bin/env bash
set -euo pipefail
SCENARIO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_DIR="$(cd -- "${SCENARIO_DIR}/../.." && pwd)"

if [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.nvm/nvm.sh"
  nvm use 24 >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true
fi

# The runner starts isolated services, and only stops its own process groups.
cd "${SCENARIO_DIR}"
export PLAYWRIGHT_BROWSERS_PATH="${REPOSITORY_DIR}/circuit-designer/.playwright-browsers"

if [[ "$*" == *"--rtllm"* ]]; then
  RTLLM_ARGS=()
  for arg in "$@"; do
    if [[ "${arg}" != "--rtllm" ]]; then
      RTLLM_ARGS+=("${arg}")
    fi
  done
  exec npm run test:rtllm -- ${RTLLM_ARGS[@]+"${RTLLM_ARGS[@]}"}
elif [[ "$*" == *"--all"* ]]; then
  SCENARIOS=("automatic" "restricted" "live" "binding" "repeated")
  EXTRA_ARGS=()
  for arg in "$@"; do
    if [[ "${arg}" != "--all" ]]; then
      EXTRA_ARGS+=("${arg}")
    fi
  done
  for s in "${SCENARIOS[@]}"; do
    echo "===================================================="
    echo "Running UI scenario: ${s}"
    echo "===================================================="
    npm test -- --scenario "${s}" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
  done
  echo "===================================================="
  echo "All ${#SCENARIOS[@]} UI scenarios passed successfully!"
  echo "===================================================="
else
  exec npm test -- "$@"
fi
