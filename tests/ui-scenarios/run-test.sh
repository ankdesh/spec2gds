#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

# Ensure Node 24 is active
if [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
  source "${HOME}/.nvm/nvm.sh"
  nvm use 24
fi

echo "=== UI Automation Test Execution ==="
echo "Project root: ${PROJECT_ROOT}"

# Ensure isolated harness source is configured
export HARNESS_SOURCE="${HARNESS_SOURCE:-/home/ankdesh/explore/deepseek-harness/deepseek-harness}"

# Function to clean up services on exit
cleanup() {
  local exit_code=$?
  echo "Shutting down spec2gds services..."
  "${PROJECT_ROOT}/scripts/serve-all.sh" stop || true
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

# Start services
echo "Starting spec2gds services..."
"${PROJECT_ROOT}/scripts/serve-all.sh" start

echo "Waiting for services to be ready..."
for i in {1..30}; do
  if curl -s "http://127.0.0.1:6010/health" >/dev/null 2>&1 && curl -s "http://127.0.0.1:6013/healthz" >/dev/null 2>&1; then
    echo "Services are ready!"
    break
  fi
  sleep 1
done

# Run the Playwright scenario runner
echo "Running UI test scenario..."
cd "${PROJECT_ROOT}/circuit-designer"
PLAYWRIGHT_BROWSERS_PATH="${PROJECT_ROOT}/circuit-designer/.playwright-browsers" \
NODE_PATH="${PROJECT_ROOT}/circuit-designer/node_modules" \
npx --yes tsx "${PROJECT_ROOT}/tests/ui-scenarios/runner/run_scenario.ts"
