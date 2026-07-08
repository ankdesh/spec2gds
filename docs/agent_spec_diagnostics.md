# Agent-Spec Diagnostics and Sanitization

The editor presents a focused view of a `.spec` document. The diagnostic CLI is
the lower-level tool for debugging package, metadata, and payload issues that
are not visible in the UI.

## Inspect A Document

Run:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli inspect \
  --container benchmarks/agent_spec/hw_docs/generated/apb_timer.spec \
  --format text
```

For scriptable output, omit `--format text`:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli inspect \
  --container benchmarks/agent_spec/hw_docs/generated/apb_timer.spec
```

The JSON report includes:

- filesystem size and SHA-256 hash
- ZIP package parts, sizes, compression mode, and mimetype placement
- manifest registrations and missing `spec_data/` manifest entries
- custom payload paths, media types, sizes, hashes, and JSON parse previews
- existing verifier results for embedded payloads and `spec://` links
- semantic document blocks, headings, links, tables, images, and diagnostics
- editor relations, section-version groups, and IP-XACT heading attachments
- IP-XACT component/interface/port-map summaries and protocol diagnostics
- persisted agent-spec manifest, graph, versions, runs, events, writebacks,
  artifacts, and checkpoints

Use `--output report.json` to save a report for diffing or attaching to an
issue.

## Sanitize A Document

Sanitization is intentionally conservative. It does not invent bus interfaces,
rewrite IP-XACT XML, modify document prose, or change action/run semantics.

It can:

- add missing `xml:id` values to headings
- add missing manifest registrations for files that already exist under
  `spec_data/`
- re-save the package so the office-compatible mimetype ZIP entry is first and
  uncompressed

Write a repaired copy:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli sanitize \
  --container broken.spec \
  --output repaired.spec
```

Preview intended actions without writing:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli sanitize \
  --container broken.spec \
  --output repaired.spec \
  --dry-run
```

Rewrite the source only when you already have a backup or version-control diff:

```bash
PYTHONPATH=. UV_CACHE_DIR=.uv-cache uv run python -m spec2gds.agent_spec.package.cli sanitize \
  --container broken.spec \
  --in-place
```

## Relationship To Validate

`validate` answers whether registered payloads and `spec://` links pass the
current plugin checks.

`inspect` answers what is inside the document, even when some of it is invalid.

`sanitize` applies safe structural repairs only. Protocol-level fixes, such as
correcting IP-XACT bus interfaces, should be made in the source XML or
benchmark builder so the protocol remains intact.
