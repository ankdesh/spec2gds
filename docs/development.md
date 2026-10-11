# Development Guide

This document defines repository organization, build commands, service configuration, logging, and test execution for `spec2gds`.

## 1. Repository Organization

```text
spec2gds/spec/spec_format/    .spec package model, SpecIR, transactions, Spec API
spec2gds/spec/activities/     Activity SDK, snapshots, generators, contracts
spec2gds/spec/importers/      PDF, Word, and ODT document importers
circuit-designer/schema/      Canonical Circuit Designer JSON Schema
circuit-designer/packages/    Core models, layout engine, React canvas, and app shell
circuit-designer/apps/        Spec Editor and standalone Circuit Designer applications
ai-assistant/                 DeepSeek Harness assistant product and UI
testplan-service/             Verification Planner service, domain, and static UI
config/services.json          Shared service registry and port configuration
tests/                        Automated tests across all subsystems
docs/                         Living technical documentation
```

---

## 2. Shared Service Configuration

The platform defines default bind addresses and ports in [`config/services.json`](../config/services.json).

### Port and Service Map

| Application | Service Port | UI Port | Purpose |
| --- | --- | --- | --- |
| **Spec Editor** | `6010` | `6010` (or `6015` in dev) | Specification authoring and IP-XACT transactions |
| **Circuit Designer** | `6011` | `6012` | Schematic layout, routing, and canvas interaction |
| **AI Assistant** | `6013` | `6013` | DeepSeek Harness conversation shell and flows |
| **Log Viewer** | `6014` | `6014` | Real-time structured log viewer |
| **Verification Planner** | `6016` | `6016` | Standalone verification planning and reference generator |

### Host Binding and Public Address
- **Bind Address**: Backend services bind to `0.0.0.0` by default to enable local intranet access.
- **Public Host**: Defaults to auto-detected local IPv4. Set `SPEC2GDS_PUBLIC_HOST` to specify an explicit IP or hostname:
  ```bash
  export SPEC2GDS_PUBLIC_HOST="192.168.1.50"
  ```

---

## 3. Unified Logging System

All subsystems share one newline-delimited JSON log file configured in `config/services.json`.
Logging is disabled by default during development.

### Enable Logging
Set environment variables before starting services:

```bash
export SPEC2GDS_LOGGING=ON
export SPEC2GDS_LOG_LEVEL=info   # Options: info, debug
```

- **Info Mode**: Records lifecycle events, HTTP requests, document transactions, and errors.
- **Debug Mode**: Enriches records with parameter payloads, diffs, and redacted model calls.
- **Security**: Tokens, passwords, cookies, and secret keys are masked automatically.

### Start the Log Viewer
Start the read-only web log viewer:

```bash
uv run spec2gds-log-viewer
# In headless environments:
uv run spec2gds-log-viewer --no-open
```
Open `http://<SERVER_IP>:6014` to inspect and filter live events.

---

## 4. Environment Setup and Service Launcher

### Complete First-Time Setup
Install Python packages and build Node workspaces:

```bash
scripts/setup-all.sh
```

### Combined Launcher
Manage the combined services with `scripts/serve-all.sh`:

```bash
# Start all services
scripts/serve-all.sh start

# Restart running services after code modifications
scripts/serve-all.sh restart

# Stop all background services
scripts/serve-all.sh stop
```

---

## 5. Testing and Validation Strategy

Follow the testing guidelines in [Software Testing Strategy](testing-strategy.md).

```bash
# Fast test suite (Python units, frontend units, and live checks)
scripts/test-all.sh fast

# Integration test suite for specific scopes
scripts/test-all.sh integration --scope spec,assistant

# Full regression test suite
scripts/test-all.sh regression
```

### Subsystem Unit Tests
```bash
# Run Python backend tests
uv run python -m pytest tests/spec -q

# Run Verification Planner tests
uv run python -m pytest testplan-service/tests -q

# Run Circuit Designer tests
npm --prefix circuit-designer test

# Run AI Assistant tests
npm --prefix ai-assistant test
```

---

## 6. Contribution Rules

1. Follow canonical terminology in [TERMINOLOGY.md](TERMINOLOGY.md).
2. Maintain one primary class per file.
3. Every mutation must cross a revision-checked boundary.
4. Separate connectivity from layout geometry.
5. Update documentation immediately when architecture, APIs, or commands change.
