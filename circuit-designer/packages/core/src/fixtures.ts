import type {
  CircuitDocument,
  CircuitInstance,
  CircuitNet,
  ComponentDefinition,
  TerminalDefinition,
} from "./types.generated";
import { emptyLayout, projectDocument, type CircuitGraphView } from "./model";

function terminal(
  id: string,
  direction: TerminalDefinition["direction"],
  category: "port" | "interface" = "port",
  width: TerminalDefinition["width"] = 1,
): TerminalDefinition {
  return { id, label: id, direction, width, category };
}

function component(id: string, terminals: TerminalDefinition[]): ComponentDefinition {
  return {
    id,
    label: id,
    origin: "local",
    editable: true,
    terminals,
    parameters: [],
    appearance: { renderer_key: "generic", properties: {} },
  };
}

function instance(id: string, component_id: string): CircuitInstance {
  return { id, label: id, component_id, parameter_values: {} };
}

function endpoint(instance_id: string, terminal_id: string): CircuitNet["endpoints"][number] {
  return { kind: "instance", instance_id, terminal_id };
}

function document(
  id: string,
  components: ComponentDefinition[],
  instances: CircuitInstance[],
  nets: CircuitNet[],
): CircuitDocument {
  return {
    protocol_version: "circuit-designer.v1",
    document_id: `fixture_${id}`,
    label: id,
    components,
    design: {
      id,
      label: id,
      boundary_terminals: [],
      instances,
      nets,
    },
    layout: emptyLayout(),
  };
}

export function simpleDocumentFixture(): CircuitDocument {
  return document(
    "simple",
    [component("producer", [terminal("data", "output")]), component("consumer", [terminal("data", "input")])],
    [instance("producer_0", "producer"), instance("consumer_0", "consumer")],
    [{ id: "data", label: "data", endpoints: [endpoint("producer_0", "data"), endpoint("consumer_0", "data")] }],
  );
}

export function mixedDocumentFixture(): CircuitDocument {
  return document(
    "mixed",
    [
      component("cpu", [terminal("irq", "input"), terminal("bus", "output", "interface", 32)]),
      component("peripheral", [terminal("bus", "input", "interface", 32), terminal("irq", "output")]),
    ],
    [instance("cpu_0", "cpu"), instance("peripheral_0", "peripheral")],
    [
      { id: "system_bus", label: "system bus", endpoints: [endpoint("cpu_0", "bus"), endpoint("peripheral_0", "bus")] },
      { id: "irq", label: "irq", endpoints: [endpoint("peripheral_0", "irq"), endpoint("cpu_0", "irq")] },
    ],
  );
}

export function bidirectionalDocumentFixture(): CircuitDocument {
  return document(
    "bidirectional",
    [
      component("transceiver", [terminal("data", "inout", "port", "[DATA_WIDTH-1:0]")]),
    ],
    [instance("transceiver_0", "transceiver"), instance("transceiver_1", "transceiver")],
    [{
      id: "shared_data",
      label: "shared data",
      endpoints: [endpoint("transceiver_0", "data"), endpoint("transceiver_1", "data")],
    }],
  );
}

export function hyperedgeDocumentFixture(): CircuitDocument {
  return document(
    "hyperedge",
    [component("source", [terminal("broadcast", "output")]), component("sink", [terminal("broadcast", "input")])],
    [instance("source_0", "source"), ...[0, 1, 2].map((index) => instance(`sink_${index}`, "sink"))],
    [{
      id: "broadcast",
      label: "broadcast",
      endpoints: [
        endpoint("source_0", "broadcast"),
        endpoint("sink_0", "broadcast"),
        endpoint("sink_1", "broadcast"),
        endpoint("sink_2", "broadcast"),
      ],
    }],
  );
}

export function hierarchyDocumentFixture(): CircuitDocument {
  const result = document(
    "hierarchy",
    [component("pipeline", [terminal("request", "input"), terminal("response", "output")])],
    [instance("pipeline_0", "pipeline")],
    [
      {
        id: "request",
        label: "request",
        endpoints: [
          { kind: "boundary", terminal_id: "request" },
          endpoint("pipeline_0", "request"),
        ],
      },
      {
        id: "response",
        label: "response",
        endpoints: [
          endpoint("pipeline_0", "response"),
          { kind: "boundary", terminal_id: "response" },
        ],
      },
    ],
  );
  result.design.boundary_terminals = [
    { id: "request", label: "request", direction: "input", width: 1, category: "port" },
    { id: "response", label: "response", direction: "output", width: 1, category: "port" },
  ];
  return result;
}

export function cycleDocumentFixture(): CircuitDocument {
  return document(
    "cycle",
    [component("stage", [terminal("input", "input"), terminal("output", "output")])],
    [0, 1, 2].map((index) => instance(`stage_${index}`, "stage")),
    [0, 1, 2].map((index) => ({
      id: `feedback_${index}`,
      label: `feedback ${index}`,
      endpoints: [
        endpoint(`stage_${index}`, "output"),
        endpoint(`stage_${(index + 1) % 3}`, "input"),
      ],
    })),
  );
}

