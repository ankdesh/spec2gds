import type {
  CircuitDocument,
  CircuitGraphView as CircuitGraphSnapshot,
  CircuitTerminalView as CircuitTerminal,
  DiagramLayoutView as DiagramLayout,
  NetRoute,
  NodeGeometry,
  Point,
  TerminalPlacement,
} from "@spec2gds/circuit-core";
import { clone, projectDocument, reanchorRouteEndpoints, simplifyRoute, type EndpointAnchor } from "@spec2gds/circuit-core";
import { routeOrthogonalNets, type RouteObstacle, type RouteRequest } from "./router";

export * from "./router";
export * from "./worker-protocol";
export * from "./worker-client";

export interface LayoutOptions {
  direction?: "RIGHT" | "DOWN";
  nodeWidth?: number;
  nodeHeight?: number;
  spacing?: number;
  gridSize?: number;
  preserveNodeGeometry?: "all" | "pinned" | "none";
}

export interface LayoutResult {
  layout: DiagramLayout;
  boundary_geometry: Record<string, NodeGeometry>;
  elapsed_ms: number;
}

export interface CircuitDocumentLayoutResult extends LayoutResult {
  document: CircuitDocument;
}

const round = (value: number) => Math.round(value * 100) / 100;
const snap = (value: number, grid: number) => Math.round(value / grid) * grid;

export function terminalSide(terminal: CircuitTerminal): TerminalPlacement["side"] {
  if (!terminal.node_id) {
    if (terminal.role === "initiator" || terminal.direction === "in") return "EAST";
    if (terminal.role === "target" || terminal.direction === "out") return "WEST";
  }
  if (terminal.role === "initiator" || terminal.direction === "out") return "EAST";
  if (terminal.role === "target" || terminal.direction === "in") return "WEST";
  return "SOUTH";
}

export function terminalOffset(placement: TerminalPlacement): number {
  return 60 + placement.order * 20;
}

export function terminalPoint(
  _terminal: CircuitTerminal,
  geometry: NodeGeometry,
  placement: TerminalPlacement,
): Point {
  const inset = terminalOffset(placement);
  if (placement.side === "EAST") return { x: round(geometry.x + geometry.width), y: round(geometry.y + Math.min(inset, geometry.height - 20)) };
  if (placement.side === "WEST") return { x: round(geometry.x), y: round(geometry.y + Math.min(inset, geometry.height - 20)) };
  if (placement.side === "NORTH") return { x: round(geometry.x + Math.min(inset, geometry.width - 20)), y: round(geometry.y) };
  return { x: round(geometry.x + Math.min(inset, geometry.width - 20)), y: round(geometry.y + geometry.height) };
}

export function terminalStubPoint(point: Point, placement: TerminalPlacement, distance = 20): Point {
  if (placement.side === "EAST") return { x: round(point.x + distance), y: point.y };
  if (placement.side === "WEST") return { x: round(point.x - distance), y: point.y };
  if (placement.side === "NORTH") return { x: point.x, y: round(point.y - distance) };
  return { x: point.x, y: round(point.y + distance) };
}

function effectivePlacements(graph: CircuitGraphSnapshot): Record<string, TerminalPlacement> {
  const placements: Record<string, TerminalPlacement> = {};
  const nextOrder = new Map<string, number>();
  for (const terminal of [...graph.terminals].sort((a, b) => a.id.localeCompare(b.id))) {
    const saved = graph.layout?.terminal_placements?.[terminal.id];
    const side = saved?.side ?? terminalSide(terminal);
    const owner = terminal.node_id ?? `boundary:${side}`;
    const key = `${owner}:${side}`;
    const order = saved?.order ?? nextOrder.get(key) ?? 0;
    placements[terminal.id] = saved ?? { side, order, locked: false };
    nextOrder.set(key, Math.max(nextOrder.get(key) ?? 0, order + 1));
  }
  return placements;
}

