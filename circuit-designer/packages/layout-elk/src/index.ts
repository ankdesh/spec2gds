import type { ElkNode } from "elkjs/lib/elk.bundled.js";
import type {
  CircuitGraphSnapshot,
  CircuitTerminal,
  DiagramLayout,
  NetRoute,
  NodeGeometry,
  Point,
  RouteVertex,
  TerminalPlacement,
} from "@spec2gds/circuit-core";

export interface LayoutOptions {
  direction?: "RIGHT" | "DOWN";
  nodeWidth?: number;
  nodeHeight?: number;
  spacing?: number;
}

export interface LayoutResult {
  layout: DiagramLayout;
  boundary_geometry: Record<string, NodeGeometry>;
  elapsed_ms: number;
}

export interface ElkLayoutEngine {
  layout(graph: ElkNode): Promise<ElkNode>;
}

const round = (value: number) => Math.round(value * 100) / 100;

function terminalSide(terminal: CircuitTerminal): TerminalPlacement["side"] {
  if (terminal.role === "initiator" || terminal.direction === "out") return "EAST";
  if (terminal.role === "target" || terminal.direction === "in") return "WEST";
  return "SOUTH";
}

function terminalPoint(
  terminal: CircuitTerminal,
  geometry: NodeGeometry,
  placement: TerminalPlacement,
): Point {
  const inset = 18 + placement.order * 14;
  if (placement.side === "EAST") return { x: round(geometry.x + geometry.width), y: round(geometry.y + Math.min(inset, geometry.height - 10)) };
  if (placement.side === "WEST") return { x: round(geometry.x), y: round(geometry.y + Math.min(inset, geometry.height - 10)) };
  if (placement.side === "NORTH") return { x: round(geometry.x + Math.min(inset, geometry.width - 10)), y: round(geometry.y) };
  return { x: round(geometry.x + Math.min(inset, geometry.width - 10)), y: round(geometry.y + geometry.height) };
}

function routeNet(
  terminalIds: string[],
  terminals: Map<string, CircuitTerminal>,
  nodeGeometry: Record<string, NodeGeometry>,
  boundaryGeometry: Record<string, NodeGeometry>,
  placements: Record<string, TerminalPlacement>,
  direction: "RIGHT" | "DOWN",
): NetRoute {
  const endpoints = terminalIds.map((id) => {
    const terminal = terminals.get(id)!;
    const geometry = terminal.node_id ? nodeGeometry[terminal.node_id] : boundaryGeometry[id];
    return { id, point: terminalPoint(terminal, geometry, placements[id]) };
  });
  const axis = direction === "RIGHT"
    ? round((Math.min(...endpoints.map((item) => item.point.x)) + Math.max(...endpoints.map((item) => item.point.x))) / 2)
    : round((Math.min(...endpoints.map((item) => item.point.y)) + Math.max(...endpoints.map((item) => item.point.y))) / 2);
  const vertices: RouteVertex[] = [];
  const segments: NetRoute["segments"] = [];
  const trunkIds: string[] = [];
  for (const [index, endpoint] of endpoints.entries()) {
    const endpointId = `endpoint:${index}`;
    const trunkId = `trunk:${index}`;
    const trunkPoint = direction === "RIGHT" ? { x: axis, y: endpoint.point.y } : { x: endpoint.point.x, y: axis };
    vertices.push({ id: endpointId, kind: "endpoint", point: endpoint.point, terminal_id: endpoint.id });
    vertices.push({ id: trunkId, kind: endpoints.length > 2 ? "junction" : "bend", point: trunkPoint });
    segments.push({ from_vertex: endpointId, to_vertex: trunkId });
    trunkIds.push(trunkId);
  }
  const ordered = trunkIds
    .map((id) => vertices.find((vertex) => vertex.id === id)!)
    .sort((a, b) => direction === "RIGHT" ? a.point.y - b.point.y : a.point.x - b.point.x);
  for (let index = 1; index < ordered.length; index += 1) {
    if (ordered[index - 1].point.x !== ordered[index].point.x || ordered[index - 1].point.y !== ordered[index].point.y) {
      segments.push({ from_vertex: ordered[index - 1].id, to_vertex: ordered[index].id });
    }
  }
  return { vertices, segments };
}

