# V1.2 SpecIR and Atomic Edits

V1.2 adds the source-only in-memory representation for the deterministic V1
package. `SpecRevision` loads a validated package into immutable semantic
objects for components, designs, bus definitions, abstraction definitions,
narrative blocks, assets, and accepted annotations.

It deliberately does not contain action history, reports, generated artifacts,
or implementation-specific SystemC/RTL state. Those arrive in later plans.

## Load and Query

```python
from spec2gds.agent_spec.spec_format import SpecRevision

revision = SpecRevision.load("design.spec")
top_designs = revision.entry_designs()
top = top_designs[0]

for instance in revision.instances(top):
    component = revision.document_by_vlnv("component", instance.component_vlnv)
    print(instance.name, component.vlnv)

closure = revision.dependency_closure(top)
```

The primary semantic query methods are `resolve`, `document_by_vlnv`,
`entry_designs`, `internal_design`, `instances`, `interfaces`, `connections`,
`narrative_blocks_for`, and `dependency_closure`. They use the stable source
IDs and VLNVs defined by V1.1, never mutable XML nodes.

`manifest` and `narrative` return defensive typed copies. Modifying a returned
object does not alter the loaded revision.

## Atomic Transactions

Edits are grouped in a `SpecEditTransaction` and tied to the source hash that
was loaded. The transaction uses a private package copy, validates every
operation together, and returns either a new revision or diagnostics. The
original revision is unchanged in both cases.

```python
from spec2gds.agent_spec.spec_format.ir import InstanceIR
from spec2gds.agent_spec.spec_format.transactions import (
    SpecEditTransaction,
    UpsertInstance,
)

transaction = SpecEditTransaction(
    base_source_revision_hash=revision.source_revision_hash,
    operations=(
        UpsertInstance(top.ref, InstanceIR("leaf2", "spec2gds.example:demo:leaf:1.0")),
    ),
)
result = transaction.apply(revision)
if not result.succeeded:
    raise RuntimeError(result.diagnostics)
next_revision = result.revision
```

The supported V1.2 operations cover profiled document upsert/delete; instance
and connection upsert/delete/reorder; composition and entry-design updates;
narrative block/link updates and reordering; and source asset add/remove. A
document upsert is the typed boundary for component, port, interface, bus, and
abstraction field edits: the supplied IP-XACT XML must pass the V1 profile.

## Validation Boundary

In addition to V1.1 archive/XSD/profile checks, a revision validates embedded
component references, component-composition cycles, internal design boundaries,
instance and connection names, port and interface endpoint existence, bus and
abstraction compatibility, and narrative entity links. A stale source hash or
any failed check rejects the entire transaction.

Run the V1.1 and V1.2 package tests with:

```bash
uv run python -m pytest tests/agent_spec/spec_format -q
```

The detailed intended boundary and exit gate remain in
[V1.2 — SpecIR, Semantic Queries, and Edit Validation](pivot/v1_02_spec_ir_and_validation.md).
