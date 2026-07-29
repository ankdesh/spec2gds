import type {
  CircuitDocument,
  CircuitLayout,
  CircuitNet,
  ComponentDefinition,
  Diagnostic,
  NetEndpoint,
  NetRoute,
  NodeGeometry,
  ParameterDefinition,
  ParameterValue,
  TerminalPlacement,
} from "./types.generated";

export interface CircuitDesignViewRef {
  id: string;
  label: string;
}

export interface CircuitComponentView {
  id: string;
  label: string;
  renderer_key: string;
}

export interface CircuitNodeView {
  id: string;
  label: string;
  component_id: string;
  component_vlnv?: string;
  terminal_ids: string[];
  display_name?: string;
  configuration_values: Record<string, string>;
}

export interface CircuitTerminalView {
  id: string;
  node_id?: string;
  label: string;
  kind: "interface" | "port" | "boundary_interface" | "boundary_port";
  direction?: "in" | "out";
  role?: string;
}

export interface CircuitNetView {
  id: string;
  label: string;
  kind: "ad_hoc";
  endpoints: Array<{ terminal_id: string }>;
}

export interface DiagramLayoutView {
  direction: "RIGHT" | "DOWN";
  node_geometry: Record<string, NodeGeometry>;
  terminal_placements: Record<string, TerminalPlacement>;
  net_routes: Record<string, NetRoute>;
}

/** Flattened, renderer-only projection. It is never persisted or used as the public protocol. */
export interface CircuitGraphView {
  protocol_version: "circuit-designer.v1";
  document_id: string;
  revision: string;
  design: CircuitDesignViewRef;
  components: CircuitComponentView[];
  nodes: CircuitNodeView[];
  terminals: CircuitTerminalView[];
  nets: CircuitNetView[];
  layout: DiagramLayoutView;
}

export const clone = <T>(value: T): T => structuredClone(value);

export function endpointTerminalKey(endpoint: NetEndpoint): string {
  return endpoint.kind === "instance"
    ? `${endpoint.instance_id}:${endpoint.terminal_id}`
    : `boundary:${endpoint.terminal_id}`;
}

export function endpointKey(endpoint: NetEndpoint): string {
  const terminal = endpointTerminalKey(endpoint);
  return endpoint.slice ? `${terminal}[${endpoint.slice.lsb}+${endpoint.slice.width}]` : terminal;
}

export function emptyLayout(): CircuitLayout {
  return {
    grid_size: 20,
    direction: "RIGHT",
    instance_geometry: {},
    terminal_placements: {},
    net_routes: {},
    label_geometry: {},
  };
}

export function terminalDefaultPlacement(direction: "input" | "output", order: number): TerminalPlacement {
  return { side: direction === "input" ? "WEST" : "EAST", order, locked: false };
}

export function projectDocument(document: CircuitDocument, revision = "draft"): CircuitGraphView {
  const components = new Map(document.components.map((component) => [component.id, component]));
  const terminals: CircuitTerminalView[] = [];
  const nodes: CircuitNodeView[] = [];
  for (const instance of document.design.instances) {
    const component = components.get(instance.component_id);
    if (!component) continue;
    const terminalIds = component.terminals.map((terminal) => `${instance.id}:${terminal.id}`);
    nodes.push({
      id: instance.id,
      label: instance.label,
      component_id: component.id,
      component_vlnv: component.appearance.renderer_key,
      terminal_ids: terminalIds,
      configuration_values: Object.fromEntries(
        Object.entries(instance.parameter_values).map(([key, value]) => [key, String(value)]),
      ),
    });
    terminals.push(...component.terminals.map((terminal) => ({
      id: `${instance.id}:${terminal.id}`,
      node_id: instance.id,
      label: terminal.label,
      kind: terminal.category === "interface" ? "interface" as const : "port" as const,
      direction: terminal.direction === "input" ? "in" as const : "out" as const,
    })));
  }
  terminals.push(...document.design.boundary_terminals.map((terminal) => ({
    id: `boundary:${terminal.id}`,
    label: terminal.label,
    kind: terminal.category === "interface" ? "boundary_interface" as const : "boundary_port" as const,
    direction: terminal.direction === "input" ? "in" as const : "out" as const,
  })));
  return {
    protocol_version: "circuit-designer.v1",
    document_id: document.document_id,
    revision,
    design: { id: document.design.id, label: document.design.label },
    components: document.components.map((component) => ({
      id: component.id,
      label: component.label,
      renderer_key: component.appearance.renderer_key,
    })),
    nodes,
    terminals,
    nets: document.design.nets.map((net) => ({
      id: net.id,
      label: net.label,
      kind: "ad_hoc",
      endpoints: [...new Set(net.endpoints.map(endpointTerminalKey))].map((terminal_id) => ({ terminal_id })),
    })),
    layout: {
      direction: document.layout.direction,
      node_geometry: clone(document.layout.instance_geometry),
      terminal_placements: clone(document.layout.terminal_placements),
      net_routes: clone(document.layout.net_routes),
    },
  };
}

