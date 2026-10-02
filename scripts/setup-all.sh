#!/usr/bin/env bash
# ==============================================================================
# spec2gds Unified Development Setup Script
#
# Sets up the complete spec2gds development environment:
# 1. Root Python workspace (Spec Editor server & runtime via uv)
# 2. Circuit Designer workspace (npm dependencies, build & Playwright browsers)
# 3. DeepSeek Harness (DSH) source checkout, dependencies & build
# 4. AI Assistant workspace (npm dependencies & production bundles)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Configuration defaults (can be overridden via environment variables)
DSH_REPO="${DSH_REPO:-git@github.com:ankdesh/deepseek-harness.git}"
DSH_REPO_HTTPS="${DSH_REPO_HTTPS:-https://github.com/ankdesh/deepseek-harness.git}"
DSH_BRANCH="${DSH_BRANCH:-spec2gds/integration}"
DEFAULT_HARNESS_DIR="$(cd -- "${PROJECT_ROOT}/.." && pwd)/deepseek-harness"
HARNESS_SOURCE="${HARNESS_SOURCE:-${DEFAULT_HARNESS_DIR}}"
# Interpret relative destinations from the repository root, before changing cwd.
if [[ "${HARNESS_SOURCE}" != /* ]]; then
  HARNESS_SOURCE="${PROJECT_ROOT}/${HARNESS_SOURCE}"
fi

echo "================================================================="
echo " spec2gds Full Development Setup"
echo " Project root:   ${PROJECT_ROOT}"
echo " DSH source:     ${HARNESS_SOURCE}"
echo " DSH repository: ${DSH_REPO}"
echo " DSH branch:     ${DSH_BRANCH}"
echo "================================================================="

# --- Step 0: Ensure Node.js and Package Manager Prerequisites ---
echo ""
echo ">>> [0/4] Checking Node.js environment..."
if [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
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

# Ensure pnpm is available (required for DeepSeek Harness)
if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is not found in PATH; installing pnpm via npm..."
  npm install -g pnpm@11.7.0 || true
fi

# --- Step 1: Root Python Workspace (Spec Editor Server) ---
echo ""
echo ">>> [1/4] Setting up root Python workspace (uv sync)..."
cd "${PROJECT_ROOT}"
if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required for Python dependency management. Please install uv." >&2
  exit 1
fi
uv sync
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

# --- Step 3: DeepSeek Harness (DSH) Setup ---
echo ""
echo ">>> [3/4] Setting up DeepSeek Harness (DSH)..."

# Resolve actual DSH directory (handling potential nested checkout)
RESOLVED_DSH="${HARNESS_SOURCE}"
if [[ -f "${HARNESS_SOURCE}/scripts/product-runtime.mjs" ]]; then
  RESOLVED_DSH="${HARNESS_SOURCE}"
elif [[ -f "${HARNESS_SOURCE}/deepseek-harness/scripts/product-runtime.mjs" ]]; then
  RESOLVED_DSH="${HARNESS_SOURCE}/deepseek-harness"
elif [[ -d "${HARNESS_SOURCE}/deepseek-harness/.git" ]]; then
  RESOLVED_DSH="${HARNESS_SOURCE}/deepseek-harness"
fi

if [[ ! -d "${RESOLVED_DSH}/.git" ]]; then
  echo "Cloning DeepSeek Harness from ${DSH_REPO} into ${RESOLVED_DSH}..."
  mkdir -p "$(dirname "${RESOLVED_DSH}")"
  if ! git clone -b "${DSH_BRANCH}" "${DSH_REPO}" "${RESOLVED_DSH}" 2>/dev/null; then
    echo "SSH clone of branch ${DSH_BRANCH} failed; attempting HTTPS clone..."
    if ! git clone -b "${DSH_BRANCH}" "${DSH_REPO_HTTPS}" "${RESOLVED_DSH}" 2>/dev/null; then
      echo "Branch ${DSH_BRANCH} not found on remote; cloning default branch..."
      git clone "${DSH_REPO_HTTPS}" "${RESOLVED_DSH}"
    fi
  fi
else
  echo "Existing DeepSeek Harness repository found at ${RESOLVED_DSH}."
  # Try checking out requested branch if available
  if git -C "${RESOLVED_DSH}" rev-parse --verify "${DSH_BRANCH}" >/dev/null 2>&1; then
    echo "Switching to branch ${DSH_BRANCH}..."
    git -C "${RESOLVED_DSH}" checkout "${DSH_BRANCH}"
  elif git -C "${RESOLVED_DSH}" rev-parse --verify "origin/${DSH_BRANCH}" >/dev/null 2>&1; then
    echo "Checking out tracking branch origin/${DSH_BRANCH}..."
    git -C "${RESOLVED_DSH}" checkout -b "${DSH_BRANCH}" "origin/${DSH_BRANCH}"
  fi
fi

# Persist the physical checkout path, including after resolving a nested clone.
RESOLVED_DSH="$(cd -- "${RESOLVED_DSH}" && pwd -P)"

# Install dependencies and build DSH
echo "Installing DSH dependencies and building in ${RESOLVED_DSH}..."
cd "${RESOLVED_DSH}"
pnpm install --frozen-lockfile || pnpm install
pnpm run build
echo "DeepSeek Harness build completed."

# --- Step 4: AI Assistant Workspace ---
echo ""
echo ">>> [4/4] Setting up AI Assistant..."
cd "${PROJECT_ROOT}/ai-assistant"

# Refresh local packages/tooling and preserve other settings in ai-assistant/.env.
node scripts/link-harness.mjs "${RESOLVED_DSH}"

# Compile server and client bundles
npm run build
echo "AI Assistant setup completed."

echo ""
echo "================================================================="
echo " spec2gds setup completed successfully!"
echo ""
echo " To start all services, run:"
echo "   scripts/serve-all.sh start"
echo ""
echo " To run UI automation tests, run:"
echo "   tests/ui-scenarios/run-test.sh"
echo "================================================================="