function nodeDimensions(
  graph: CircuitGraphSnapshot,
  placements: Record<string, TerminalPlacement>,
  nodeId: string,
  minimumWidth: number,
  minimumHeight: number,
): Pick<NodeGeometry, "width" | "height"> {
  const counts: Record<TerminalPlacement["side"], number> = { NORTH: 0, EAST: 0, SOUTH: 0, WEST: 0 };
  for (const terminal of graph.terminals.filter((item) => item.node_id === nodeId)) {
    const placement = placements[terminal.id];
    counts[placement.side] = Math.max(counts[placement.side], placement.order + 1);
  }
  return {
    width: Math.max(minimumWidth, 120 + Math.max(counts.NORTH, counts.SOUTH) * 20),
    height: Math.max(minimumHeight, 80 + Math.max(counts.EAST, counts.WEST) * 20),
  };
}

function directedOwners(graph: CircuitGraphSnapshot): { adjacency: Map<string, Set<string>>; incoming: Map<string, number> } {
  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  const adjacency = new Map([...nodeIds].map((id) => [id, new Set<string>()]));
  const incoming = new Map([...nodeIds].map((id) => [id, 0]));
  for (const net of graph.nets) {
    const owners = [...new Set(net.endpoints.map((endpoint) => terminals.get(endpoint.terminal_id)?.node_id).filter((id): id is string => Boolean(id && nodeIds.has(id))))];
    if (owners.length < 2) continue;
    const sources = owners.filter((owner) => net.endpoints.some((endpoint) => {
      const terminal = terminals.get(endpoint.terminal_id);
      return terminal?.node_id === owner && (terminal.direction === "out" || terminal.role === "initiator");
    }));
    const roots = sources.length ? sources : [owners[0]];
    for (const source of roots) for (const target of owners) {
      if (source === target || adjacency.get(source)!.has(target)) continue;
      adjacency.get(source)!.add(target);
      incoming.set(target, (incoming.get(target) ?? 0) + 1);
    }
  }
  return { adjacency, incoming };
}

function weakComponents(nodeIds: string[], adjacency: Map<string, Set<string>>): string[][] {
  const undirected = new Map(nodeIds.map((id) => [id, new Set<string>()]));
  for (const [source, targets] of adjacency) for (const target of targets) {
    undirected.get(source)?.add(target);
    undirected.get(target)?.add(source);
  }
  const remaining = new Set(nodeIds);
  const result: string[][] = [];
  while (remaining.size) {
    const seed = [...remaining].sort()[0];
    const queue = [seed];
    const component: string[] = [];
    remaining.delete(seed);
    while (queue.length) {
      const current = queue.shift()!;
      component.push(current);
      for (const neighbour of undirected.get(current) ?? []) if (remaining.delete(neighbour)) queue.push(neighbour);
    }
    result.push(component.sort());
  }
  return result;
}

