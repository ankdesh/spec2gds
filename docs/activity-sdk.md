# Activity SDK

The Activity SDK provides the Python extension interface to analyze hardware specifications, generate code, and produce verification artifacts.
The SDK remains completely independent of queueing, process management, and HTTP hosting.

```mermaid
flowchart LR
    Rev["SpecRevision"] --> Snap["Activity Snapshot v1"]
    Snap --> Ctx["ActivityContext"]
    Ctx --> Act["Activity Plugin"]
    Act --> Res["Activity Result"]
    Res --> Rep["Reports & Artifacts"]
    Res --> Prop["Typed Source Proposals"]
```

## 1. Core Concepts and Architecture

- **Activity**: A registered Python function or class that performs analysis or code generation.
- **Job**: An execution instance of an Activity with concrete parameters.
- **Activity Snapshot**: An immutable, portable ZIP container capturing one complete `.spec` source revision.
- **Activity Context**: The runtime execution interface providing read-only access to specification data.
- **Activity Result**: The immutable output containing markdown reports, output artifacts, and optional typed source proposals.

Activity code never receives mutable `.spec` packages or live editor sessions.
Any source changes return as typed proposals that require designer review and revision validation.

---

## 2. Activity Snapshot v1 Container Specification

An Activity Snapshot is the portable input boundary for Activities and Context Renderers.
The container media type is `application/vnd.spec2gds.activity-snapshot.v1+zip`.

The deterministic ZIP contains exactly three entries in order:
```text
mimetype
snapshot.json
source/source.spec
```

- `mimetype`: Uncompressed file containing the exact media type string.
- `source/source.spec`: Complete, valid, source-only `.spec` container without execution history.
- `snapshot.json`: Manifest adhering to `spec2gds.activity-snapshot.v1`:

```json
{
  "schema_version": "spec2gds.activity-snapshot.v1",
  "snapshot_id": "sha256:...",
  "source": {
    "document_id": "soc_top",
    "source_revision_hash": "sha256:...",
    "package_path": "source/source.spec",
    "package_sha256": "sha256:..."
  },
  "scope": {
    "kind": "entity",
    "target": {
      "document_id": "soc_top",
      "entity_kind": "design",
      "entity_id": "main_design"
    }
  },
  "dependency_closure": []
}
```

The `snapshot_id` hashes the canonical manifest fields.
Timestamps and host paths are excluded to guarantee deterministic snapshot hashes.

---

## 3. Two-Level Read API

The `ActivityContext` exposes two distinct read interfaces:

### High-Level API (`context.spec.high`)
Use `context.spec.high` for general hardware analysis and LLM prompt rendering:

```python
# Query entities by kind
components = context.spec.high.entities(kind="component")
dma = components.where(name="dma").one()

# Query graph relationships
dependencies = context.spec.high.related(dma.ref, "dependencies")
usages = context.spec.high.related(dma.ref, "usages")

# Read narrative documentation
intent = context.spec.high.text.linked_to(dma.ref).plain_text()
```

High-level queries are deterministic, iterable, and immutable.

### Low-Level API (`context.spec.low`)
Use `context.spec.low` when detailed IP-XACT hardware models or exact port layouts are required:

```python
for component in context.spec.low.components:
    for port in component.ports:
        print(component.vlnv, port.name, port.direction, port.width)

# Resolve design topology and netlist connections
design = context.spec.low.resolve(design_ref)
connections = context.spec.low.connections(design_ref)
```

The low-level API returns concrete immutable `SpecIR` objects.
It never exposes raw XML or mutable write handles.

---

## 4. Define and Register an Activity

Use the `@activity` decorator to register an Activity function:

```python
from pydantic import BaseModel
from spec2gds.spec.activities import activity, ActivityContext, ActivityResult

class LintParams(BaseModel):
    strict: bool = True

@activity(
    id="hardware.lint",
    title="Hardware Spec Linter",
    description="Validates port conventions and naming rules.",
    version="1.0.0",
    params_model=LintParams,
)
def run_linter(context: ActivityContext, params: LintParams) -> ActivityResult:
    warnings = []
    for component in context.spec.low.components:
        if not component.ports:
            warnings.append(f"Component {component.name} has no ports defined.")
            
    return ActivityResult(
        summary=f"Lint completed with {len(warnings)} warnings.",
        report_markdown="\n".join(f"- {w}" for w in warnings) if warnings else "Clean.",
    )
```

---

## 5. Execution Rules and Determinism

- **No Network / Process Side Effects**: Activities must be pure deterministic functions of their snapshot and inputs.
- **Scratch Directory**: Use `context.scratch_dir` for temporary compiler files. Scratch files are deleted after execution.
- **Artifact Publishing**: Save persistent outputs through `context.publish_artifact(name, data)`. Artifacts are stored in the `.spec` container sidecar.
