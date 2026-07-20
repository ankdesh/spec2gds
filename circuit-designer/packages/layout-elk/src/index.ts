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
  gridSize?: number;
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
  const inset = 62 + placement.order * 18;
  if (placement.side === "EAST") return { x: round(geometry.x + geometry.width), y: round(geometry.y + Math.min(inset, geometry.height - 10)) };
  if (placement.side === "WEST") return { x: round(geometry.x), y: round(geometry.y + Math.min(inset, geometry.height - 10)) };
  if (placement.side === "NORTH") return { x: round(geometry.x + Math.min(inset, geometry.width - 10)), y: round(geometry.y) };
  return { x: round(geometry.x + Math.min(inset, geometry.width - 10)), y: round(geometry.y + geometry.height) };
}

function terminalStubPoint(point: Point, placement: TerminalPlacement, distance = 24): Point {
  if (placement.side === "EAST") return { x: round(point.x + distance), y: point.y };
  if (placement.side === "WEST") return { x: round(point.x - distance), y: point.y };
  if (placement.side === "NORTH") return { x: point.x, y: round(point.y - distance) };
  return { x: point.x, y: round(point.y + distance) };
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
    const placement = placements[id];
    const point = terminalPoint(terminal, geometry, placement);
    return { id, point, stub: terminalStubPoint(point, placement) };
  });
  const axis = direction === "RIGHT"
    ? round((Math.min(...endpoints.map((item) => item.stub.x)) + Math.max(...endpoints.map((item) => item.stub.x))) / 2)
    : round((Math.min(...endpoints.map((item) => item.stub.y)) + Math.max(...endpoints.map((item) => item.stub.y))) / 2);
  const vertices: RouteVertex[] = [];
  const segments: NetRoute["segments"] = [];
  const trunkIds: string[] = [];
  for (const [index, endpoint] of endpoints.entries()) {
    const endpointId = `endpoint:${index}`;
    const stubId = `stub:${index}`;
    const trunkId = `trunk:${index}`;
    const trunkPoint = direction === "RIGHT" ? { x: axis, y: endpoint.stub.y } : { x: endpoint.stub.x, y: axis };
    vertices.push({ id: endpointId, kind: "endpoint", point: endpoint.point, terminal_id: endpoint.id });
    vertices.push({ id: stubId, kind: "bend", point: endpoint.stub });
    vertices.push({ id: trunkId, kind: endpoints.length > 2 ? "junction" : "bend", point: trunkPoint });
    segments.push({ from_vertex: endpointId, to_vertex: stubId });
    if (endpoint.stub.x !== trunkPoint.x || endpoint.stub.y !== trunkPoint.y) segments.push({ from_vertex: stubId, to_vertex: trunkId });
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

function routeNetFromElk(
  terminalIds: string[],
  elkEdges: Array<{ sections?: Array<{ startPoint: Point; endPoint: Point; bendPoints?: Point[] }> }>,
  terminals: Map<string, CircuitTerminal>,
  nodeGeometry: Record<string, NodeGeometry>,
  boundaryGeometry: Record<string, NodeGeometry>,
  placements: Record<string, TerminalPlacement>,
): NetRoute | undefined {
  if (terminalIds.length < 2 || elkEdges.length !== terminalIds.length - 1 || elkEdges.some((edge) => !edge.sections?.length)) return undefined;
  const vertices: RouteVertex[] = [];
  const segments: NetRoute["segments"] = [];
  const byCoordinate = new Map<string, string>();
  const segmentKeys = new Set<string>();
  const endpointIds = new Map<string, string>();
  const pointFor = (terminalId: string) => {
    const terminal = terminals.get(terminalId)!;
    const placement = placements[terminalId];
    const point = terminalPoint(terminal, terminal.node_id ? nodeGeometry[terminal.node_id] : boundaryGeometry[terminalId], placement);
    return { point, stub: terminalStubPoint(point, placement) };
  };
  const ensure = (point: Point, terminalId?: string) => {
    if (terminalId && endpointIds.has(terminalId)) return endpointIds.get(terminalId)!;
    const normalized = { x: round(point.x), y: round(point.y) };
    const key = `${normalized.x}:${normalized.y}`;
    if (!terminalId && byCoordinate.has(key)) return byCoordinate.get(key)!;
    const id = terminalId ? `endpoint:${endpointIds.size}` : `route:${byCoordinate.size}`;
    vertices.push({ id, kind: terminalId ? "endpoint" : "bend", point: normalized, ...(terminalId ? { terminal_id: terminalId } : {}) });
    if (terminalId) endpointIds.set(terminalId, id);
    else byCoordinate.set(key, id);
    return id;
  };
  const connect = (from: string, to: string) => {
    if (from === to) return;
    const key = [from, to].sort().join("|");
    if (!segmentKeys.has(key)) { segmentKeys.add(key); segments.push({ from_vertex: from, to_vertex: to }); }
  };
  const bridge = (fromId: string, from: Point, toId: string, to: Point) => {
    if (from.x === to.x || from.y === to.y) { connect(fromId, toId); return; }
    const bend = ensure({ x: to.x, y: from.y });
    connect(fromId, bend); connect(bend, toId);
  };
  const sourceTerminal = terminalIds[0];
  const branches = new Map<string, { point: Point; endpointId: string; stub: Point; stubId: string }>();
  const branch = (terminalId: string) => {
    const existing = branches.get(terminalId);
    if (existing) return existing;
    const { point, stub } = pointFor(terminalId);
    const endpointId = ensure(point, terminalId);
    const stubId = `stub:${branches.size}`;
    vertices.push({ id: stubId, kind: "bend", point: stub });
    byCoordinate.set(`${stub.x}:${stub.y}`, stubId);
    connect(endpointId, stubId);
    const value = { point, endpointId, stub, stubId };
    branches.set(terminalId, value);
    return value;
  };
  const source = branch(sourceTerminal);
  elkEdges.forEach((edge, index) => {
    const targetTerminal = terminalIds[index + 1];
    const target = branch(targetTerminal);
    const section = edge.sections![0];
    const elkPoints = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint].map((point) => ({ x: round(point.x), y: round(point.y) }));
    const ids = elkPoints.map((point) => ensure(point));
    bridge(source.stubId, source.stub, ids[0], elkPoints[0]);
    for (let pointIndex = 1; pointIndex < ids.length; pointIndex += 1) connect(ids[pointIndex - 1], ids[pointIndex]);
    bridge(ids.at(-1)!, elkPoints.at(-1)!, target.stubId, target.stub);
  });
  const degree = new Map<string, number>();
  for (const segment of segments) {
    degree.set(segment.from_vertex, (degree.get(segment.from_vertex) ?? 0) + 1);
    degree.set(segment.to_vertex, (degree.get(segment.to_vertex) ?? 0) + 1);
  }
  return { vertices: vertices.map((vertex) => vertex.kind === "bend" && (degree.get(vertex.id) ?? 0) > 2 ? { ...vertex, kind: "junction" } : vertex), segments };
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
  const direction = graph.layout?.direction ?? options.direction ?? "RIGHT";
  const nodeWidth = options.nodeWidth ?? 180;
  const nodeHeight = options.nodeHeight ?? 84;
  const spacing = options.spacing ?? 72;
  const gridSize = options.gridSize ?? 20;
  const snap = (value: number) => round(Math.round(value / gridSize) * gridSize);
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  const boundaryTerminals = graph.terminals.filter((terminal) => !terminal.node_id);
  const nodeHeightFor = (nodeId: string) => {
    const sideCounts = new Map<string, number>();
    for (const terminal of graph.terminals.filter((item) => item.node_id === nodeId)) {
      const side = terminalSide(terminal);
      sideCounts.set(side, (sideCounts.get(side) ?? 0) + 1);
    }
    return Math.max(nodeHeight, 78 + Math.max(0, ...sideCounts.values()) * 18);
  };
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
      ...[...graph.nodes].sort((a, b) => a.id.localeCompare(b.id)).map((node) => ({ id: node.id, width: nodeWidth, height: nodeHeightFor(node.id) })),
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
      x: snap(child.x ?? 0), y: snap(child.y ?? 0),
      width: round(child.width ?? nodeWidth), height: round(child.height ?? nodeHeight), pinned: false,
    };
    if (child.id.startsWith("boundary:")) boundaryGeometry[child.id.slice("boundary:".length)] = geometry;
    else nodeGeometry[child.id] = geometry;
  }
  for (const [nodeId, geometry] of Object.entries(graph.layout?.node_geometry ?? {})) {
    nodeGeometry[nodeId] = { ...geometry, x: snap(geometry.x), y: snap(geometry.y) };
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
    const ids = net.endpoints.map((endpoint) => endpoint.terminal_id);
    // ELK remains responsible for node ordering and obstacle-aware placement.
    // Electrical nets use one deterministic route tree instead of merging
    // several ELK two-node edge sections, which creates hairpins and duplicate
    // parallel trunks for fanout nets.
    netRoutes[net.id] = routeNet(ids, terminals, nodeGeometry, boundaryGeometry, terminalPlacements, direction);
  }
  return {
    layout: {
      direction,
      node_geometry: nodeGeometry,
      terminal_placements: { ...terminalPlacements, ...(graph.layout?.terminal_placements ?? {}) },
      net_routes: { ...netRoutes, ...(graph.layout?.net_routes ?? {}) },
    },
    boundary_geometry: boundaryGeometry,
    elapsed_ms: round(performance.now() - started),
  };
}
