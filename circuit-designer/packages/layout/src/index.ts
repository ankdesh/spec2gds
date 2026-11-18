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
import { clone, effectiveCircuitTiming, projectDocument, reanchorRouteEndpoints, simplifyRoute, sortedCycleEdges, stageForHorizontalSpan, type EndpointAnchor, circuitTerminalSide, effectiveCircuitTerminalPlacements, circuitFrameGeometry, circuitTerminalPoint, circuitTerminalStubPoint, circuitFrameRoutingBounds } from "@spec2gds/circuit-core";
import { routeOrthogonalNets, routeIntersectsGeometry, type RouteObstacle, type RouteRequest } from "./router";

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
  container_geometry: NodeGeometry;
  elapsed_ms: number;
}

export interface CircuitDocumentLayoutResult extends LayoutResult {
  document: CircuitDocument;
}

const round = (value: number) => Math.round(value * 100) / 100;
const snap = (value: number, grid: number) => Math.round(value / grid) * grid;

export const terminalSide = circuitTerminalSide;

export function terminalOffset(placement: TerminalPlacement): number {
  return 60 + placement.order * 20;
}

export function terminalPoint(
  _terminal: CircuitTerminal,
  geometry: NodeGeometry,
  placement: TerminalPlacement,
): Point {
  return circuitTerminalPoint(geometry, placement);
}

export const terminalStubPoint = circuitTerminalStubPoint;

