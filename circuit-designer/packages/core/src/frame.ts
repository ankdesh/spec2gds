/** Derived drawing geometry. A frame is never part of circuit connectivity. */
import type { CircuitGraphView, CircuitTerminalView } from "./model";
import type { NetRoute, NodeGeometry, Point, TerminalPlacement } from "./types.generated";
import { reanchorRouteEndpoints } from "./route-editor";

export const CIRCUIT_FRAME_HEADER_HEIGHT = 60;

export interface CircuitContainerPresentation {
  label: string;
  description: string;
}

export function oppositeTerminalSide(side: TerminalPlacement["side"]): TerminalPlacement["side"] {
  return ({ NORTH: "SOUTH", SOUTH: "NORTH", EAST: "WEST", WEST: "EAST" } as const)[side];
}

/** Boundary placements describe the inward connection direction, as before. */
export function circuitTerminalSide(terminal: CircuitTerminalView): TerminalPlacement["side"] {
  if (!terminal.node_id) {
    if (terminal.role === "initiator" || terminal.direction === "in") return "EAST";
    if (terminal.role === "target" || terminal.direction === "out") return "WEST";
    return "NORTH";
  }
  if (terminal.role === "initiator" || terminal.direction === "out") return "EAST";
  if (terminal.role === "target" || terminal.direction === "in") return "WEST";
  return "SOUTH";
}

export function effectiveCircuitTerminalPlacements(graph: CircuitGraphView): Record<string, TerminalPlacement> {
  const result: Record<string, TerminalPlacement> = {};
  const nextOrder = new Map<string, number>();
  for (const terminal of [...graph.terminals].sort((a, b) => a.id.localeCompare(b.id))) {
    const saved = graph.layout.terminal_placements[terminal.id];
    const side = saved?.side ?? circuitTerminalSide(terminal);
    const key = `${terminal.node_id ?? "boundary"}:${side}`;
    const order = saved?.order ?? nextOrder.get(key) ?? 0;
    result[terminal.id] = saved ?? { side, order, locked: false };
    nextOrder.set(key, Math.max(nextOrder.get(key) ?? 0, order + 1));
  }
  return result;
}

/** All boundary boxes stay invisible; their inward handles sit on the frame. */
export function circuitFrameGeometry(
  graph: CircuitGraphView,
  nodes: Record<string, NodeGeometry>,
  placementOverrides: Record<string, TerminalPlacement> = {},
  routes: Record<string, NetRoute> = graph.layout.net_routes,
  grid = 20,
  expansion = 0,
): { container_geometry: NodeGeometry; boundary_geometry: Record<string, NodeGeometry> } {
  // The canvas can receive a new graph before its asynchronous layout returns.
  const placements = { ...effectiveCircuitTerminalPlacements(graph), ...placementOverrides };
  const boxes = Object.values(nodes);
  const grouped: Record<TerminalPlacement["side"], CircuitTerminalView[]> = { NORTH: [], EAST: [], SOUTH: [], WEST: [] };
  for (const terminal of graph.terminals.filter(item => !item.node_id)) grouped[placements[terminal.id].side].push(terminal);
  for (const items of Object.values(grouped)) items.sort((a, b) => placements[a.id].order - placements[b.id].order || a.id.localeCompare(b.id));
  const down = (n: number) => Math.floor(n / grid) * grid;
  const up = (n: number) => Math.ceil(n / grid) * grid;
  // Endpoints follow the frame. Only route interiors can enlarge it, otherwise
  // each saved layout would move its frame farther from its own endpoints.
  const interiors = Object.values(routes).flatMap(route => route.vertices.filter(vertex => vertex.kind !== "endpoint").map(vertex => vertex.point));
  const left = down(Math.min(...boxes.map(box => box.x - 220), ...interiors.map(point => point.x - grid), boxes.length ? Infinity : -140) - expansion);
  const top = down(Math.min(...boxes.map(box => box.y - 140), ...interiors.map(point => point.y - CIRCUIT_FRAME_HEADER_HEIGHT - grid), boxes.length ? Infinity : -60) - expansion);
  const right = up(Math.max(left + 640, ...boxes.map(box => box.x + box.width + 220), ...interiors.map(point => point.x + grid), left + 120 + Math.max(grouped.NORTH.length, grouped.SOUTH.length) * 200) + expansion);
  const bottom = up(Math.max(top + 360, ...boxes.map(box => box.y + box.height + 80), ...interiors.map(point => point.y + grid), top + 140 + Math.max(grouped.EAST.length, grouped.WEST.length) * 40) + expansion);
  const container_geometry = { x: left, y: top, width: right - left, height: bottom - top, pinned: false };
  const boundary_geometry: Record<string, NodeGeometry> = {};
  for (const [side, items] of Object.entries(grouped) as Array<[TerminalPlacement["side"], CircuitTerminalView[]]>) {
    items.forEach((terminal, index) => {
      const point: Point = side === "EAST" ? { x: left, y: top + 100 + index * 40 }
        : side === "WEST" ? { x: right, y: top + 100 + index * 40 }
          : side === "NORTH" ? { x: left + 120 + index * 200, y: bottom }
            : { x: left + 120 + index * 200, y: top + CIRCUIT_FRAME_HEADER_HEIGHT };
      boundary_geometry[terminal.id] = {
        x: point.x - (side === "EAST" ? 40 : side === "WEST" ? 0 : 20),
        y: point.y - (side === "SOUTH" ? 40 : side === "NORTH" ? 0 : 20),
        width: 40, height: 40, pinned: false,
      };
    });
  }
  return { container_geometry, boundary_geometry };
}

