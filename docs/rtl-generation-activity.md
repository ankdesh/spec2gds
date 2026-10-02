# Deterministic RTL Generation Activity

`rtl.generate` version `1.2.0` generates a SystemVerilog 2017
project for one selected component or design. It preserves reachable component hierarchy,
emits one reusable module per component definition, and translates direct
physical wire connections. It does not call an LLM, inspect narrative intent,
mutate the specification or infer clocks and resets. It incorporates explicit
component/design SystemVerilog body sections when present.

## Supported source profile

The Activity accepts leaf/composite components and designs, including owned
internal designs. Only reachable definitions are emitted. Reachable ports must be
physical wires with scalar/decimal ranges; connected effective widths must match.
Numeric slices use `{lsb,width}` with bounds/overlap checks; unsliced boundary strings
remain valid. Symbolic and ascending sliced ranges and sliced bidirectional ports
are unsupported.

Only IP-XACT ad-hoc connections are supported. Each endpoint can belong to one
connection per non-overlapping bit interval, one ordinary driver can feed multiple sinks, and nets containing
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
`logic` and inouts as `wire`, removes the automatic leaf output/inout tie-offs
and `_unused_ok` input sink, and expects the body to implement the required
behavior. Generated nets and instances appear first, followed by the component
body and then the owned/design body. Line mappings retain the stored section
path in diagnostics. Missing or whitespace bodies keep the original scaffold
behavior.

Composite scaffolds contain child instances and structural nets; explicit SV
bodies can add behavior. An
unconnected child input is tied to `'0`; unconnected child outputs and inouts
use explicit `.port()` no-connects. Internal-design targets use their owning
component module as the top. Entry and otherwise unowned designs receive a
portless top wrapper.

Names are based on IP-XACT names. Invalid characters and SystemVerilog keywords
are normalized, collisions receive a stable hash suffix, and the complete name
map is stored in both the report and ownership manifest.

## Invoke from Spec Editor

Open the target component or design in Spec Editor and choose **Options → More actions… →
Launch activity…**. Select **Generate SystemVerilog RTL** and press **Run**.
Preflight diagnostics remain visible in the dialog; unsupported designs cannot
be queued, while unconnected instance ports are warnings and do not block the
run.

After enqueue, the editor opens the **Activity** tab. It restores active and
completed jobs after refresh, receives live state changes, and offers
**Cancel** while a job is queued or running. A completed report shows the top
module, generated file count, warnings, originating source revision, and the
absolute server output path. Run `make lint` from that path separately;
`rtl.generate` performs generation only.

The run always uses the immutable source snapshot created at enqueue time.
Later editor changes do not alter it. On restart, queued jobs remain queued and
interrupted running jobs are requeued from that snapshot. Terminal reports and
artifacts are stored in the `.spec` package's Activity metadata without
changing its source revision hash.

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

The workspace root is caller-owned. Editor-launched generation uses the folder
containing the active `.spec` package. With that folder as the root, output is
published at:

```text
rtl/<document-name>/<entity-name>/
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
the generated tree digest. V3 manifests/reports include generic targets, emitted
entity provenance and implementation status. Saved V2 reports and ownership
manifests remain readable. Text explanations do not alter generated logic.

The directory is fully generator-owned. A rerun atomically replaces it only
when its manifest matches the generator, document, and target. Do not add
hand-written implementation code to this tree because regeneration discards
manual edits.

See [RTL semantics examples](rtl-semantics-examples.md) for one-cycle and
two-cycle component bodies, configured workspace generation, and behavioral
verification.

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