function placeNodes(
  graph: CircuitGraphSnapshot,
  placements: Record<string, TerminalPlacement>,
  options: Required<Pick<LayoutOptions, "direction" | "nodeWidth" | "nodeHeight" | "spacing" | "gridSize" | "preserveNodeGeometry">>,
): Record<string, NodeGeometry> {
  const { adjacency, incoming } = directedOwners(graph);
  const components = weakComponents(graph.nodes.map((node) => node.id), adjacency);
  const result: Record<string, NodeGeometry> = {};
  let componentOffset = 80;
  for (const component of components) {
    const roots = component.filter((id) => (incoming.get(id) ?? 0) === 0);
    const queue = (roots.length ? roots : [component[0]]).map((id) => ({ id, rank: 0 }));
    const rank = new Map<string, number>();
    while (queue.length) {
      const current = queue.shift()!;
      if (rank.has(current.id) && rank.get(current.id)! <= current.rank) continue;
      rank.set(current.id, current.rank);
      const neighbours = new Set<string>(adjacency.get(current.id) ?? []);
      for (const [candidate, targets] of adjacency) if (targets.has(current.id)) neighbours.add(candidate);
      for (const neighbour of neighbours) if (component.includes(neighbour) && !rank.has(neighbour)) queue.push({ id: neighbour, rank: current.rank + 1 });
    }
    const ranks = new Map<number, string[]>();
    for (const id of component) {
      const value = rank.get(id) ?? 0;
      if (!ranks.has(value)) ranks.set(value, []);
      ranks.get(value)!.push(id);
    }
    let componentExtent = 0;
    let primary = 80;
    for (const [, ids] of [...ranks].sort((a, b) => a[0] - b[0])) {
      ids.sort();
      let secondary = componentOffset;
      let primaryExtent = 0;
      ids.forEach((id) => {
        const dimensions = nodeDimensions(graph, placements, id, options.nodeWidth, options.nodeHeight);
        result[id] = options.direction === "RIGHT"
          ? { x: snap(primary, options.gridSize), y: snap(secondary, options.gridSize), ...dimensions, pinned: false }
          : { x: snap(secondary, options.gridSize), y: snap(primary, options.gridSize), ...dimensions, pinned: false };
        componentExtent = Math.max(componentExtent, secondary + (options.direction === "RIGHT" ? dimensions.height : dimensions.width));
        secondary += (options.direction === "RIGHT" ? dimensions.height : dimensions.width) + options.spacing + 40;
        primaryExtent = Math.max(primaryExtent, options.direction === "RIGHT" ? dimensions.width : dimensions.height);
      });
      primary += primaryExtent + options.spacing + 100;
    }
    componentOffset = snap(componentExtent + options.spacing + 80, options.gridSize);
  }
  const preserve = options.preserveNodeGeometry;
  for (const [nodeId, geometry] of Object.entries(graph.layout?.node_geometry ?? {})) {
    if (preserve === "none" || (preserve === "pinned" && !geometry.pinned)) continue;
    result[nodeId] = {
      ...geometry,
      x: snap(geometry.x, options.gridSize),
      y: snap(geometry.y, options.gridSize),
    };
  }
  return result;
}

function placeBoundaries(
  graph: CircuitGraphSnapshot,
  geometry: Record<string, NodeGeometry>,
  placements: Record<string, TerminalPlacement>,
  grid: number,
): Record<string, NodeGeometry> {
  const values = Object.values(geometry);
  const minX = Math.min(...values.map((item) => item.x), 80);
  const minY = Math.min(...values.map((item) => item.y), 80);
  const maxX = Math.max(...values.map((item) => item.x + item.width), 260);
  const maxY = Math.max(...values.map((item) => item.y + item.height), 180);
  const result: Record<string, NodeGeometry> = {};
  const sideOrders: Record<TerminalPlacement["side"], number> = { NORTH: 0, EAST: 0, SOUTH: 0, WEST: 0 };
  for (const terminal of graph.terminals.filter((item) => !item.node_id).sort((a, b) => a.id.localeCompare(b.id))) {
    const side = placements[terminal.id].side;
    const order = sideOrders[side]++;
    if (side === "EAST") result[terminal.id] = { x: snap(minX - 120, grid), y: snap(minY + order * 80, grid), width: 20, height: 40, pinned: false };
    else if (side === "WEST") result[terminal.id] = { x: snap(maxX + 100, grid), y: snap(minY + order * 80, grid), width: 20, height: 40, pinned: false };
    else if (side === "SOUTH") result[terminal.id] = { x: snap(minX + order * 80, grid), y: snap(minY - 100, grid), width: 40, height: 20, pinned: false };
    else result[terminal.id] = { x: snap(minX + order * 80, grid), y: snap(maxY + 80, grid), width: 40, height: 20, pinned: false };
  }
  return result;
}