export function circuitFrameRoutingBounds(frame: NodeGeometry) {
  return { minX: frame.x, minY: frame.y + CIRCUIT_FRAME_HEADER_HEIGHT, maxX: frame.x + frame.width, maxY: frame.y + frame.height };
}

/** Shared handle position for canvas layout and image rendering. */
export function circuitTerminalPoint(geometry: NodeGeometry, placement: TerminalPlacement): Point {
  const inset = 60 + placement.order * 20;
  if (placement.side === "EAST") return { x: geometry.x + geometry.width, y: geometry.y + Math.min(inset, geometry.height - 20) };
  if (placement.side === "WEST") return { x: geometry.x, y: geometry.y + Math.min(inset, geometry.height - 20) };
  if (placement.side === "NORTH") return { x: geometry.x + Math.min(inset, geometry.width - 20), y: geometry.y };
  return { x: geometry.x + Math.min(inset, geometry.width - 20), y: geometry.y + geometry.height };
}

export function circuitTerminalStubPoint(point: Point, placement: TerminalPlacement, distance = 20): Point {
  if (placement.side === "EAST") return { x: point.x + distance, y: point.y };
  if (placement.side === "WEST") return { x: point.x - distance, y: point.y };
  if (placement.side === "NORTH") return { x: point.x, y: point.y - distance };
  return { x: point.x, y: point.y + distance };
}

/** Old saved endpoints must follow the same new anchors as the live canvas. */
export function reanchorCircuitFrameRoutes(
  graph: CircuitGraphView,
  nodes: Record<string, NodeGeometry>,
  boundaries: Record<string, NodeGeometry>,
  placements = effectiveCircuitTerminalPlacements(graph),
): Record<string, NetRoute> {
  const anchors = Object.fromEntries(graph.terminals.flatMap(terminal => {
    const box = terminal.node_id ? nodes[terminal.node_id] : boundaries[terminal.id] ?? boundaries[terminal.id.slice(9)];
    const placement = placements[terminal.id];
    if (!box || !placement) return [];
    const point = circuitTerminalPoint(box, placement);
    return [[terminal.id, { point, stub: circuitTerminalStubPoint(point, placement) }]];
  }));
  return Object.fromEntries(Object.entries(graph.layout.net_routes).map(([id, route]) => [id, reanchorRouteEndpoints(route, anchors)]));
}
