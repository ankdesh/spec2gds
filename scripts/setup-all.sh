#!/usr/bin/env bash
# ==============================================================================
# spec2hw Unified Development Setup Script
#
# Sets up the complete spec2hw development environment:
# 1. Root Python workspace (Spec Editor server & runtime via uv)
# 2. Circuit Designer workspace (npm dependencies, build & Playwright browsers)
# 3. AI Assistant packages from repository archives
# 4. AI Assistant server and browser builds
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

echo "Setting up spec2hw from locked application and Harness packages."

# --- Step 0: Ensure Node.js and Package Manager Prerequisites ---
echo ""
echo ">>> [0/4] Checking Node.js environment..."
if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 24 || (major === 24 && minor >= 2) || (major === 22 && minor >= 19) ? 0 : 1)' 2>/dev/null && [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
  # Load nvm if available
  # shellcheck source=/dev/null
  source "${HOME}/.nvm/nvm.sh"
  nvm use 24 >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true
fi

NODE_VERSION="$(node -v 2>/dev/null || echo "none")"
if [[ "${NODE_VERSION}" == "none" ]]; then
  echo "Error: Node.js is required but not installed." >&2
  exit 1
fi
echo "Using Node.js ${NODE_VERSION}"

# --- Step 1: Root Python Workspace (Spec Editor Server) ---
echo ""
echo ">>> [1/4] Setting up root Python workspace (uv sync)..."
cd "${PROJECT_ROOT}"
if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required for Python dependency management. Please install uv." >&2
  exit 1
fi
uv sync --all-packages
echo "Python workspace synced successfully."

# --- Step 2: Circuit Designer Workspace ---
echo ""
echo ">>> [2/4] Setting up Circuit Designer..."
cd "${PROJECT_ROOT}/circuit-designer"
npm install
npm run build --if-present

# Install Playwright browser binaries for UI automation testing
echo "Ensuring Playwright Chromium browser binary is installed..."
PLAYWRIGHT_BROWSERS_PATH="${PROJECT_ROOT}/circuit-designer/.playwright-browsers" \
  npx playwright install chromium

echo "Circuit Designer setup completed."

# --- Step 3: AI Assistant packages ---
echo ">>> Installing AI Assistant dependencies from repository archives..."
cd "${PROJECT_ROOT}/ai-assistant"
npm run install:packages

# Compile server and client bundles
npm run build
echo "AI Assistant setup completed."

echo ""
echo "================================================================="
echo " spec2hw setup completed successfully!"
echo ""
echo " To start all services, run:"
echo "   scripts/serve-all.sh start"
echo ""
echo " To run UI automation tests, run:"
echo "   tests/ui-scenarios/run-test.sh"
echo "================================================================="
