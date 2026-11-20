# Development Guide

This document defines repository organization, build commands, service configuration, logging, and test execution for spec2hw.

The product is named **spec2hw**. The repository is named `spec2gds`.
Existing imports, packages, commands, environment variables, service paths,
schemas, saved data, and release profiles retain their `spec2gds` identifiers.

## 1. Repository Organization

```text
spec2gds/spec/spec_format/    .spec package model, SpecIR, transactions, Spec API
spec2gds/spec/activities/     Activity SDK, snapshots, Activities, contracts
spec2gds/spec/importers/      PDF, Word, and ODT document importers
circuit-designer/schema/      Canonical Circuit Designer JSON Schema
circuit-designer/packages/    Core models, layout engine, React canvas, and app shell
circuit-designer/apps/        Spec Editor and standalone Circuit Designer applications
ai-assistant/                 DeepSeek Harness assistant product and UI
ai-assistant/production/      Production lockfiles (spec2gds-web and spec2gds-headless)
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
| **Verification Planner** | `6016` | `6016` | Standalone verification planning and reference generation |

### Address precedence and launch options

Use **command line → configuration file → defaults** for all listeners.
Select a file with `--service-config PATH`; omitted fields use the packaged
shared defaults. Network environment settings have no effect. Credential,
storage, and logging environment settings keep their existing rules.

```bash
scripts/serve-all.sh start --service-config config/services.json --public-host design-host.example
uv run spec2gds-server --service-config config/services.json --port 6420
npm --prefix circuit-designer run dev -- --service-config "$PWD/config/services.json" --port 6421 --ui-port 6422
npm --prefix circuit-designer run dev:editor -- --service-config "$PWD/config/services.json" --port 6425
npm --prefix ai-assistant run dev -- --service-config "$PWD/config/services.json" --port 6423 --no-open
uv run verification-planner --service-config config/services.json
uv run spec2gds-log-viewer --service-config config/services.json --no-open
```

Individual listeners also accept `--host` and `--public-host`. The combined
launcher accepts `--host`, `--public-host`, `--spec-port`, `--circuit-port`,
`--circuit-ui-port`, and `--assistant-port`. Circuit Designer's combined command
uses `--ui-host`/`--ui-port` for its separate UI. Vite development and preview
adapters consume product options before forwarding other arguments to Vite.
Assistant adapters do the same before invoking the Harness.

Concrete endpoint hosts control their advertised URLs. Wildcard listeners use
the public host for browser URLs and matching loopback addresses for probes and
proxies. `auto` selects the preferred outbound IPv4 address or the hostname.
Verification Planner keeps its default loopback bind. Shared service/UI
listeners must agree in the configuration. Python reload workers read an
importable per-run factory; endpoints are never transported in environment
variables. Snapshots resolve relative storage paths before they are saved.

The combined launcher starts only Spec Editor, Circuit Designer, and AI
Assistant. `temp/TEMP_serve-all/` contains resolved snapshots, process identities,
group IDs, effective endpoints, and logs. Stop and restart affect only recorded
process groups. Untracked conflicts are reported with their address, port, and
PID. A configuration change does not expand the stop target list.

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
Install Python packages and build Node workspaces. Harness archives are included in the repository; no GitHub package token is required:

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
# Routine deterministic checks
scripts/test-all.sh fast

# Short browser checks and live model checks
scripts/test-all.sh browser-smoke
scripts/test-all.sh live-smoke

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

### Spec Catalog service

Run `uv sync --all-packages` after updating the workspace. The `spec_catalog` service entry defines the listener (port 6017), catalog root, and state directory. `serve-all` starts and checks this service. Its CLI commands and HTTP prefix use catalog names; see [the service guide](../spec_catalog_service/README.md).
