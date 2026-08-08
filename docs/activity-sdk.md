# Activity SDK

The Activity SDK is the supported Python interface for teams that analyze a
specification, generate code, run tools, or format selected information for an
LLM. It is deliberately independent of how work is queued, launched, stored,
or monitored.

## Terminology and lifecycle

An **Activity** is registered Python logic. An **Activity Snapshot** is its
complete immutable Spec input. An **Activity Result** contains its report,
artifacts, and optional review-gated source proposals. Host-owned run status is
not part of any of these contracts.

```text
SpecRevision -> ActivitySnapshot -> ActivityContext -> Activity -> ActivityResult
```

Activity definitions contain no command, process, HTTP, database, queue, or
workspace settings. A future in-process runner, child-process runner, or
independent Activity service can invoke the same plugin unchanged.

## Two-level read API

`context.spec.high` is the preferred stable API for most plugins:

```python
components = context.spec.high.entities(kind="component")
dma = components.where(name="dma").one()
dependencies = context.spec.high.related(dma.ref, "dependencies")
usages = context.spec.high.related(dma.ref, "usages")
intent = context.spec.high.text.linked_to(dma.ref).plain_text()
```

High-level queries are deterministic, iterable, and immutable. They expose
common entity identity, relationships, and narrative text without requiring
knowledge of concrete IP-XACT types.

`context.spec.low` provides more detailed typed access:

```python
for component in context.spec.low.components:
    for port in component.ports:
        print(component.vlnv, port.name, port.style)

design = context.spec.low.resolve(design_ref)
connections = context.spec.low.connections(design_ref)
```

The low-level API returns concrete immutable SpecIR values. It does not expose
raw XML, mutable package files, `save()`, `to_package()`, or transaction APIs.
Use it when generic queries do not contain enough hardware detail.

## Define an Activity

The function decorator is the shortest authoring path:

```python
import pydantic

from spec2gds.agent_spec.activities import (
    ActivityContext,
    ActivityResult,
    ActivityScopes,
    activity,
)


class Report(pydantic.BaseModel):
    component_count: int


@activity(
    activity_id="acme.component_summary",
    version="1.0.0",
    title="Component summary",
    description="Write a compact component inventory.",
    scopes=ActivityScopes(document=True, entity_kinds=("component",)),
    report_model=Report,
    artifact_roles=("inventory.text",),
)
def summarize(context: ActivityContext) -> ActivityResult:
    components = context.spec.high.entities(kind="component").all()
    artifact = context.outputs.add_text(
        role="inventory.text",
        name="components.txt",
        text="\n".join(item.name for item in components),
    )
    return ActivityResult(
        summary=f"Found {len(components)} components.",
        report=Report(component_count=len(components)).model_dump(mode="json"),
        artifacts=(artifact,),
    )
```

Subclass `BaseActivity` when an Activity needs its own availability check or
additional private helper methods. `ActivityDefinition` declares document or
entity scope, report schema, artifact roles, and proposal permission. Per-run
user input and earlier Activity artifacts are not inputs in v1.

The output writer constructs validated, portable artifacts from bytes, text,
JSON, files, or a deterministically zipped directory. Plugins declare semantic
roles; the eventual host chooses durable storage and artifact IDs.

## Source proposals

An Activity cannot mutate SpecIR. An Activity that declares
`may_propose_changes=True` may return `SpecChangeProposalDraft` objects with a
rationale and typed public Spec operations. The host attaches snapshot and
Activity provenance, previews the operations against the current source hash,
and requires explicit Accept or Reject. Reports and artifacts do not require
approval.

## Register extensions

One plugin module can register Activities and Context Renderers:

```python
def register(registry):
    registry.register_activity(summarize)
    registry.register_context_renderer(MyContextRenderer())
```

Deployments load explicit `module:callable` paths with
`load_extension_modules()`. Registration is atomic per module. Invalid imports,
definitions, duplicate IDs, or schema mismatches disable that module and
produce visible `ExtensionDiagnostic` records; valid plugins remain available.

Context Renderers use the same snapshot and read APIs but return deterministic
`RenderedContext` text rather than creating Activity runs. This is the intended
replacement boundary for consumer-specific LLM context formatting.

## Test a plugin

Use `ActivityTestHarness` with a small fixture revision and a
`SpecExtensionRegistry`. Its `snapshot()`, `invoke()`, and `render()` methods
are direct contract checks, not a scheduling decision: they validate
availability, report schemas, artifact roles, source references, proposal
permissions, and returned provenance. The underlying `invoke_activity()` and
`render_context()` functions are also public for focused tests.

The repository examples live in
`spec2gds.agent_spec.activities.reference`. Contract tests are in
`tests/agent_spec/activities/`.
