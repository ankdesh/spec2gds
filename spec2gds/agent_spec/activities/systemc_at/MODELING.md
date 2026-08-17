# SystemC AT Performance Modeling Principles

This document records the topology-driven modeling rules being developed for
the deterministic SystemC TLM 2.0 AT generator. The three reference
applications are examples of the rules, not special generator modes:

1. fixed-latency and pipelined processing;
2. arbitration at a shared component boundary; and
3. FIFO-based backpressure between components.

The generated model is timing-only. Transactions carry identity, class,
destination, and size metadata, but generated components do not implement
functional operations such as ADD or MUL. Workloads are separate from the
hardware Spec so the same generated hardware can be exercised with different
traffic.

## Unified component model

Every packet-accepting leaf component is modeled as a bounded resident store
around a timed service resource:

~~~mermaid
flowchart LR
    U["Upstream component"] -->|"BEGIN_REQ"| A["Boundary admission"]
    A -->|"capacity available"| Q["Shared resident FIFO"]
    A -->|"capacity full: hold END_REQ"| ST["Upstream stalled"]
    Q -->|"II permits service start"| S["Fixed-latency service"]
    S -->|"ready after L cycles"| O["Output holding state"]
    O -->|"downstream END_REQ"| F["Release resident slot"]
    F --> A
~~~

For a sink, the resident slot is released when local service completes. For a
forwarding component, the slot remains occupied while the packet is queued,
being serviced, ready, or blocked by the downstream component.

Observed packet latency is therefore:

~~~text
observed latency =
    input queue wait
  + arbitration wait
  + configured service latency
  + downstream backpressure wait
~~~

The configured latency is the zero-contention service time. Queueing,
arbitration, and downstream stalls are measured effects rather than additions
hidden inside the configured value.

## Case 1: fixed latency and initiation interval

Latency is time, while FIFO depth is storage. A FIFO whose number of entries
equals latency is not a general latency model. It represents an L-stage
pipeline only when all of these additional assumptions are true:

- one packet may enter every cycle;
- every packet advances by one stage every cycle;
- packets remain in order; and
- output stalls have defined pipeline-freeze or elastic-buffer behavior.

The generic model instead schedules service completion with a timed packet
queue or PEQ. A packet that starts service at cycle T becomes internally ready
at cycle T plus latency_cycles.

The Spec must also describe the initiation interval, or II. II is the minimum
number of cycles between service starts. It determines throughput independently
of latency.

### Fully pipelined example

For latency_cycles = 4 and initiation_interval_cycles = 1:

~~~text
cycle          0  1  2  3  4  5  6
packet A       S  .  .  .  C
packet B          S  .  .  .  C
packet C             S  .  .  .  C
~~~

S means service start and C means internally complete. Every packet takes four
cycles, but a new packet starts every cycle.

### Non-pipelined example

For latency_cycles = 4 and initiation_interval_cycles = 4:

~~~text
cycle          0  1  2  3  4  5  6  7  8
packet A       S  .  .  .  C
packet B                   S  .  .  .  C
~~~

The resource remains occupied by packet A for four cycles. Packet B may have
already crossed the input boundary into the component FIFO, but it waits until
cycle 4 to start service.

Latency and II also represent partially pipelined resources. For example,
latency_cycles = 6 and initiation_interval_cycles = 2 allows a new operation
every two cycles even though each operation takes six cycles to complete.

### Reference: pipelined ALU

The reference ALU has one target-side input, ADD latency of three cycles, MUL
latency of four cycles, and an initiation interval of one cycle. Requests may
overlap in execution. Its in-order retirement queue delays a younger completed
operation until every older operation is complete.

The generic model should not implement ADD or MUL. Instead, the workload marks
transactions with an operation class, and the timing profile maps each class
to its fixed service latency. If class-specific latency is not configured, the
component default latency applies.

## Case 2: arbitration at component boundaries

Arbitration is required when multiple upstream requests compete to cross one
accepting component boundary or use one shared internal service resource.

~~~mermaid
flowchart LR
    U0["Upstream 0"] --> R["Shared receiving component"]
    U1["Upstream 1"] --> R
    U2["Upstream 2"] --> R
~~~

This fan-in topology represents contention. The receiving component collects
all requests arriving in the same cycle and selects one winner at a
deterministic scheduling point. Selection must not depend on SystemC callback
or socket binding order.

The first library version supports:

- round-robin arbitration; and
- fixed-priority arbitration.

The policy must be stated in the Spec because topology cannot infer whether
the hardware is fair or priority-based. Round-robin uses a deterministic
initial pointer. Fixed-priority arbitration requires an explicit priority
ordering or another deterministic ordering rule.

Admission occurs at grant time. Until a request wins arbitration, the target
returns TLM_ACCEPTED without changing BEGIN_REQ to END_REQ. The producer
remains stalled. When the request wins, the component reserves capacity and
sends END_REQ backward to release that producer.

The component initiation interval determines the earliest cycle at which the
shared resource may grant another request.

### Fan-out is not arbitration

