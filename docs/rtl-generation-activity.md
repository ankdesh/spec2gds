# Deterministic RTL Generation Activity

`rtl.generate` version `1.1.0` generates a SystemVerilog 2017
scaffold for one selected design. It preserves reachable component hierarchy,
emits one reusable module per component definition, and translates direct
physical wire connections. It does not call an LLM, inspect narrative intent,
mutate the specification or infer clocks and resets. It incorporates explicit
component/design SystemVerilog body sections when present.

## Supported source profile

The Activity accepts any selected design, including a component-owned internal
design. Every reachable component must contain only physical wire ports with
scalar or explicit decimal ranges. A connected range must match at every
endpoint, including its left and right bounds.

Only IP-XACT ad-hoc connections are supported. Each endpoint can belong to one
connection, one ordinary driver can feed multiple sinks, and nets containing
`inout` endpoints are allowed. For a component-owned internal design, an
external port is interpreted relative to the enclosing module: an external
input drives the design and an external output is a sink. Multiple ordinary
drivers, input-only nets, multiple external endpoints on one connection, or
external endpoints on an unowned design make the Activity unavailable.

Generation also rejects:

- every reachable bus-interface declaration, even if it is unused;
- interface connection records;
- transactional and structured ports; and
- symbolic ranges such as `DATA_WIDTH-1:0`.

These cases are rejected before workspace output is written. Non-fatal
unconnected instance ports appear as `Warning:` diagnostics during availability
and are persisted in the generation report.

## Generated modules

Leaf modules declare ANSI `wire` ports. Outputs are tied to `'0`, inouts are
tied to `'z`, and input/inout values are consumed by an `_unused_ok` sink so
the scaffold passes strict lint without pretending to implement behavior.

With a non-whitespace SV body, the module instead declares inputs/outputs as
`logic` and inouts as `wire`, removes automatic leaf output/inout tie-offs, and
expects the body to drive required outputs. Generated nets and instances appear
first, followed by the component body and then the owned/design body. Line
mappings retain the stored section path in diagnostics. Missing or whitespace
bodies keep the original scaffold behavior.

Composite modules contain only child instances and structural nets. An
unconnected child input is tied to `'0`; unconnected child outputs and inouts
use explicit `.port()` no-connects. Internal-design targets use their owning
component module as the top. Entry and otherwise unowned designs receive a
portless top wrapper.

Names are based on IP-XACT names. Invalid characters and SystemVerilog keywords
are normalized, collisions receive a stable hash suffix, and the complete name
map is stored in both the report and ownership manifest.

## Invoke from Python

```python
from pathlib import Path

from spec2gds.agent_spec.activities import (
    ActivitySnapshot,
    LocalActivityWorkspace,
    SpecExtensionRegistry,
    invoke_activity,
)
from spec2gds.agent_spec.activities.rtl import register_extensions
from spec2gds.agent_spec.spec_format.ir import SpecRevision

revision = SpecRevision.load("design.spec")
target = revision.entry_designs()[0].ref
snapshot = ActivitySnapshot.create(revision, target)

registry = SpecExtensionRegistry()
register_extensions(registry)
result = invoke_activity(
    registry,
    "rtl.generate",
    snapshot,
    LocalActivityWorkspace(Path("generated")),
)
print(result.report["output_path"])
```

The workspace root is caller-owned. With the root above, output is published
at:

```text
generated/rtl/<document-id>/<design-id>/
├── Makefile
├── README.md
├── generation-manifest.json
└── rtl/
    ├── components/*.sv
    ├── designs/<top>.sv
    └── files.f
```

The `designs/` file is omitted when the selected internal design uses its
owning component module as the top. The Activity also returns a typed report and
the `rtl.generation_report` JSON artifact with provenance, counts, warnings,
name mappings, consumed section IDs/digests/output locations, file hashes, and
the generated tree digest. The generation manifest and report schemas are V2.

The directory is fully generator-owned. A rerun atomically replaces it only
when its manifest matches the generator, document, and design. Do not add
hand-written implementation code to this tree because regeneration discards
manual edits.

## Verify with Verilator

Verilator 5.x and GNU Make are required. From the generated project root, run:

```bash
make lint
```

The target selects the generated top explicitly and runs SystemVerilog 2017
`--lint-only` with `-Wall`. Warnings remain fatal; only
`PINCONNECTEMPTY` is disabled because explicit output/inout no-connects are an
intentional scaffold construct.

Repository RTL tests invoke this target without a skip, so install Verilator
5.x before running the Python suite:

```bash
uv run python -m pytest tests/agent_spec/activities/rtl -q
```