export async function layoutCircuitGraph(
  graph: CircuitGraphSnapshot,
  options: LayoutOptions = {},
): Promise<LayoutResult> {
  const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
  return layoutCircuitGraphWithEngine(graph, new ELK(), options);
}

export async function layoutCircuitGraphWithEngine(
  graph: CircuitGraphSnapshot,
  engine: ElkLayoutEngine,
  options: LayoutOptions = {},
): Promise<LayoutResult> {
  const started = performance.now();
  const direction = options.direction ?? "RIGHT";
  const nodeWidth = options.nodeWidth ?? 180;
  const nodeHeight = options.nodeHeight ?? 84;
  const spacing = options.spacing ?? 72;
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  const boundaryTerminals = graph.terminals.filter((terminal) => !terminal.node_id);
  const owner = (terminalId: string) => terminals.get(terminalId)?.node_id ?? `boundary:${terminalId}`;
  const elkGraph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": direction,
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": String(spacing),
      "elk.layered.spacing.nodeNodeBetweenLayers": String(spacing + 32),
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.randomSeed": "1",
    },
    children: [
      ...[...graph.nodes].sort((a, b) => a.id.localeCompare(b.id)).map((node) => ({ id: node.id, width: nodeWidth, height: nodeHeight })),
      ...boundaryTerminals.map((terminal) => ({ id: `boundary:${terminal.id}`, width: 18, height: 36 })),
    ],
    edges: [...graph.nets].sort((a, b) => a.id.localeCompare(b.id)).flatMap((net) => {
      const owners = [...new Set(net.endpoints.map((endpoint) => owner(endpoint.terminal_id)))];
      if (owners.length < 2) return [];
      return owners.slice(1).map((target, index) => ({ id: `${net.id}:${index}`, sources: [owners[0]], targets: [target] }));
    }),
  };
  const laidOut = await engine.layout(elkGraph);
  const nodeGeometry: Record<string, NodeGeometry> = {};
  const boundaryGeometry: Record<string, NodeGeometry> = {};
  for (const child of laidOut.children ?? []) {
    const geometry = {
      x: round(child.x ?? 0), y: round(child.y ?? 0),
      width: round(child.width ?? nodeWidth), height: round(child.height ?? nodeHeight), pinned: false,
    };
    if (child.id.startsWith("boundary:")) boundaryGeometry[child.id.slice("boundary:".length)] = geometry;
    else nodeGeometry[child.id] = geometry;
  }
  const terminalPlacements: Record<string, TerminalPlacement> = {};
  const orderByOwnerSide = new Map<string, number>();
  for (const terminal of [...graph.terminals].sort((a, b) => a.id.localeCompare(b.id))) {
    const side = terminal.node_id ? terminalSide(terminal) : terminal.direction === "out" ? "EAST" : "WEST";
    const key = `${terminal.node_id ?? terminal.id}:${side}`;
    const order = orderByOwnerSide.get(key) ?? 0;
    orderByOwnerSide.set(key, order + 1);
    terminalPlacements[terminal.id] = { side, order };
  }
  const netRoutes: Record<string, NetRoute> = {};
  for (const net of graph.nets) {
    netRoutes[net.id] = routeNet(net.endpoints.map((endpoint) => endpoint.terminal_id), terminals, nodeGeometry, boundaryGeometry, terminalPlacements, direction);
  }
  return {
    layout: { direction, node_geometry: nodeGeometry, terminal_placements: terminalPlacements, net_routes: netRoutes },
    boundary_geometry: boundaryGeometry,
    elapsed_ms: round(performance.now() - started),
  };
}