One output port connected to multiple downstream endpoints means routing or
broadcast, not arbitration:

~~~mermaid
flowchart LR
    S["One sending port"] --> D0["Downstream 0"]
    S --> D1["Downstream 1"]
    S --> D2["Downstream 2"]
~~~

This ambiguous single-port fan-out is rejected in the first version. Every
supported Spec connection remains pairwise. A component may still expose
multiple distinct output interfaces, as a switch does; selecting among those
interfaces is a separate routing problem and is listed under open decisions.

### Reference: round-robin switch

The reference switch has four distinct ingress interfaces, four distinct
egress interfaces, one shared transmission resource, and a three-cycle
resource occupancy. Four requests arriving at cycle 1 are collected together.
Round-robin grants ingress 0, then 1, then 2, then 3. END_REQ is held for each
loser until its grant.

In the generic model this is inferred from the component topology plus its
performance data:

- multiple target-side inputs identify a contention boundary;
- arbitration policy selects round-robin;
- latency and II describe transmission timing; and
- pairwise output connections identify distinct downstream paths.

The component name and the reference application's fixed count of four must
not appear in the generator algorithm.

## Case 3: FIFO backpressure

Every packet-accepting leaf component declares a positive capacity_packets.
Capacity is component-wide in the first version: all target-side inputs and
all resident packet states consume the same bounded storage.

Capacity is reserved when END_REQ is scheduled, not when service completes.
This prevents simultaneous arrivals from overbooking the FIFO.

When capacity is available:

1. reserve one resident slot;
2. return or send END_REQ according to the boundary timing rule;
3. queue the packet for service; and
4. start it when the component II permits.

When capacity is full:

1. leave the phase as BEGIN_REQ;
2. return TLM_ACCEPTED;
3. retain the legal outstanding request for that ingress; and
4. send END_REQ backward only after a slot has been reserved.

A forwarding component does not release its slot at service start or service
completion. It releases the slot only after the downstream component accepts
the packet with END_REQ. Consequently, a downstream stall holds the packet in
the upstream component, fills its FIFO, and eventually propagates
backpressure further upstream.

The occupancy calculation includes every packet in these states:

- queued and waiting for service;
- currently in service;
- internally ready; and
- waiting for downstream acceptance.

### Reference: depth-four FIFO

The reference producer sends one packet per cycle into a FIFO with capacity
four. The consumer initially does not drain the FIFO. At cycle 6 the FIFO is
full, so the sixth write remains in BEGIN_REQ and the producer stalls. When the
consumer accepts a packet, one resident slot is released. The FIFO reserves
that slot for the pending write and sends END_REQ backward, allowing the
producer to resume.

The same behavior should emerge from generic topology and parameters:

~~~text
FIFO component:
  latency_cycles: 2
  initiation_interval_cycles: 1
  capacity_packets: 4

Consumer component:
  latency_cycles: workload-independent configured value
  initiation_interval_cycles: configured service rate
  capacity_packets: configured resident capacity
~~~

The generator must not recognize class names such as Producer, FifoTarget, or
Consumer.

## Information required from the Spec

The topology remains canonical IP-XACT structure: component definitions,
instances, typed initiator/target interfaces, pairwise connections, and
component compositions.

A versioned, typed performance annotation supplies data topology cannot
determine. At minimum, each packet-accepting leaf requires:

| Information | Purpose |
| --- | --- |
| latency_cycles | Zero-contention fixed service latency |
| initiation_interval_cycles | Minimum spacing between service starts |
| capacity_packets | Shared resident packet capacity |
| arbitration policy | Required when multiple target-side inputs contend |
| fixed-priority order | Required when fixed-priority arbitration is selected |
| optional class latency table | Allows transaction classes to use different fixed latencies |

Missing required information must make Activity availability fail before any
project is written. Diagnostics should name the hierarchical component
instance, the inferred topology shape, and every missing or inconsistent
field so the user can update the Spec and rerun deterministically.

## Topology classification

The intended initial classification is:

| Leaf interface shape | Generated behavior |
| --- | --- |
| initiator only | Workload-driven source adapter |
| one target only | Timed sink |
| one target and one initiator | Timed forwarding component |
| multiple target inputs | Arbitrated shared boundary and service |
| no interfaces | Unsupported or passive; requires an explicit decision |
| ambiguous multi-endpoint connection | Rejected |

Buffering and backpressure are not separate component kinds. They arise from
the required finite capacity and downstream handshake behavior of every
accepting component.

## Open decisions

The following points were not yet agreed and must be resolved before
implementation:

1. Whether only leaf components carry timing data, or whether composite
   components may also declare derived timing assertions.
2. Whether successful request acknowledgement delay is fixed at one cycle or
   configured per accepting component.
3. How a component with multiple distinct egress interfaces selects an output.
   Candidate approaches are topology-based destination reachability or an
   explicit route table.
4. The exact external workload JSON schema, simulation stop condition, metrics
   report, and optional VCD outputs.
5. The deterministic authoring workflow for adding and validating performance
   annotations in a Spec package.
