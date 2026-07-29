import {
  cycleDocumentFixture,
  crossingDocumentFixture,
  hyperedgeDocumentFixture,
  mixedDocumentFixture,
  simpleDocumentFixture,
  type CircuitDocument,
} from "@spec2gds/circuit-core";

export interface StandaloneExample {
  title: string;
  summary: string;
  build: () => CircuitDocument;
}

function identify(document: CircuitDocument, id: string, label: string): CircuitDocument {
  document.document_id = `standalone_${id}`;
  document.label = label;
  document.design = { ...document.design, id, label };
  return document;
}

export const standaloneExamples = {
  subsystem: {
    title: "Processor subsystem",
    summary: "A CPU, peripheral bus, and interrupt connection mixing interface and port terminals.",
    build: () => identify(mixedDocumentFixture(), "processor_subsystem", "Processor subsystem"),
  },
  datapath: {
    title: "Producer / consumer",
    summary: "A minimal two-block datapath useful for selection, dragging, and net edits.",
    build: () => identify(simpleDocumentFixture(), "producer_consumer", "Producer / consumer"),
  },
  fanout: {
    title: "Broadcast fanout",
    summary: "One source driving three sinks through a multi-endpoint net with a junction.",
    build: () => identify(hyperedgeDocumentFixture(), "broadcast_fanout", "Broadcast fanout"),
  },
  feedback: {
    title: "Feedback pipeline",
    summary: "A cyclic three-stage pipeline for testing orthogonal feedback routing.",
    build: () => identify(cycleDocumentFixture(), "feedback_pipeline", "Feedback pipeline"),
  },
  crossing: {
    title: "Disconnected crossing",
    summary: "Two geometric net crossings with no shared electrical junction.",
    build: () => identify(crossingDocumentFixture(), "disconnected_crossing", "Disconnected crossing"),
  },
} satisfies Record<string, StandaloneExample>;

export type StandaloneExampleId = keyof typeof standaloneExamples;
