# SystemC AT performance model requirements

Proposed work, not current generator behavior. The delivered
[`systemc.generate_at_skeleton`](systemc-at-activity.md) creates structural sockets
with a fixed acknowledgement delay and an empty simulation. It does not implement
the resident queues, workloads, arbitration or timed forwarding described here.
This consolidates the former generator-local `MODELING.md` design notes.

## Model and provenance

Keep topology in canonical IP-XACT and performance data in a versioned typed
annotation. A deterministic generator must not infer behavior from narrative,
component names or a special sample mode. Workloads remain separate from hardware.
Packets may carry identity, class, destination and size; timing models should not
claim to implement functional ADD/MUL or other DUT operations.

Each accepting leaf needs explicit service latency, initiation interval (II),
positive component-wide capacity and, for shared resources, an arbitration policy.
Fixed priority needs an ordering; class-specific latency is optional. Missing or
inconsistent data should reject preflight with hierarchical instance diagnostics.

Latency is time and capacity is storage. Starting at cycle T with latency L means
readiness at T+L; II bounds the spacing between starts. For example, L=4/II=1 is
pipelined, L=4/II=4 is serial, and L=6/II=2 is partially pipelined. In-order retirement
must prevent a younger short-latency request from overtaking an older request.
Observed latency includes queueing, arbitration and downstream stalls separately.

## Admission, arbitration and backpressure

Reserve capacity before sending `END_REQ`, not when service completes. When full,
retain the outstanding request in `BEGIN_REQ`/`TLM_ACCEPTED` until a slot is reserved.
All queued, servicing, ready and downstream-blocked packets consume the same
resident capacity. A sink releases a slot at completion; a forwarding component
releases it only when downstream acceptance is confirmed. Backpressure then follows
from finite capacity and the handshake rather than a special FIFO component type.

For fan-in, collect arrivals at a deterministic cycle scheduling point. Round-robin
and fixed-priority policies are candidate initial policies, with explicit initial
pointer/order; SystemC callback/binding order must not choose the winner. II also
bounds grants. Single-port fan-out requires routing/broadcast semantics and remains
unsupported; distinct egress interfaces require a separate routing decision.

Proposed classifications are an initiator-only workload source, a target-only
sink, target+initiator forwarding and multiple-target shared arbitration. Passive
leaves and ambiguous connections require an explicit policy before implementation.
The current generator rejects fan-in/fan-out; supporting this model requires
extending preflight and generation together.

## Acceptance scenarios and unresolved decisions

Use generic fixtures for overlapping class latencies with ordered retirement,
simultaneous four-ingress round-robin contention, and capacity-four backpressure.
The fifth resident request must stall until a release, then receive one matching
acknowledgement. Fixtures must measure timing, occupancy and grant order without
embedding their names or fixed component counts in generator algorithms.

Resolve these decisions before implementing the runtime:

- Leaf-only performance data versus composite derived timing assertions.
- Fixed one-cycle versus configurable acknowledgement delay.
- Topology-derived destination routing versus an explicit route table.
- Workload schema, stop condition, metrics and optional VCD signals.
- Deterministic annotation authoring/validation and its Spec editor workflow.