function terminalAnchors(
  terminalIds: string[],
  terminals: Map<string, CircuitTerminal>,
  nodeGeometry: Record<string, NodeGeometry>,
  boundaryGeometry: Record<string, NodeGeometry>,
  placements: Record<string, TerminalPlacement>,
): Record<string, EndpointAnchor> {
  return Object.fromEntries(terminalIds.map((id) => {
    const terminal = terminals.get(id)!;
    const geometry = terminal.node_id ? nodeGeometry[terminal.node_id] : boundaryGeometry[id];
    const placement = placements[id] ?? { side: terminalSide(terminal), order: 0, locked: false };
    const point = terminalPoint(terminal, geometry, placement);
    return [id, { point, stub: terminalStubPoint(point, placement) }];
  }));
}

function routeRequests(
  graph: CircuitGraphSnapshot,
  netIds: Set<string>,
  nodeGeometry: Record<string, NodeGeometry>,
  boundaryGeometry: Record<string, NodeGeometry>,
  placements: Record<string, TerminalPlacement>,
): RouteRequest[] {
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  return graph.nets.filter((net) => netIds.has(net.id)).map((net) => {
    const ids = net.endpoints.map((endpoint) => endpoint.terminal_id);
    const anchors = terminalAnchors(ids, terminals, nodeGeometry, boundaryGeometry, placements);
    return {
      netId: net.id,
      anchors: ids.map((id) => {
        const terminal = terminals.get(id)!;
        return {
          terminalId: id,
          ...anchors[id],
          source: terminal.direction === "out" || terminal.role === "initiator" || (!terminal.node_id && terminal.direction === "in"),
        };
      }),
    };
  });
}

function obstacles(nodeGeometry: Record<string, NodeGeometry>, boundaryGeometry: Record<string, NodeGeometry>): RouteObstacle[] {
  return [
    ...Object.entries(nodeGeometry).map(([id, geometry]) => ({ id, geometry })),
    ...Object.entries(boundaryGeometry).map(([id, geometry]) => ({ id: `boundary:${id}`, geometry })),
  ];
}

const hasLocks = (route: NetRoute | undefined) => Boolean(route?.segments.some((segment) => segment.locked) || route?.vertices.some((vertex) => vertex.locked));

/** Route selected, unlocked nets together without moving any block or port. */
export function routeCircuitNets(
  graph: CircuitGraphSnapshot,
  layout: DiagramLayout,
  boundaryGeometry: Record<string, NodeGeometry>,
  netIds = graph.nets.map((net) => net.id),
  preserveConstraints = true,
): Record<string, NetRoute> {
  const selected = new Set(netIds);
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  const placements = { ...effectivePlacements(graph), ...(layout.terminal_placements ?? {}) };
  const nodeGeometry = layout.node_geometry ?? {};
  const fixedRoutes: Record<string, NetRoute> = {};
  const preserved: Record<string, NetRoute> = {};
  const reroute = new Set<string>();
  for (const net of graph.nets) {
    const previous = layout.net_routes?.[net.id];
    if (!selected.has(net.id)) {
      if (previous) fixedRoutes[net.id] = previous;
      continue;
    }
    if (preserveConstraints && previous && hasLocks(previous)) {
      const ids = net.endpoints.map((endpoint) => endpoint.terminal_id);
      const anchored = simplifyRoute(reanchorRouteEndpoints(previous, terminalAnchors(ids, terminals, nodeGeometry, boundaryGeometry, placements)));
      fixedRoutes[net.id] = anchored;
      preserved[net.id] = anchored;
    } else reroute.add(net.id);
  }
  return {
    ...preserved,
    ...routeOrthogonalNets(routeRequests(graph, reroute, nodeGeometry, boundaryGeometry, placements), obstacles(nodeGeometry, boundaryGeometry), {
      gridSize: 20,
      fixedRoutes,
    }),
  };
}

