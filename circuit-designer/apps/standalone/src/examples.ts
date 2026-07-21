import {
  cycleFixture,
  crossingFixture,
  hyperedgeFixture,
  mixedFixture,
  simpleFixture,
  type CircuitGraphSnapshot,
} from "@spec2gds/circuit-core";

export interface StandaloneExample {
  title: string;
  summary: string;
  build: () => CircuitGraphSnapshot;
}

function identify(graph: CircuitGraphSnapshot, id: string, label: string): CircuitGraphSnapshot {
  graph.document_id = `standalone_${id}`;
  graph.design = { ...graph.design, id, label, vlnv: `example:standalone:${id}:1.0` };
  graph.nodes = graph.nodes.map((node) => ({ ...node, source_ref: { kind: "local_instance", source_id: node.id } }));
  graph.terminals = graph.terminals.map((terminal) => ({ ...terminal, source_ref: { kind: "local_terminal", source_id: terminal.id } }));
  graph.nets = graph.nets.map((net) => ({ ...net, source_ref: { kind: "local_connection", source_id: net.id } }));
  return graph;
}

export const standaloneExamples = {
  subsystem: {
    title: "Processor subsystem",
    summary: "A CPU, peripheral bus, and interrupt connection mixing interface and port nets.",
    build: () => identify(mixedFixture(), "processor_subsystem", "Processor subsystem"),
  },
  datapath: {
    title: "Producer / consumer",
    summary: "A minimal two-block datapath useful for selection, dragging, and net edits.",
    build: () => identify(simpleFixture(), "producer_consumer", "Producer / consumer"),
  },
  fanout: {
    title: "Broadcast fanout",
    summary: "One source driving three sinks through a multi-endpoint net with a junction.",
    build: () => identify(hyperedgeFixture(), "broadcast_fanout", "Broadcast fanout"),
  },
  feedback: {
    title: "Feedback pipeline",
    summary: "A cyclic three-stage pipeline for testing orthogonal feedback routing.",
    build: () => identify(cycleFixture(), "feedback_pipeline", "Feedback pipeline"),
  },
  crossing: {
    title: "Disconnected crossing",
    summary: "Two geometric net crossings with no shared electrical junction.",
    build: () => identify(crossingFixture(), "disconnected_crossing", "Disconnected crossing"),
  },
} satisfies Record<string, StandaloneExample>;

export type StandaloneExampleId = keyof typeof standaloneExamples;
