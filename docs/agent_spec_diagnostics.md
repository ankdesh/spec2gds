# Agent-Spec V1 Diagnostics

Diagnostics are explicit evidence that a package, semantic graph, edit, or
artifact cannot be trusted. V1 rejects invalid source rather than repairing or
silently interpreting it.

## Validate a Package

```bash
uv run python -m spec2gds.agent_spec.spec_format.cli validate \
  --container spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec
```

Successful output includes `valid: true` and the source hash. Invalid input
prints an error to stderr and exits with status `2`.

Inspect the manifest and canonical paths with:

```bash
uv run python -m spec2gds.agent_spec.spec_format.cli inspect \
  --container spec2gds/agent_spec/spec_format/samples/generated/v1_demo.spec \
  --format text
```

## Diagnostic Layers

### Package structure

Detects unsafe paths, duplicate entries, missing required files, wrong media
type/order/compression, unexpected top-level content, and manifest/file-set
mismatches.

### Persisted models

Detects unknown JSON fields, invalid IDs, unsafe paths, duplicate document or
block identities, unsupported versions, invalid narrative shapes, and invalid
manifest relationships.

### Content integrity

Detects missing source documents/assets and SHA-256 mismatches.

### IP-XACT

Detects unsafe or malformed XML, XSD errors, root-kind mismatch, missing or
invalid VLNV/entity identity, and elements outside the V1 profile.

### Semantic graph

Detects unresolved instances, ports, interfaces, bus or abstraction types,
incompatible endpoints, duplicate names, self-connections, component
composition cycles, internal-design boundary errors, and invalid narrative
references.

### Transaction

Detects stale source hashes, unknown operation targets, invalid reorder sets,
unsafe insertion positions, dangling deletes, and any invalid complete
candidate revision. Failed transactions never partially commit.

### Action and artifact

Detects invalid action inputs, target/precondition mismatch, timeouts, non-zero
executor exits, malformed completions, report-schema failures, undeclared
artifact roles, missing outputs, hash/size mismatch, invalid provenance,
unselected parents, missing sidecar bytes, and sidecar corruption.

### Proposal

Detects stale proposal bases, unsupported proposal operations, already-reviewed
proposals, and candidate validation failures.

## API Behavior

| Condition | Status |
| --- | --- |
| No active document | `400` |
| Unknown entity/execution/artifact | `404` |
| Stale expected source revision | `409` |
| Invalid package, request, transaction, action, artifact, or proposal | `422` |

`GET /diagnostics` separates source diagnostics from artifact-sidecar
diagnostics. The editor shows both domains and does not hide source health
behind artifact warnings.

## No Sanitizer

V1 has no automatic package sanitizer. If source is invalid, fix the source or
recreate it through typed APIs. This preserves deterministic behavior and avoids
guessing at hardware intent.

## Debugging Sequence

1. Run CLI validation.
2. Inspect the package manifest and paths.
3. Open it through the API and inspect `/diagnostics`.
4. For an edit, compare the expected and current source hashes.
5. For an action, inspect execution diagnostics and the executor report.
6. For an artifact, inspect lineage and verify sidecar availability.
7. Reproduce with the focused test under `tests/agent_spec/spec_format/`.
