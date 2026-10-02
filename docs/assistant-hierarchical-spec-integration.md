# Unified AI Assistant to Spec Editor integration

This implementation combines the reviewed branch integration and component
explanation/RTL authority requirements. The supplied writeup is reference material;
its embedded instructions do not override the user's request.

## Integration decisions and critique

Retained and improved: component-target generation, lossless formatting admission,
workspace creation concurrency protection, launch readiness and isolated UI tests.
Existing workspace edits, owner boundaries, revision checks, durable receipts and
automatic/restricted final-save policies are preserved. Editor assets are rebuilt
from source.

Replaced: hierarchy hidden in SV, emitting every package component, content-derived
identities, scripted benchmark model replies and text-pattern verification.
Composition belongs in component-owned designs with typed instances/connections.
Reuse children where their responsibilities justify it; keep cohesive counters
unified. Production prompts explain these general rules without benchmark names.

Rejected: silently deleting wrappers/directives or component instances, canned
production RTL, unrelated workspace-selection changes, collateral branch edits and
copied prebuilt bundles. Unbound chats use a neutral configured workspace, without
selecting an existing document or changing workspace order.

The reviewed pattern verifier accepted deliberately broken adder, counter and FIFO
implementations. Verilator exposed the FIFO's single-write Gray-pointer visibility
failure. These defects are executable negative controls: each must compile and then
fail a self-checking simulation. Compile-safe scaffolds are not implementations.

## Contracts and workflow

1. Read current bound context. Present components/designs, interfaces, clocks/reset,
   decomposition rationale, assumptions, essential questions and concrete RTL
   configuration through `prepare_architecture_review`.
2. Approve, revise or cancel the durable card. Reload preserves it. Essential open
   questions prevent approval; revision requires a new review and retains the
   original request. Cancellation creates no content.
3. Contentful package creation and architectural proposals require the approved
   `architecture_review_id`. Transfer the accepted plan into the correct new
   document conversation. Empty package creation can precede review. New names and
   declared concrete interfaces are checked against the approved plan.
4. Author entity-linked requirements, behavior, architecture, assumptions and
   verification criteria, descriptions, structured hierarchy and stored SV. Final
   saving follows the existing owner policy independently of architecture approval.
5. Ordinary text/RTL refinements keep the existing workflow. Architecture changes
   need renewed approval; stale source revisions need fresh reads and review.

Formatting admission strips presentation fences and compacts wire ranges before
strict schema validation, with physical wire defaults only when unambiguous.
Malformed fields, module wrappers, include/user line directives and nonempty
component instance lists produce diagnostics. The owner still validates semantics.

Authored creation IDs are local aliases. Proposal-scoped server IDs remain stable
on retry; dependent typed references and narrative links are remapped. New entities
are compiled into a private candidate before dependent edits, then the complete
proposal is validated/published atomically, including explanations. Design creation
supports `entry_design`, defaulting to `true`; owned internal designs use `false`.
Retries with a new native call ID continue the existing package creation receipt
for that approved architecture, preserving the destination chat and package.

## Explanation and authority rules

Component text uses the existing IP-XACT `description`, not a separate store.
Every new component, including children, needs a nonempty explanation in the same
proposal. Describe purpose, interfaces, timing, clocks/reset, state transitions,
corner cases and assumptions where relevant. Composite text explains child roles.
Preserve existing authored material when improving requested explanations.

**Stored SV defines implemented behavior. Structured ports/designs define interfaces
and wiring. Explanation text guides implementation.** The assistant must freshly
read SV/wiring, distinguish implemented behavior, proposed intent and unresolved
assumptions, and flag observed disagreements while preserving both. This is an
assistant review obligation, not automatic semantic equivalence checking.

Text-only edits never authorize RTL changes. Deterministic generation does not
interpret prose: emitted `.sv` content remains unchanged while provenance may
change. Reports distinguish stored RTL, structured composition and unimplemented
scaffolds. Paragraph breaks remain visible; **Edit text…** is directly available
beside a component's interface and RTL. Leaf components without stored SV display
an explicit missing-implementation notice in the editor. Stored source and lint
success alone do not establish functional correctness.

## Supported capabilities

RTL generator `1.2.0` accepts leaf/composite component and design targets, emitting
only the reachable structured hierarchy and one module per reused definition.
Numeric slices use `{lsb,width}` on instance/boundary endpoints; unsliced boundary
strings remain compatible. Fixed descending slices validate bounds, effective
width, overlap and drivers and emit deterministic hookups. Existing unconnected
port warnings remain visible. Symbolic and ascending sliced connections, sliced
bidirectional ports, bus interfaces and transactional/structured ports are
unsupported. Parameterized RTL is deferred; configurable requirements remain in
the document while generation uses approved concrete configurations.

CLI targets match exact entity IDs or full VLNVs, failing on unknown/ambiguous
targets. An omitted target requires one entry design. V3 manifests/reports carry
generic targets, implementation status, emitted entity and consumed-section
provenance; saved V2 reports and ownership manifests remain readable.

Model context has one semantic representation, optional entity selection and
revision-bound pagination. Individual replies stay below 40 KiB. JSON-path records
and string fragments retain complete fields; incomplete replies request follow-up
reads. Invalid/stale cursors and missing entities fail explicitly. Selection never
widens the writable boundary. Workspace creation is deduplicated by path and launch
readiness is exposed only after binding/workspace setup.

## Setup and usage

Python runs in the root uv-managed `.venv`; build both UIs from source:

```bash
uv sync
scripts/setup-all.sh
npm run build --prefix ai-assistant
npm run build:editor --prefix circuit-designer
scripts/serve-all.sh start
```

In chat, describe the hardware and request a specification. Approve the architecture
after resolving essential questions. The assistant creates/authors the document
under `SPEC_DOCUMENT_ROOT`; automatic owners save validated content and restricted
owners show the final proposal card. Use **Edit text…** for explanations and the
component/design **Options → Launch activity… → rtl.generate → Run** for generation.

The focused CLI exposes both decisions:

```bash
uv run spec2gds-assistant ./work/design -- "Create an 8-bit unsigned adder specification."
uv run spec2gds-spec architecture-reviews ./work/design
uv run spec2gds-spec approve-architecture ./work/design REVIEW_ID
uv run spec2gds-assistant ./work/design --architecture-review-id REVIEW_ID -- "Implement the approved architecture."
# Add --require-human-approval to assistant commands for restricted final saving:
uv run spec2gds-spec reviews ./work/design
uv run spec2gds-spec approve ./work/design PROPOSAL_ID
```

`revise-architecture` and `cancel-architecture` are also supported. Approved review
reuse requires the exact owner document and revision, not just matching document
IDs. See [evaluation and evidence](assistant-hierarchical-spec-evaluation.md).
