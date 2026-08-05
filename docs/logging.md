# Unified logging

Spec Editor, Circuit Designer, AI Assistant, their browser clients, and the
Log Viewer share one newline-delimited JSON file. Logging is intentionally off
by default so ordinary editor use performs no file writes.

## Enable logging

The tracked defaults live in `config/services.json`. Environment variables may
override only the switch and detail level:

```bash
export SPEC2GDS_LOGGING=ON
export SPEC2GDS_LOG_LEVEL=info   # or debug
```

Restart each service after changing these values. Every process must use the
same `SPEC2GDS_SERVICE_CONFIG` registry so it resolves the same log path.

Info mode records a concise line for lifecycle events, HTTP outcomes, document
operations, assistant workflows, warnings, and errors. Debug mode enriches
those records with validated parameters and results at system boundaries. The
Assistant captures the redacted OpenAI request immediately before the owned SDK
call and the returned object immediately afterward; it does not intercept SDK
internals.

Authorization values, cookies, API keys, passwords, secrets, and tokens are
masked recursively. Binary and base64 content is replaced by its size and
SHA-256 digest. Debug logs still contain specification text and conversations,
so treat the file as private project data.

## Retention and concurrent writers

The configured `logging.file` is the only log file. Python and Node writers use
the same short-lived lock file while appending. When the active file would
exceed `logging.max_bytes`, the writer atomically replaces it with the newest
complete JSONL records that fit. No rotated backup files are created.

Logging failures are isolated from editor behavior. A persistent write failure
is reported once to stderr, after which user operations continue normally.

## Browser viewer

Start the read-only loopback viewer:

```bash
uv run spec2gds-log-viewer
# In WSL or a headless shell:
uv run spec2gds-log-viewer --no-open
```

The default URL is <http://127.0.0.1:4300>. Filter by application, component,
severity, correlation ID, or arbitrary text. New records arrive live. Select a
row to inspect its complete structured data. Debug, Info, Warning, and Error
rows use purple, blue, amber, and red accents respectively, with visible text
labels so meaning never depends on color alone.

The viewer never clears or modifies the log and refuses non-loopback binding.
