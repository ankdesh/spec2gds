import type {
  CircuitComponentDefinition,
  CircuitGraphSnapshot,
  CircuitNet,
  CircuitNode,
  CircuitTerminal,
} from "./types.generated";

const protocol_version = "circuit-designer.v1" as const;
const source_revision_hash = `sha256:${"0".repeat(64)}`;

const source = (source_id: string, kind: string) => ({ source_id, kind });

function component(id: string): CircuitComponentDefinition {
  return { id, label: id, vlnv: `example:fixture:${id}:1.0`, source_ref: source(id, "component") };
}

function port(node: string, name: string, direction: "in" | "out" | "inout"): CircuitTerminal {
  return {
    id: `${node}:port:${name}`,
    node_id: node,
    label: name,
    kind: "port",
    direction,
    mapped_port_ids: [],
    declared_bounds: [],
    source_ref: source(`${node}:${name}`, "port"),
  };
}

function iface(node: string, name: string, role: "initiator" | "target"): CircuitTerminal {
  return {
    id: `${node}:interface:${name}`,
    node_id: node,
    label: name,
    kind: "interface",
    role,
    bus_vlnv: "example:fixture:bus:1.0",
    abstraction_vlnv: "example:fixture:bus_wire:1.0",
    mapped_port_ids: [],
    declared_bounds: [],
    source_ref: source(`${node}:${name}`, "interface"),
  };
}

function node(id: string, component_id: string, terminals: CircuitTerminal[]): CircuitNode {
  return {
    id,
    label: id,
    component_id,
    component_vlnv: `example:fixture:${component_id}:1.0`,
    terminal_ids: terminals.map((terminal) => terminal.id),
    configuration_values: {},
    source_ref: source(id, "instance"),
  };
}

function net(id: string, kind: "interface" | "ad_hoc", terminalIds: string[]): CircuitNet {
  return {
    id,
    label: id,
    kind,
    endpoints: terminalIds.map((terminal_id) => ({ terminal_id })) as CircuitNet["endpoints"],
    source_ref: source(id, "connection"),
  };
}

function graph(
  id: string,
  components: CircuitComponentDefinition[],
  nodes: CircuitNode[],
  terminals: CircuitTerminal[],
  nets: CircuitNet[],
): CircuitGraphSnapshot {
  return {
    protocol_version,
    document_id: `fixture_${id}`,
    source_revision_hash,
    design: { id, label: id, vlnv: `example:fixture:${id}:1.0`, source_ref: source(id, "design") },
    breadcrumbs: [],
    capabilities: {
      edit_topology: false,
      edit_layout: false,
      replace_component: false,
      edit_instance_details: false,
      submit_agent_proposal: false,
    },
    components,
    nodes,
    terminals,
    nets,
  };
}

export function simpleFixture(): CircuitGraphSnapshot {
  const producerPort = port("producer_0", "data", "out");
  const consumerPort = port("consumer_0", "data", "in");
  return graph(
    "simple",
    [component("producer"), component("consumer")],
    [node("producer_0", "producer", [producerPort]), node("consumer_0", "consumer", [consumerPort])],
    [producerPort, consumerPort],
    [net("data", "ad_hoc", [producerPort.id, consumerPort.id])],
  );
}

export function mixedFixture(): CircuitGraphSnapshot {
  const initiator = iface("cpu_0", "bus", "initiator");
  const irqIn = port("cpu_0", "irq", "in");
  const target = iface("peripheral_0", "bus", "target");
  const irqOut = port("peripheral_0", "irq", "out");
  return graph(
    "mixed",
    [component("cpu"), component("peripheral")],
    [node("cpu_0", "cpu", [irqIn, initiator]), node("peripheral_0", "peripheral", [target, irqOut])],
    [irqIn, initiator, target, irqOut],
    [net("system_bus", "interface", [initiator.id, target.id]), net("irq", "ad_hoc", [irqOut.id, irqIn.id])],
  );
}

export function hyperedgeFixture(): CircuitGraphSnapshot {
  const output = port("source_0", "broadcast", "out");
  const inputs = [0, 1, 2].map((index) => port(`sink_${index}`, "broadcast", "in"));
  return graph(
    "hyperedge",
    [component("source"), component("sink")],
    [node("source_0", "source", [output]), ...inputs.map((terminal, index) => node(`sink_${index}`, "sink", [terminal]))],
    [output, ...inputs],
    [net("broadcast", "ad_hoc", [output.id, ...inputs.map((terminal) => terminal.id)])],
  );
}

export function hierarchyFixture(): CircuitGraphSnapshot {
  const input = port("pipeline_0", "request", "in");
  const output = port("pipeline_0", "response", "out");
  const boundaryIn: CircuitTerminal = {
    id: "boundary:port:request",
    label: "request",
    kind: "boundary_port",
    direction: "in",
    mapped_port_ids: [],
    declared_bounds: [],
    source_ref: source("boundary:request", "boundary_port"),
  };
  const boundaryOut: CircuitTerminal = {
    id: "boundary:port:response",
    label: "response",
    kind: "boundary_port",
    direction: "out",
    mapped_port_ids: [],
    declared_bounds: [],
    source_ref: source("boundary:response", "boundary_port"),
  };
  const result = graph(
    "hierarchy",
    [component("pipeline")],
    [node("pipeline_0", "pipeline", [input, output])],
    [boundaryIn, input, output, boundaryOut],
    [net("request", "ad_hoc", [boundaryIn.id, input.id]), net("response", "ad_hoc", [output.id, boundaryOut.id])],
  );
  result.breadcrumbs = [
    { id: "top", label: "top", vlnv: "example:fixture:top:1.0", source_ref: source("top", "design") },
  ];
  return result;
}

export function cycleFixture(): CircuitGraphSnapshot {
  const terminals: CircuitTerminal[] = [];
  const nodes: CircuitNode[] = [];
  for (let index = 0; index < 3; index += 1) {
    const input = port(`stage_${index}`, "in", "in");
    const output = port(`stage_${index}`, "out", "out");
    terminals.push(input, output);
    nodes.push(node(`stage_${index}`, "stage", [input, output]));
  }
  return graph(
    "cycle",
    [component("stage")],
    nodes,
    terminals,
    [0, 1, 2].map((index) => net(`feedback_${index}`, "ad_hoc", [`stage_${index}:port:out`, `stage_${(index + 1) % 3}:port:in`])),
  );
}

export function largeFixture(instanceCount = 200): CircuitGraphSnapshot {
  const terminals: CircuitTerminal[] = [];
  const nodes: CircuitNode[] = [];
  for (let index = 0; index < instanceCount; index += 1) {
    const input = port(`block_${index}`, "in", "in");
    const output = port(`block_${index}`, "out", "out");
    terminals.push(input, output);
    nodes.push(node(`block_${index}`, "block", [input, output]));
  }
  const nets: CircuitNet[] = [];
  for (let index = 0; index < instanceCount - 1; index += 1) {
    nets.push(net(`chain_${index}`, "ad_hoc", [`block_${index}:port:out`, `block_${index + 1}:port:in`]));
    nets.push(net(`skip_${index}`, "ad_hoc", [`block_${index}:port:out`, `block_${(index + 7) % instanceCount}:port:in`]));
  }
  return graph("large", [component("block")], nodes, terminals, nets);
}

export const fixtures = {
  simple: simpleFixture,
  mixed: mixedFixture,
  hyperedge: hyperedgeFixture,
  hierarchy: hierarchyFixture,
  cycle: cycleFixture,
  large: largeFixture,
};