const effectivePlacements = effectiveCircuitTerminalPlacements;

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
    // Boundary-driven nets (including shared controls) have consumers here,
    // not an instance driver. Do not invent dependencies between those sinks.
    for (const source of sources) for (const target of owners) {
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

function lockedRouteNodeIds(graph: CircuitGraphSnapshot): Set<string> {
  const nodeByTerminal = new Map(graph.terminals.map(terminal => [terminal.id, terminal.node_id]));
  return new Set(graph.nets.filter(net => hasLocks(graph.layout.net_routes[net.id])).flatMap(net =>
    net.endpoints.flatMap(endpoint => nodeByTerminal.get(endpoint.terminal_id) ? [nodeByTerminal.get(endpoint.terminal_id)!] : [])));
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
  const routeLockedNodes = lockedRouteNodeIds(graph);
  const preservedIds = new Set<string>();
  for (const [nodeId, geometry] of Object.entries(graph.layout?.node_geometry ?? {})) {
    if (!routeLockedNodes.has(nodeId) && (preserve === "none" || (preserve === "pinned" && !geometry.pinned))) continue;
    preservedIds.add(nodeId);
    result[nodeId] = {
      ...geometry,
      x: snap(geometry.x, options.gridSize),
      y: snap(geometry.y, options.gridSize),
    };
  }
  // New instances must not cover saved instances after those positions are
  // restored. Keep every saved coordinate and move only automatic placements.
  const occupied = [...preservedIds].map(id => result[id]);
  for (const [id, geometry] of Object.entries(result)) {
    if (preservedIds.has(id)) continue;
    let collisions: NodeGeometry[];
    do {
      collisions = occupied.filter(box => geometry.x < box.x + box.width && geometry.x + geometry.width > box.x
        && geometry.y < box.y + box.height && geometry.y + geometry.height > box.y);
      if (collisions.length) {
        const field = options.direction === "RIGHT" ? "y" : "x";
        const dimension = options.direction === "RIGHT" ? "height" : "width";
        geometry[field] = Math.ceil((Math.max(...collisions.map(box => box[field] + box[dimension])) + options.spacing) / options.gridSize) * options.gridSize;
      }
    } while (collisions.length);
    occupied.push(geometry);
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
      bounds: circuitFrameRoutingBounds(circuitFrameGeometry(graph, nodeGeometry, placements, { ...layout.net_routes, ...fixedRoutes }).container_geometry),
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
  // A failed attempt can enlarge drawing space, but never change connectivity.
  let lastError: unknown;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const frame = circuitFrameGeometry(graph, nodeGeometry, placements, graph.layout.net_routes, resolved.gridSize, attempt * 80);
    const boundaryGeometry = frame.boundary_geometry;
    const savedRoutes: Record<string, NetRoute> = {};
    const terminals = new Map(graph.terminals.map((terminal) => [terminal.id, terminal]));
    try {
      for (const net of graph.nets) {
        const saved = graph.layout?.net_routes?.[net.id];
        if (!saved) continue;
        if (resolved.preserveNodeGeometry !== "all" && !hasLocks(saved)) continue;
        const ids = net.endpoints.map((endpoint) => endpoint.terminal_id);
        const anchored = reanchorRouteEndpoints(saved, terminalAnchors(ids, terminals, nodeGeometry, boundaryGeometry, placements));
        if (Object.values(nodeGeometry).some(box => routeIntersectsGeometry(anchored, box))) {
          if (hasLocks(saved)) throw new Error(`Locked route ${net.id} intersects an instance. Unlock or move its route before continuing.`);
          continue;
        }
        savedRoutes[net.id] = anchored;
      }
      const missing = new Set(graph.nets.filter((net) => !savedRoutes[net.id]).map((net) => net.id));
      const automatic = routeOrthogonalNets(routeRequests(graph, missing, nodeGeometry, boundaryGeometry, placements), obstacles(nodeGeometry, boundaryGeometry), {
        gridSize: resolved.gridSize,
        fixedRoutes: savedRoutes,
        bounds: circuitFrameRoutingBounds(frame.container_geometry),
      });
      return {
        layout: {
          direction: resolved.direction,
          node_geometry: nodeGeometry,
          terminal_placements: placements,
          net_routes: { ...savedRoutes, ...automatic },
        },
        ...frame,
        elapsed_ms: round(performance.now() - started),
      };
    } catch (error) { lastError = error; }
  }
  throw lastError;
}

/** Layout a canonical document through its flattened renderer projection. */
export async function layoutCircuitDocument(
  document: CircuitDocument,
  options: LayoutOptions = {},
): Promise<CircuitDocumentLayoutResult> {
  let result = await layoutCircuitGraph(projectDocument(document, "layout"), options);
  const updated = clone(document);
  if (document.timing?.cycle_edges.length) {
    const routeLockedNodes = lockedRouteNodeIds(projectDocument(document));
    const timing = effectiveCircuitTiming(document);
    const edges = sortedCycleEdges(timing);
    const byStage = new Map<number, string[]>();
    for (const instance of document.design.instances) {
      const original = document.layout.instance_geometry[instance.id];
      const stage = original ? stageForHorizontalSpan(timing, original.x, original.x + original.width) : undefined;
      const resolvedStage = stage ?? Math.min(edges.length, Math.max(0, edges.filter((edge) => edge.x <= (result.layout.node_geometry[instance.id]?.x ?? 0)).length));
      byStage.set(resolvedStage, [...(byStage.get(resolvedStage) ?? []), instance.id]);
    }
    const movedEdges = edges.map((edge) => ({ ...edge }));
    const padding = Math.max(40, (options.gridSize ?? document.layout.grid_size) * 2);
    for (let stage = 1; stage < movedEdges.length; stage += 1) {
      const ids = byStage.get(stage) ?? [];
      if (!ids.length) continue;
      const values = ids.map((id) => result.layout.node_geometry[id]).filter(Boolean);
      const minGenerated = Math.min(...values.map((value) => value.x));
      const required = Math.max(...values.map((value) => value.x + value.width - minGenerated)) + padding * 2;
      const available = movedEdges[stage].x - movedEdges[stage - 1].x;
      if (required <= available) continue;
      if (movedEdges.slice(stage).some((edge) => edge.locked)) {
        throw new Error(`Stage ${stage} needs ${Math.ceil(required - available)} more pixels, but a following cycle edge is locked.`);
      }
      const delta = Math.ceil((required - available) / (options.gridSize ?? document.layout.grid_size)) * (options.gridSize ?? document.layout.grid_size);
      for (let index = stage; index < movedEdges.length; index += 1) movedEdges[index].x += delta;
    }
    for (const [stage, ids] of byStage) {
      if (!ids.length) continue;
      const values = ids.map((id) => result.layout.node_geometry[id]).filter(Boolean);
      const minGenerated = Math.min(...values.map((value) => value.x));
      const left = stage === 0
        ? movedEdges[0].x - (Math.max(...values.map((value) => value.x + value.width - minGenerated)) + padding)
        : movedEdges[stage - 1]?.x + padding;
      for (const id of ids) {
        const original = document.layout.instance_geometry[id];
        const preserve = options.preserveNodeGeometry ?? "all";
        if (original && (routeLockedNodes.has(id) || preserve === "all" || (preserve === "pinned" && original.pinned))) continue;
        result.layout.node_geometry[id].x = snap(left + (result.layout.node_geometry[id].x - minGenerated), options.gridSize ?? document.layout.grid_size);
      }
    }
    updated.timing = { ...timing, cycle_edges: movedEdges };
    const rerouteDocument = clone(updated);
    rerouteDocument.layout.instance_geometry = result.layout.node_geometry;
    rerouteDocument.layout.terminal_placements = result.layout.terminal_placements;
    rerouteDocument.layout.net_routes = Object.fromEntries(
      Object.entries(result.layout.net_routes ?? {}).filter(([, route]) => hasLocks(route)),
    );
    result = await layoutCircuitGraph(projectDocument(rerouteDocument, "layout"), { ...options, preserveNodeGeometry: "all" });
  }
  updated.layout.direction = result.layout.direction;
  updated.layout.instance_geometry = result.layout.node_geometry;
  updated.layout.terminal_placements = result.layout.terminal_placements;
  updated.layout.net_routes = result.layout.net_routes;
  return { ...result, document: updated };
}