export function crossingDocumentFixture(): CircuitDocument {
  const result = document(
    "crossing",
    [
      component("left", [terminal("east", "output")]),
      component("right", [terminal("west", "input")]),
      component("top", [terminal("south", "output")]),
      component("bottom", [terminal("north", "input")]),
    ],
    [instance("left_0", "left"), instance("right_0", "right"), instance("top_0", "top"), instance("bottom_0", "bottom")],
    [
      { id: "horizontal", label: "horizontal", endpoints: [endpoint("left_0", "east"), endpoint("right_0", "west")] },
      { id: "vertical", label: "vertical", endpoints: [endpoint("top_0", "south"), endpoint("bottom_0", "north")] },
    ],
  );
  result.layout.instance_geometry = {
    left_0: { x: 0, y: 80, width: 180, height: 120, pinned: true },
    right_0: { x: 400, y: 80, width: 180, height: 120, pinned: true },
    top_0: { x: 240, y: 0, width: 180, height: 80, pinned: true },
    bottom_0: { x: 240, y: 220, width: 180, height: 80, pinned: true },
  };
  result.layout.terminal_placements = {
    "left_0:east": { side: "EAST", order: 0, locked: true },
    "right_0:west": { side: "WEST", order: 0, locked: true },
    "top_0:south": { side: "SOUTH", order: 0, locked: true },
    "bottom_0:north": { side: "NORTH", order: 0, locked: true },
  };
  result.layout.net_routes = {
    horizontal: {
      vertices: [
        { id: "h-left", kind: "endpoint", terminal_id: "left_0:east", point: { x: 180, y: 140 } },
        { id: "h-right", kind: "endpoint", terminal_id: "right_0:west", point: { x: 400, y: 140 } },
      ],
      segments: [{ id: "h-crossing", from_vertex: "h-left", to_vertex: "h-right" }],
    },
    vertical: {
      vertices: [
        { id: "v-top", kind: "endpoint", terminal_id: "top_0:south", point: { x: 300, y: 80 } },
        { id: "v-bottom", kind: "endpoint", terminal_id: "bottom_0:north", point: { x: 300, y: 220 } },
      ],
      segments: [{ id: "v-crossing", from_vertex: "v-top", to_vertex: "v-bottom" }],
    },
  };
  return result;
}

export function largeDocumentFixture(instanceCount = 200): CircuitDocument {
  const block = component("block", [
    terminal("chain_in", "input"),
    terminal("chain_out", "output"),
    terminal("skip_in", "input"),
    terminal("skip_out", "output"),
  ]);
  const instances = Array.from({ length: instanceCount }, (_, index) => instance(`block_${index}`, "block"));
  const nets: CircuitNet[] = [];
  for (let index = 0; index < instanceCount - 1; index += 1) {
    nets.push({
      id: `chain_${index}`,
      label: `chain ${index}`,
      endpoints: [endpoint(`block_${index}`, "chain_out"), endpoint(`block_${index + 1}`, "chain_in")],
    });
  }
  for (let index = 0; index < instanceCount - 7; index += 1) {
    nets.push({
      id: `skip_${index}`,
      label: `skip ${index}`,
      endpoints: [endpoint(`block_${index}`, "skip_out"), endpoint(`block_${index + 7}`, "skip_in")],
    });
  }
  return document("large", [block], instances, nets);
}

export const documentFixtures = {
  simple: simpleDocumentFixture,
  mixed: mixedDocumentFixture,
  bidirectional: bidirectionalDocumentFixture,
  hyperedge: hyperedgeDocumentFixture,
  hierarchy: hierarchyDocumentFixture,
  cycle: cycleDocumentFixture,
  crossing: crossingDocumentFixture,
  large: largeDocumentFixture,
};

export function simpleFixture(): CircuitGraphView { return projectDocument(simpleDocumentFixture(), "fixture"); }
export function mixedFixture(): CircuitGraphView { return projectDocument(mixedDocumentFixture(), "fixture"); }
export function bidirectionalFixture(): CircuitGraphView { return projectDocument(bidirectionalDocumentFixture(), "fixture"); }
export function hyperedgeFixture(): CircuitGraphView { return projectDocument(hyperedgeDocumentFixture(), "fixture"); }
export function hierarchyFixture(): CircuitGraphView { return projectDocument(hierarchyDocumentFixture(), "fixture"); }
export function cycleFixture(): CircuitGraphView { return projectDocument(cycleDocumentFixture(), "fixture"); }
export function crossingFixture(): CircuitGraphView { return projectDocument(crossingDocumentFixture(), "fixture"); }
export function largeFixture(instanceCount = 200): CircuitGraphView {
  return projectDocument(largeDocumentFixture(instanceCount), "fixture");
}

/** Renderer fixtures retained as projections while the canvas migrates incrementally. */
export const fixtures = {
  simple: simpleFixture,
  mixed: mixedFixture,
  bidirectional: bidirectionalFixture,
  hyperedge: hyperedgeFixture,
  hierarchy: hierarchyFixture,
  cycle: cycleFixture,
  crossing: crossingFixture,
  large: largeFixture,
};
