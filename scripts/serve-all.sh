#!/usr/bin/env bash

set -u

if [[ -f "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  source "${HOME}/.nvm/nvm.sh"
  nvm use 24 >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${PROJECT_ROOT}/logs/serve-all"

SERVICES=(spec-editor circuit-designer ai-assistant)
DEFAULT_PORTS=(6010 6011 6012 6013 6014)

usage() {
  echo "Usage: scripts/serve-all.sh {start|restart|stop}"
}

pid_file() {
  echo "${STATE_DIR}/$1.pid"
}

log_file() {
  echo "${STATE_DIR}/$1.log"
}

public_host() {
  if [[ -n "${SPEC2GDS_PUBLIC_HOST:-}" && "${SPEC2GDS_PUBLIC_HOST}" != "auto" ]]; then
    echo "${SPEC2GDS_PUBLIC_HOST}"
    return
  fi
  local address
  address="$(hostname -I 2>/dev/null | awk '{print $1}')"
  echo "${address:-$(hostname)}"
}

tracked_pid() {
  local file
  file="$(pid_file "$1")"
  if [[ -f "${file}" ]]; then
    tr -d '[:space:]' < "${file}"
  fi
}

is_running() {
  local pid
  pid="$(tracked_pid "$1")"
  [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null
}

start_service() {
  local name="$1"
  local workdir="$2"
  shift 2

  if is_running "${name}"; then
    echo "${name} is already running (PID $(tracked_pid "${name}"))."
    return 0
  fi

  rm -f "$(pid_file "${name}")"
  : > "$(log_file "${name}")"

  (
    cd -- "${workdir}" || exit 1
    exec setsid "$@"
  ) >> "$(log_file "${name}")" 2>&1 &

  local pid=$!
  echo "${pid}" > "$(pid_file "${name}")"
  echo "Started ${name} (PID ${pid}); log: $(log_file "${name}")"
}

assert_clean_start() {
  local running=0
  local name
  for name in "${SERVICES[@]}"; do
    if is_running "${name}"; then
      running=$((running + 1))
    fi
  done

  if [[ ${running} -eq ${#SERVICES[@]} ]]; then
    echo "The spec2gds stack is already running. Use 'scripts/serve-all.sh restart' after rebuilding or changing source." >&2
    return 2
  fi
  if [[ ${running} -ne 0 ]]; then
    echo "Only ${running} of ${#SERVICES[@]} tracked services are running. Use 'scripts/serve-all.sh restart' to recover a consistent stack." >&2
    return 1
  fi

  if ! command -v lsof >/dev/null 2>&1; then
    echo "lsof is required to verify that the default ports are available." >&2
    return 1
  fi
  local occupied=()
  local port
  for port in "${DEFAULT_PORTS[@]}"; do
    if lsof -nP -t -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      occupied+=("${port}")
    fi
  done
  if [[ ${#occupied[@]} -ne 0 ]]; then
    echo "Cannot start: untracked listeners already own default port(s) ${occupied[*]}. Use 'scripts/serve-all.sh restart' to replace the stale stack." >&2
    return 1
  fi
}

stop_service() {
  local name="$1"
  local pid
  pid="$(tracked_pid "${name}")"

  if [[ ! "${pid}" =~ ^[0-9]+$ ]]; then
    rm -f "$(pid_file "${name}")"
    echo "${name} is not tracked."
    return 0
  fi

  if ! kill -0 "${pid}" 2>/dev/null; then
    rm -f "$(pid_file "${name}")"
    echo "${name} is already stopped."
    return 0
  fi

  # Each service is started in its own process group. Signal the group so npm
  # and uv child processes are stopped along with the tracked launcher.
  kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true

  local attempt
  for attempt in {1..50}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  if kill -0 "${pid}" 2>/dev/null; then
    kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null || true
  fi
  rm -f "$(pid_file "${name}")"
  echo "Stopped ${name}."
}

start_all() {
  command -v uv >/dev/null 2>&1 || { echo "uv is required." >&2; return 1; }
  command -v node >/dev/null 2>&1 || { echo "Node.js is required." >&2; return 1; }
  command -v npm >/dev/null 2>&1 || { echo "npm is required." >&2; return 1; }
  command -v setsid >/dev/null 2>&1 || { echo "setsid is required." >&2; return 1; }
  node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 19) ? 0 : 1)' || {
    echo "AI Assistant requires Node.js 22.19 or newer (Node.js 24 LTS is recommended)." >&2
    return 1
  }

  assert_clean_start
  local startable=$?
  [[ ${startable} -eq 2 ]] && return 0
  [[ ${startable} -eq 0 ]] || return 1

  mkdir -p "${STATE_DIR}"

  # Resolve auto once and export it so Python, Node, and printed browser URLs
  # all advertise the same interface on multi-homed development machines.
  if [[ -z "${SPEC2GDS_PUBLIC_HOST:-}" || "${SPEC2GDS_PUBLIC_HOST}" == "auto" ]]; then
    export SPEC2GDS_PUBLIC_HOST="$(public_host)"
  fi
  # The combined product explicitly opts Circuit Designer into the legacy
  # shared directory. Independent Circuit Designer launches do not need it.
  export SPEC2GDS_SERVICE_CONFIG="${SPEC2GDS_SERVICE_CONFIG:-${PROJECT_ROOT}/config/services.json}"

  start_service "spec-editor" "${PROJECT_ROOT}" uv run spec2gds-server
  start_service "circuit-designer" "${PROJECT_ROOT}/circuit-designer" npm run dev
  start_service "ai-assistant" "${PROJECT_ROOT}/ai-assistant" npm run dev -- --no-open

  # Catch immediate failures such as missing dependencies or occupied ports.
  sleep 3
  local failed=0
  local name
  for name in "${SERVICES[@]}"; do
    if ! is_running "${name}"; then
      echo "${name} failed to start; see $(log_file "${name}")." >&2
      failed=1
    fi
  done
  if [[ ${failed} -ne 0 ]]; then
    stop_tracked_services
    return 1
  fi

  local advertised_host
  advertised_host="$(public_host)"
  echo "Spec Editor:      http://${advertised_host}:6010/editor"
  echo "Circuit Designer: http://${advertised_host}:6012"
  echo "AI Assistant:     http://${advertised_host}:6013"
}

stop_tracked_services() {
  local name
  for name in "${SERVICES[@]}"; do
    stop_service "${name}"
  done
}

stop_default_port_listeners() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "lsof is not available; cannot check for untracked service listeners." >&2
    return 1
  fi

  local -A targets=()
  local port pid
  for port in "${DEFAULT_PORTS[@]}"; do
    while IFS= read -r pid; do
      if [[ "${pid}" =~ ^[0-9]+$ ]]; then
        targets["${pid}"]="${targets["${pid}"]:-}${port} "
      fi
    done < <(lsof -nP -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null)
  done

  if [[ ${#targets[@]} -eq 0 ]]; then
    echo "No services are listening on the default ports."
    return 0
  fi

  for pid in "${!targets[@]}"; do
    echo "Stopping PID ${pid} listening on port(s) ${targets["${pid}"]% }."
    kill -TERM "${pid}" 2>/dev/null || true
  done

  local attempt running
  for attempt in {1..50}; do
    running=0
    for pid in "${!targets[@]}"; do
      if kill -0 "${pid}" 2>/dev/null; then
        running=1
        break
      fi
    done
    [[ ${running} -eq 0 ]] && break
    sleep 0.1
  done

  for pid in "${!targets[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      echo "PID ${pid} did not stop gracefully; forcing it to stop."
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  done
}

stop_all() {
  mkdir -p "${STATE_DIR}"
  stop_tracked_services
  stop_default_port_listeners
}

restart_all() {
  stop_all
  start_all
}

case "${1:-}" in
  start)
    start_all
    ;;
  restart)
    restart_all
    ;;
  stop)
    stop_all
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
