#!/usr/bin/env bash
set -euo pipefail
SCENARIO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_DIR="$(cd -- "${SCENARIO_DIR}/../.." && pwd)"
# The runner starts isolated services, and only stops its own process groups.
cd "${SCENARIO_DIR}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${REPOSITORY_DIR}/circuit-designer/.playwright-browsers}"
exec npm test -- "$@"
