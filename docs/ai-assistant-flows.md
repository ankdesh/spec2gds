# Reusable flows

A flow definition declares inputs, operations, conditions, decisions, and outputs.
A flow execution records one run. DeepSeek Harness owns both generic contracts
and execution. Spec2gds registers its domain commands and six definitions: four
published flows and two shared subflows.

The model selects a named flow tool and supplies the complete request. The tool
returns acceptance and concludes that turn. The host advances the pinned flow
when the initiating native log has been saved. Acceptance is not completion.
The browser displays progress and decisions. It does not start the next model
phase after file creation.

| Tool | Sequence | Completion evidence |
| --- | --- | --- |
| `flow_create_empty_spec` | Resolve destination, create Spec, bind a separate conversation | Creation receipt and confirmed binding |
| `flow_create_spec_with_component` | Prepare architecture, obtain approval, create Spec, bind destination, read context, author complete Component, submit, await save | Exact applied proposal receipt and saved revision |
| `flow_edit_spec` | Read context and operation schema, author a typed batch, obtain approval for structural edits, submit, await save | Exact applied proposal receipt and saved revision |
| `flow_add_component` | Check binding, read context, prepare architecture, obtain approval, refresh context, author complete Component, submit, await save | Exact applied proposal receipt and saved revision |

These tools are available in Focused and Goal Spec conversations. Selected
Component and Design conversations expose the edit flow and new-Spec creation
flows. Adding a new leaf Component requires a document-bound conversation.
The edit flow can create a complete Design in document scope from existing
Component references. It saves the Design, instances, connections and description
in one atomic batch after approval of the exact operations. Selected Component
and Design conversations cannot create another top-level entity.
Orchestrated Spec conversations support reads and analysis only. They cannot write
a Spec. Circuit conversations do not expose these tools.
Starting a flow does not create a Goal. An active Goal pauses while a flow controls
its conversation. A durable pending delivery releases the unchanged Goal after
success. Flow success does not complete a larger Goal. Failure retains the claim
until an explicit designer action.

Component authoring uses a typed private draft. Domain code converts it into one
atomic batch containing ports, description, optional requested narrative, and
functional SystemVerilog. It checks the approved interfaces, complete content,
operation schema, and authored revision. No placeholder Component is saved.
Restricted content policy waits for the exact proposal in Spec Editor. A preview
or pending proposal does not complete the content request.

Architecture Revise starts a linked replacement execution. After a file was
created but authoring failed, the revision reuses the confirmed file and bound
conversation. It reads fresh context and requests a new architecture approval.
The prior approved review remains immutable. This action requires the observed
failed execution revision and explicit feedback.

The generic states are `running`, `waiting`, `paused`, `needs-resume`,
`needs-reconcile`, `succeeded`, `failed`, and `cancelled`. Architecture and proposal
states remain in product records. Controls use the execution ID and observed
revision. Cancel stops further work and preserves confirmed writes.

On restart, explicit Resume is required before new writes or model requests.
Completed outputs and spending remain recorded. Uncertain writes use stable
request identities and declared receipt reconciliation. Missing or mismatched
service receipts remain pending with a diagnostic. They are not save evidence.
Offline trace inspection reads the stored inputs, outputs, decisions, attempts,
and receipts. It invokes neither a model nor a service.

Definitions and instructions are in `ai-assistant/profile/catalog/flows`.
The profile sets request, token, active-time, output, retained-data, and expanded
node limits explicitly. Subflows and destination model phases share the parent
allowance. Goal-associated requests also consume the source execution allowance.
Waiting for a designer or service does not consume a model request.
The Spec profile permits up to 8 MiB of retained execution data. This includes
recorded context, model inputs and typed outputs, not only the saved proposal.
Its token allowance is 1,000,000 tokens across the execution. Reservations cover
the full native request envelope, including retained conversation history.

Harness exposes `flows.start`, `get`, `list`, `control`, `answer`, and `trace`
through its remote service. Product HTTP controls call the same executor commands.
The product `/spec2gds-api/flows/{sessionId}` view adds the exact architecture
review identity for its approval card. It also shows confirmed creation when the
content request is incomplete. A destination conversation button requires a
confirmed binding. The architecture decision route accepts only reviews linked
to a flow. The
generic `/spec2gds-api/flow-runs/start` adapter starts an eligible published flow
with explicit inputs and a stable request ID. It does not write directly.

The legacy Spec creation, architecture preparation, and proposal model tools have
been removed. Browser creation callbacks, continuation messages, Assistant Spec
save actions, and proposal details cards have also been removed. Direct Spec
creation and old Spec review controls are rejected. The Spec Editor provides
content decisions through exact service receipts. No compatibility path remains
for old pending Spec requests. Start a new flow; confirmed saved files remain.
The Python review bridge is read-only. Spec CLI approval, rejection and
architecture decision commands are removed. The Assistant CLI requires an
existing Spec and returns the flow identity at its first wait. It cannot create
an empty file or append an approved architecture ID to the model request.
Spec definitions and operations use version 2.0.0, with instruction handler
compatibility version 2. Old incompatible releases stop explicitly.

Generic flows are opt-in for other Harness deployments. The bundled text-analysis
example uses deterministic counting, a branch, a subflow, and an optional typed
summary without any Spec2gds dependency.

Native phases retain the caller preset and selected model route after the source
conversation closes. Their charges stay in the source allowance. A pending Goal
release remains recorded until the source conversation is restored and its
native state is persisted.

A recorded submission intent can be resumed with its original artifact and
proposal ID. The host first reads the exact service receipt. It repeats the
submission only when the service reports that no receipt exists, using the same
ID and artifact. Lost responses do not require another model phase. A different
artifact digest stops reconciliation.

The stdio SDK exposes `flow/start`, `flow/get`, `flow/list`, `flow/control`,
`flow/answer`, and `flow/trace`, plus `flow.progress` notifications. These calls
use the same commands and revision checks as browser and product controls.

Structural edits include the exact proposed operation batch in the architecture
review context. The host records its digest and rejects a different batch at
submission. Content edits skip hardware review. Both branches require an applied
service receipt. Rejected, discarded, or stale receipts fail the request.
All completed flows record an immutable receipt from the authoritative Spec service.