/** Reroute unlocked attached nets after a component drag; retain locked routes. */
export function reanchorRoutesForNode(
  graph: CircuitGraphSnapshot,
  layout: DiagramLayout,
  boundaryGeometry: Record<string, NodeGeometry>,
  nodeId: string,
  geometry: NodeGeometry,
): Record<string, NetRoute> {
  const terminalIds = new Set(graph.terminals.filter((terminal) => terminal.node_id === nodeId).map((terminal) => terminal.id));
  const netIds = graph.nets.filter((net) => net.endpoints.some((endpoint) => terminalIds.has(endpoint.terminal_id))).map((net) => net.id);
  const draft = { ...layout, node_geometry: { ...(layout.node_geometry ?? {}), [nodeId]: geometry } };
  return routeCircuitNets(graph, draft, boundaryGeometry, netIds, true);
}

export function autoSizeNodeGeometry(
  graph: CircuitGraphSnapshot,
  layout: DiagramLayout,
  nodeId: string,
  minimumWidth = 180,
  minimumHeight = 100,
): NodeGeometry | undefined {
  const current = layout.node_geometry?.[nodeId];
  if (!current) return undefined;
  const placements = { ...effectivePlacements(graph), ...(layout.terminal_placements ?? {}) };
  return { ...current, ...nodeDimensions(graph, placements, nodeId, minimumWidth, minimumHeight) };
}

/** Deterministic grid placement followed by one global obstacle-aware router. */
export async function layoutCircuitGraph(graph: CircuitGraphSnapshot, options: LayoutOptions = {}): Promise<LayoutResult> {
  const started = performance.now();
  const placements = effectivePlacements(graph);
  const resolved = {
    direction: graph.layout?.direction ?? options.direction ?? "RIGHT",
    nodeWidth: options.nodeWidth ?? 180,
    nodeHeight: options.nodeHeight ?? 100,
    spacing: options.spacing ?? 80,
    gridSize: options.gridSize ?? 20,
    preserveNodeGeometry: options.preserveNodeGeometry ?? "all",
  } as const;
  const nodeGeometry = placeNodes(graph, placements, resolved);
  const boundaryGeometry = placeBoundaries(graph, nodeGeometry, placements, resolved.gridSize);
  const savedRoutes: Record<string, NetRoute> = {};
  const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
  for (const net of graph.nets) {
    const saved = graph.layout?.net_routes?.[net.id];
    if (!saved) continue;
    const ids = net.endpoints.map((endpoint) => endpoint.terminal_id);
    savedRoutes[net.id] = reanchorRouteEndpoints(saved, terminalAnchors(ids, terminals, nodeGeometry, boundaryGeometry, placements));
  }
  const missing = new Set(graph.nets.filter((net) => !savedRoutes[net.id]).map((net) => net.id));
  const automatic = routeOrthogonalNets(routeRequests(graph, missing, nodeGeometry, boundaryGeometry, placements), obstacles(nodeGeometry, boundaryGeometry), {
    gridSize: resolved.gridSize,
    fixedRoutes: savedRoutes,
  });
  return {
    layout: {
      direction: resolved.direction,
      node_geometry: nodeGeometry,
      terminal_placements: placements,
      net_routes: { ...savedRoutes, ...automatic },
    },
    boundary_geometry: boundaryGeometry,
    elapsed_ms: round(performance.now() - started),
  };
}

/** Layout a canonical document through its flattened renderer projection. */
export async function layoutCircuitDocument(
  document: CircuitDocument,
  options: LayoutOptions = {},
): Promise<CircuitDocumentLayoutResult> {
  const result = await layoutCircuitGraph(projectDocument(document, "layout"), options);
  const updated = clone(document);
  updated.layout.direction = result.layout.direction;
  updated.layout.instance_geometry = result.layout.node_geometry;
  updated.layout.terminal_placements = result.layout.terminal_placements;
  updated.layout.net_routes = result.layout.net_routes;
  return { ...result, document: updated };
}