function duplicates(values: string[]): string[] {
  const seen = new Set<string>();
  const repeated = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) repeated.add(value);
    seen.add(value);
  }
  return [...repeated].sort();
}

function diagnostic(
  severity: Diagnostic["severity"],
  code: string,
  message: string,
  element_key?: string,
  path?: string,
): Diagnostic {
  return { severity, code, message, ...(element_key ? { element_key } : {}), ...(path ? { path } : {}) };
}

function parameterValid(definition: ParameterDefinition, value: ParameterValue): boolean {
  if (definition.type === "string") return typeof value === "string";
  if (definition.type === "boolean") return typeof value === "boolean";
  if (definition.type === "number") {
    return typeof value === "number"
      && (definition.minimum === undefined || value >= definition.minimum)
      && (definition.maximum === undefined || value <= definition.maximum);
  }
  return typeof value === "string" && definition.values.includes(value);
}

function terminalForEndpoint(
  document: CircuitDocument,
  endpoint: NetEndpoint,
): { width: number; direction: "input" | "output"; key: string } | undefined {
  if (endpoint.kind === "boundary") {
    const terminal = document.design.boundary_terminals.find((item) => item.id === endpoint.terminal_id);
    return terminal && { width: terminal.width, direction: terminal.direction, key: endpointTerminalKey(endpoint) };
  }
  const instance = document.design.instances.find((item) => item.id === endpoint.instance_id);
  const component = document.components.find((item) => item.id === instance?.component_id);
  const terminal = component?.terminals.find((item) => item.id === endpoint.terminal_id);
  return terminal && { width: terminal.width, direction: terminal.direction, key: endpointTerminalKey(endpoint) };
}

function rangesOverlap(
  first: { lsb: number; width: number },
  second: { lsb: number; width: number },
): boolean {
  return first.lsb < second.lsb + second.width && second.lsb < first.lsb + first.width;
}

