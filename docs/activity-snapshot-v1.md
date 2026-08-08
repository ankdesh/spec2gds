# Activity Snapshot v1

An Activity Snapshot is the immutable, portable input boundary for Python
Activities and Context Renderers. It captures one complete source revision;
extension code never reads the live Spec session.

## Container

The snapshot media type is
`application/vnd.spec2gds.activity-snapshot.v1+zip`. The deterministic ZIP has
exactly three entries in this order:

```text
mimetype
snapshot.json
source/source.spec
```

`mimetype` is stored without compression. The other entries use deterministic
ZIP timestamps, permissions, ordering, and compression settings.

`source/source.spec` is a complete, valid source-only `.spec` package. It
contains IP-XACT documents, typed narrative, assets, and accepted annotations.
Files below `activity/` are removed before serialization. This prevents old
execution state from becoming an Activity input or changing snapshot identity.

## Manifest

`snapshot.json` uses schema `spec2gds.activity-snapshot.v1`:

```json
{
  "schema_version": "spec2gds.activity-snapshot.v1",
  "snapshot_id": "sha256:...",
  "source": {
    "document_id": "soc",
    "source_revision_hash": "sha256:...",
    "package_path": "source/source.spec",
    "package_sha256": "sha256:..."
  },
  "scope": {
    "kind": "entity",
    "target": {
      "document_id": "soc",
      "entity_kind": "design",
      "entity_id": "design_top"
    }
  },
  "dependency_closure": []
}
```

Document scope uses `kind=document` and `target=null`. Entity scope names one
stable `EntityRef`. The full source package is included for both scopes; the
target is an invocation and navigation scope, not a data-pruning rule.

The snapshot ID hashes the canonical manifest identity fields: schema, source
identity and package digest, scope, target, and dependency closure. Run IDs,
timestamps, queue settings, executor commands, and storage locations are not
part of the format.

## Validation

`ActivitySnapshot.from_bytes()` fails closed unless:

- the ZIP entry set, order, mimetype, and compression rule are correct;
- the embedded package digest matches the manifest;
- the embedded `.spec` validates normally and contains no Activity history;
- document ID and source revision hash match the embedded source;
- an entity target resolves in that revision;
- the dependency closure recomputed from SpecIR matches the manifest; and
- the snapshot ID matches the canonical manifest identity.

The snapshot can therefore be stored, cached by `snapshot_id`, transferred to
another process, or replayed without depending on a live editor. A future host
may reuse a content-addressed snapshot instead of rebuilding it, without
changing the format or Activity API.

## Python API

```python
from spec2gds.agent_spec.activities import ActivitySnapshot

snapshot = ActivitySnapshot.create(revision, target=design.ref)
encoded = snapshot.to_bytes()
restored = ActivitySnapshot.from_bytes(encoded)

assert restored.manifest.snapshot_id == snapshot.manifest.snapshot_id
assert restored.revision.source_revision_hash == revision.source_revision_hash
```

Activities should use the read APIs described in
[Activity SDK](activity-sdk.md), not `snapshot.revision` directly. The revision
is retained on the snapshot so a host can construct those controlled views and
validate returned references.