export function validateDocumentSemantics(document: CircuitDocument): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const componentIds = new Set(document.components.map((component) => component.id));
  for (const id of duplicates(document.components.map((component) => component.id))) {
    diagnostics.push(diagnostic("error", "duplicate_component_id", `Component ID is duplicated: ${id}`, id));
  }
  for (const component of document.components) {
    if (component.origin !== "local" && component.editable) {
      diagnostics.push(diagnostic("error", "invalid_component_editability", `Only local components may be editable: ${component.id}`, component.id));
    }
    for (const id of duplicates(component.terminals.map((terminal) => terminal.id))) {
      diagnostics.push(diagnostic("error", "duplicate_terminal_id", `Terminal ID is duplicated in ${component.id}: ${id}`, `${component.id}:${id}`));
    }
    for (const id of duplicates(component.parameters.map((parameter) => parameter.id))) {
      diagnostics.push(diagnostic("error", "duplicate_parameter_id", `Parameter ID is duplicated in ${component.id}: ${id}`, `${component.id}:${id}`));
    }
    for (const parameter of component.parameters) {
      if (parameter.type === "enum" && !parameter.values.includes(parameter.default)) {
        diagnostics.push(diagnostic("error", "invalid_parameter_default", `Enum default is not an allowed value: ${component.id}.${parameter.id}`, component.id));
      }
    }
  }

  const instanceIds = new Set(document.design.instances.map((instance) => instance.id));
  for (const id of duplicates(document.design.instances.map((instance) => instance.id))) {
    diagnostics.push(diagnostic("error", "duplicate_instance_id", `Instance ID is duplicated: ${id}`, id));
  }
  for (const instance of document.design.instances) {
    const component = document.components.find((item) => item.id === instance.component_id);
    if (!component) {
      diagnostics.push(diagnostic("error", "unknown_component", `Instance ${instance.id} references unknown component ${instance.component_id}.`, instance.id));
      continue;
    }
    const parameters = new Map(component.parameters.map((parameter) => [parameter.id, parameter]));
    for (const [id, value] of Object.entries(instance.parameter_values)) {
      const definition = parameters.get(id);
      if (!definition) diagnostics.push(diagnostic("error", "unknown_parameter", `Unknown parameter ${component.id}.${id}.`, instance.id));
      else if (!parameterValid(definition, value)) diagnostics.push(diagnostic("error", "invalid_parameter_value", `Invalid value for ${component.id}.${id}.`, instance.id));
    }
  }

  for (const id of duplicates(document.design.boundary_terminals.map((terminal) => terminal.id))) {
    diagnostics.push(diagnostic("error", "duplicate_boundary_terminal_id", `Boundary terminal ID is duplicated: ${id}`, id));
  }
  for (const id of duplicates(document.design.nets.map((net) => net.id))) {
    diagnostics.push(diagnostic("error", "duplicate_net_id", `Net ID is duplicated: ${id}`, id));
  }

  const occupied = new Map<string, Array<{ netId: string; range: { lsb: number; width: number } }>>();
  for (const net of document.design.nets) {
    if (net.endpoints.length < 2) {
      diagnostics.push(diagnostic("warning", "incomplete_net", `Net ${net.id} has fewer than two endpoints.`, net.id));
    }
    const widths: number[] = [];
    let sourceCount = 0;
    for (const [index, endpoint] of net.endpoints.entries()) {
      const terminal = terminalForEndpoint(document, endpoint);
      if (!terminal) {
        diagnostics.push(diagnostic("error", "unknown_endpoint", `Net ${net.id} endpoint ${endpointTerminalKey(endpoint)} does not exist.`, net.id, `/design/nets/${net.id}/endpoints/${index}`));
        continue;
      }
      const range = endpoint.slice ?? { lsb: 0, width: terminal.width };
      if (range.lsb + range.width > terminal.width) {
        diagnostics.push(diagnostic("error", "slice_out_of_range", `Endpoint slice exceeds terminal width on ${terminal.key}.`, net.id));
        continue;
      }
      const prior = occupied.get(terminal.key) ?? [];
      if (prior.some((item) => rangesOverlap(item.range, range) && item.netId !== net.id)) {
        diagnostics.push(diagnostic("error", "terminal_slice_in_multiple_nets", `Terminal slice ${endpointKey(endpoint)} belongs to more than one net.`, net.id));
      }
      prior.push({ netId: net.id, range });
      occupied.set(terminal.key, prior);
      widths.push(range.width);
      const isSource = endpoint.kind === "instance"
        ? terminal.direction === "output"
        : terminal.direction === "input";
      if (isSource) sourceCount += 1;
    }
    if (new Set(widths).size > 1) diagnostics.push(diagnostic("warning", "width_mismatch", `Net ${net.id} connects endpoint slices with different widths.`, net.id));
    if (sourceCount === 0 && net.endpoints.length > 1) diagnostics.push(diagnostic("warning", "net_without_source", `Net ${net.id} has no output/source endpoint.`, net.id));
    if (sourceCount > 1) diagnostics.push(diagnostic("warning", "multiple_net_sources", `Net ${net.id} has more than one output/source endpoint.`, net.id));
  }

  for (const key of Object.keys(document.layout.instance_geometry)) {
    if (!instanceIds.has(key)) diagnostics.push(diagnostic("error", "unknown_layout_instance", `Layout references unknown instance ${key}.`, key));
  }
  const terminalKeys = new Set<string>(document.design.boundary_terminals.map((terminal) => `boundary:${terminal.id}`));
  for (const instance of document.design.instances) {
    const component = document.components.find((item) => item.id === instance.component_id);
    for (const terminal of component?.terminals ?? []) terminalKeys.add(`${instance.id}:${terminal.id}`);
  }
  for (const key of Object.keys(document.layout.terminal_placements)) {
    if (!terminalKeys.has(key)) {
      diagnostics.push(diagnostic("error", "unknown_layout_terminal", `Layout references unknown terminal ${key}.`, key));
    }
  }
  const netIds = new Set(document.design.nets.map((net) => net.id));
  for (const key of Object.keys(document.layout.net_routes)) {
    if (!netIds.has(key)) diagnostics.push(diagnostic("error", "unknown_layout_net", `Layout references unknown net ${key}.`, key));
  }
  for (const net of document.design.nets) {
    const route = document.layout.net_routes[net.id];
    if (!route) continue;
    const vertices = new Map(route.vertices.map((vertex) => [vertex.id, vertex]));
    if (vertices.size !== route.vertices.length) {
      diagnostics.push(diagnostic("error", "duplicate_route_vertex", `Route for ${net.id} contains duplicate vertex IDs.`, net.id));
      continue;
    }
    const adjacency = new Map([...vertices.keys()].map((id) => [id, new Set<string>()]));
    const segmentKeys = new Set<string>();
    for (const segment of route.segments) {
      const start = vertices.get(segment.from_vertex);
      const end = vertices.get(segment.to_vertex);
      if (!start || !end) {
        diagnostics.push(diagnostic("error", "unknown_route_vertex", `Route for ${net.id} references an unknown vertex.`, net.id));
        continue;
      }
      const segmentKey = [start.id, end.id].sort().join("|");
      if (segmentKeys.has(segmentKey)) {
        diagnostics.push(diagnostic("error", "duplicate_route_segment", `Route for ${net.id} contains a duplicate segment.`, net.id));
      }
      segmentKeys.add(segmentKey);
      if (start.id === end.id || (start.point.x === end.point.x && start.point.y === end.point.y)) {
        diagnostics.push(diagnostic("error", "zero_length_route_segment", `Route for ${net.id} contains a zero-length segment.`, net.id));
      }
      if (start.point.x !== end.point.x && start.point.y !== end.point.y) {
        diagnostics.push(diagnostic("error", "diagonal_route_segment", `Route for ${net.id} contains a diagonal segment.`, net.id));
      }
      adjacency.get(start.id)?.add(end.id);
      adjacency.get(end.id)?.add(start.id);
    }
    if (route.vertices.length && route.segments.length !== route.vertices.length - 1) {
      diagnostics.push(diagnostic("error", "invalid_route_tree", `Route for ${net.id} is not a tree.`, net.id));
    }
    if (route.vertices.length) {
      const visited = new Set<string>();
      const pending = [route.vertices[0].id];
      while (pending.length) {
        const id = pending.pop()!;
        if (visited.has(id)) continue;
        visited.add(id);
        pending.push(...(adjacency.get(id) ?? []));
      }
      if (visited.size !== route.vertices.length) {
        diagnostics.push(diagnostic("error", "disconnected_route", `Route for ${net.id} is disconnected.`, net.id));
      }
    }
    const expected = [...new Set(net.endpoints.map(endpointTerminalKey))].sort();
    const actual = route.vertices
      .filter((vertex) => vertex.kind === "endpoint")
      .flatMap((vertex) => vertex.terminal_id ? [vertex.terminal_id] : [])
      .sort();
    if (expected.join("\0") !== actual.join("\0")) {
      diagnostics.push(diagnostic("error", "route_endpoint_mismatch", `Route endpoints do not match net ${net.id}.`, net.id));
    }
    for (const vertex of route.vertices) {
      const degree = adjacency.get(vertex.id)?.size ?? 0;
      if (vertex.kind === "endpoint" && degree !== 1) {
        diagnostics.push(diagnostic("error", "invalid_endpoint_degree", `Route endpoint ${vertex.id} must have degree one.`, net.id));
      } else if (vertex.kind === "bend" && degree !== 2) {
        diagnostics.push(diagnostic("error", "invalid_bend_degree", `Route bend ${vertex.id} must have degree two.`, net.id));
      } else if (vertex.kind === "junction" && degree < 3) {
        diagnostics.push(diagnostic("error", "invalid_junction_degree", `Route junction ${vertex.id} must have degree three or greater.`, net.id));
      }
    }
  }
  for (const instance of document.design.instances) {
    if (!componentIds.has(instance.component_id)) continue;
    if (!document.layout.instance_geometry[instance.id]) diagnostics.push(diagnostic("warning", "missing_instance_geometry", `Instance ${instance.id} needs automatic placement.`, instance.id));
  }
  return diagnostics;
}

export function connectedInstanceIds(document: CircuitDocument, instanceId: string): string[] {
  const connected = new Set<string>();
  for (const net of document.design.nets) {
    if (!net.endpoints.some((endpoint) => endpoint.kind === "instance" && endpoint.instance_id === instanceId)) continue;
    for (const endpoint of net.endpoints) {
      if (endpoint.kind === "instance" && endpoint.instance_id !== instanceId) connected.add(endpoint.instance_id);
    }
  }
  return [...connected].sort();
}

export function componentById(document: CircuitDocument, componentId: string): ComponentDefinition | undefined {
  return document.components.find((component) => component.id === componentId);
}

export function netById(document: CircuitDocument, netId: string): CircuitNet | undefined {
  return document.design.nets.find((net) => net.id === netId);
}
