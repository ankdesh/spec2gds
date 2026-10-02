/** Geometry-only route editing over an already defined electrical net.
 * Bends, segments and junctions describe a drawing, not new connectivity.
 * Preserve terminal identity when normalizing a route so visual edits cannot
 * silently retarget its logical endpoint. */
import type { NetRoute, Point, RouteSegment, RouteVertex } from "./types.generated";

const clone = <T>(value: T): T => structuredClone(value);
const pointKey = (point: Point) => `${point.x}:${point.y}`;

export type RouteOrientation = "horizontal" | "vertical";

export function snapRouteCoordinate(value: number, gridSize = 20): number {
  return Math.round(value / gridSize) * gridSize;
}

export function routeSegmentId(segment: RouteSegment, index = 0): string {
  return segment.id ?? `segment:${[segment.from_vertex, segment.to_vertex].sort().join(":")}:${index}`;
}

export function routeOrientation(route: NetRoute, segmentId: string): RouteOrientation | undefined {
  const normalized = ensureRouteIds(route);
  const segment = normalized.segments.find((item) => item.id === segmentId);
  if (!segment) return undefined;
  const vertices = new Map(normalized.vertices.map((vertex) => [vertex.id, vertex]));
  const start = vertices.get(segment.from_vertex)?.point;
  const end = vertices.get(segment.to_vertex)?.point;
  if (!start || !end) return undefined;
  if (start.y === end.y && start.x !== end.x) return "horizontal";
  if (start.x === end.x && start.y !== end.y) return "vertical";
  return undefined;
}

/** Ensure every route element has stable renderer/programmatic identity. */
export function ensureRouteIds(route: NetRoute): NetRoute {
  const result = clone(route);
  const used = new Set<string>();
  result.segments = result.segments.map((segment, index) => {
    const base = routeSegmentId(segment, index);
    let id = base;
    let suffix = 1;
    while (used.has(id)) id = `${base}:${suffix++}`;
    used.add(id);
    return { ...segment, id };
  });
  return classifyRouteVertices(result);
}

function uniqueId(route: NetRoute, prefix: string): string {
  const used = new Set(route.vertices.map((vertex) => vertex.id));
  let index = 1;
  let id = `${prefix}:${index}`;
  while (used.has(id)) id = `${prefix}:${++index}`;
  return id;
}

function uniqueSegmentId(route: NetRoute, prefix: string): string {
  const used = new Set(route.segments.map((segment, index) => routeSegmentId(segment, index)));
  let index = 1;
  let id = `${prefix}:${index}`;
  while (used.has(id)) id = `${prefix}:${++index}`;
  return id;
}

function verticesById(route: NetRoute): Map<string, RouteVertex> {
  return new Map(route.vertices.map((vertex) => [vertex.id, vertex]));
}

function incident(route: NetRoute, vertexId: string): RouteSegment[] {
  return route.segments.filter((segment) => segment.from_vertex === vertexId || segment.to_vertex === vertexId);
}

function otherEnd(segment: RouteSegment, vertexId: string): string {
  return segment.from_vertex === vertexId ? segment.to_vertex : segment.from_vertex;
}

function classifyRouteVertices(route: NetRoute): NetRoute {
  const degrees = new Map(route.vertices.map((vertex) => [vertex.id, 0]));
  for (const segment of route.segments) {
    degrees.set(segment.from_vertex, (degrees.get(segment.from_vertex) ?? 0) + 1);
    degrees.set(segment.to_vertex, (degrees.get(segment.to_vertex) ?? 0) + 1);
  }
  return {
    ...route,
    vertices: route.vertices.map((vertex) => vertex.kind === "endpoint" ? vertex : {
      ...vertex,
      kind: (degrees.get(vertex.id) ?? 0) >= 3 ? "junction" : "bend",
    }),
  };
}

function orthogonal(start: Point, end: Point): boolean {
  return (start.x === end.x || start.y === end.y) && pointKey(start) !== pointKey(end);
}

function repairMovedVertices(
  route: NetRoute,
  movedVertexIds: Set<string>,
  protectedSegmentId?: string,
): NetRoute | undefined {
  const result = ensureRouteIds(route);
  let vertices = verticesById(result);
  for (const segment of [...result.segments]) {
    if (segment.id === protectedSegmentId) continue;
    const start = vertices.get(segment.from_vertex)!;
    const end = vertices.get(segment.to_vertex)!;
    if (orthogonal(start.point, end.point)) continue;
    if (segment.locked) return undefined;
    const movedStart = movedVertexIds.has(start.id);
    const movedEnd = movedVertexIds.has(end.id);
    if (!movedStart && !movedEnd) return undefined;
    const moved = movedStart ? start : end;
    const fixed = movedStart ? end : start;
    const bendPoint = { x: moved.point.x, y: fixed.point.y };
    const bendId = uniqueId(result, "manual-bend");
    result.vertices.push({ id: bendId, kind: "bend", point: bendPoint });
    result.segments = result.segments.filter((item) => item.id !== segment.id);
    const first = movedStart ? [moved.id, bendId] : [fixed.id, bendId];
    const second = movedStart ? [bendId, fixed.id] : [bendId, moved.id];
    result.segments.push(
      { id: segment.id, from_vertex: first[0], to_vertex: first[1] },
      { id: uniqueSegmentId(result, "manual-segment"), from_vertex: second[0], to_vertex: second[1] },
    );
    vertices = verticesById(result);
  }
  return simplifyRoute(result, movedVertexIds);
}

/** Drag one orthogonal segment along its perpendicular axis. */
export function moveRouteSegment(route: NetRoute, segmentId: string, coordinate: number, gridSize = 20): NetRoute {
  const result = ensureRouteIds(route);
  const segment = result.segments.find((item) => item.id === segmentId);
  if (!segment || segment.locked) return result;
  const byId = verticesById(result);
  const start = byId.get(segment.from_vertex)!;
  const end = byId.get(segment.to_vertex)!;
  if (start.locked || end.locked || start.kind === "endpoint" || end.kind === "endpoint") return result;
  const orientation = routeOrientation(result, segmentId);
  if (!orientation) return result;
  const snapped = snapRouteCoordinate(coordinate, gridSize);
  if (orientation === "horizontal") { start.point.y = snapped; end.point.y = snapped; }
  else { start.point.x = snapped; end.point.x = snapped; }
  return repairMovedVertices(result, new Set([start.id, end.id]), segmentId) ?? ensureRouteIds(route);
}

/** Move a bend or electrical junction and repair all adjacent branches. */
export function moveRouteVertex(route: NetRoute, vertexId: string, point: Point, gridSize = 20): NetRoute {
  const result = ensureRouteIds(route);
  const vertex = result.vertices.find((item) => item.id === vertexId);
  if (!vertex || vertex.kind === "endpoint" || vertex.locked || incident(result, vertexId).some((segment) => segment.locked)) return result;
  vertex.point = { x: snapRouteCoordinate(point.x, gridSize), y: snapRouteCoordinate(point.y, gridSize) };
  return repairMovedVertices(result, new Set([vertexId])) ?? ensureRouteIds(route);
}

/** Split a segment at a grid-aligned point, creating a draggable degree-two bend. */
export function insertRouteBend(route: NetRoute, segmentId: string, point: Point, gridSize = 20): NetRoute {
  const result = ensureRouteIds(route);
  const segment = result.segments.find((item) => item.id === segmentId);
  if (!segment || segment.locked) return result;
  const byId = verticesById(result);
  const start = byId.get(segment.from_vertex)!;
  const end = byId.get(segment.to_vertex)!;
  const orientation = routeOrientation(result, segmentId);
  if (!orientation) return result;
  const bendPoint = orientation === "horizontal"
    ? { x: snapRouteCoordinate(point.x, gridSize), y: start.point.y }
    : { x: start.point.x, y: snapRouteCoordinate(point.y, gridSize) };
  if (pointKey(bendPoint) === pointKey(start.point) || pointKey(bendPoint) === pointKey(end.point)) return result;
  const bendId = uniqueId(result, "manual-bend");
  result.vertices.push({ id: bendId, kind: "bend", point: bendPoint });
  result.segments = result.segments.filter((item) => item.id !== segmentId);
  result.segments.push(
    { id: segmentId, from_vertex: start.id, to_vertex: bendId },
    { id: uniqueSegmentId(result, "manual-segment"), from_vertex: bendId, to_vertex: end.id },
  );
  return classifyRouteVertices(result);
}

/** Remove a redundant unlocked bend when its neighbours can be joined orthogonally. */
export function removeRouteBend(route: NetRoute, vertexId: string): NetRoute {
  const result = ensureRouteIds(route);
  const vertex = result.vertices.find((item) => item.id === vertexId);
  const attached = incident(result, vertexId);
  if (!vertex || vertex.kind !== "bend" || vertex.locked || attached.length !== 2 || attached.some((segment) => segment.locked)) return result;
  const byId = verticesById(result);
  const firstId = otherEnd(attached[0], vertexId);
  const secondId = otherEnd(attached[1], vertexId);
  if (!orthogonal(byId.get(firstId)!.point, byId.get(secondId)!.point)) return result;
  result.vertices = result.vertices.filter((item) => item.id !== vertexId);
  result.segments = result.segments.filter((item) => !attached.some((segment) => segment.id === item.id));
  result.segments.push({ id: attached[0].id, from_vertex: firstId, to_vertex: secondId });
  return classifyRouteVertices(result);
}

export function toggleRouteSegmentLock(route: NetRoute, segmentId: string): NetRoute {
  const result = ensureRouteIds(route);
  const segment = result.segments.find((item) => item.id === segmentId);
  if (segment) segment.locked = !segment.locked;
  return result;
}

export function toggleRouteVertexLock(route: NetRoute, vertexId: string): NetRoute {
  const result = ensureRouteIds(route);
  const vertex = result.vertices.find((item) => item.id === vertexId);
  if (vertex && vertex.kind !== "endpoint") vertex.locked = !vertex.locked;
  return result;
}

/** Remove unlocked zero-length and redundant collinear degree-two vertices. */
export function simplifyRoute(route: NetRoute, preserve = new Set<string>()): NetRoute {
  const result = ensureRouteIds(route);
  let changed = true;
  while (changed) {
    changed = false;
    const byId = verticesById(result);
    for (const vertex of [...result.vertices]) {
      if (vertex.kind === "endpoint" || vertex.locked || preserve.has(vertex.id)) continue;
      const attached = incident(result, vertex.id);
      if (attached.length !== 2 || attached.some((segment) => segment.locked)) continue;
      const firstId = otherEnd(attached[0], vertex.id);
      const secondId = otherEnd(attached[1], vertex.id);
      const first = byId.get(firstId)!;
      const second = byId.get(secondId)!;
      const collinear = (first.point.x === vertex.point.x && vertex.point.x === second.point.x)
        || (first.point.y === vertex.point.y && vertex.point.y === second.point.y);
      if (!collinear || pointKey(first.point) === pointKey(second.point)) continue;
      result.vertices = result.vertices.filter((item) => item.id !== vertex.id);
      result.segments = result.segments.filter((item) => !attached.some((segment) => segment.id === item.id));
      result.segments.push({ id: attached[0].id, from_vertex: firstId, to_vertex: secondId });
      changed = true;
      break;
    }
  }
  return classifyRouteVertices(result);
}

export interface EndpointAnchor {
  point: Point;
  stub: Point;
}

/**
 * Reanchor selected semantic endpoints while retaining every unaffected trunk,
 * junction, stable id, and locked corridor.
 */
export function reanchorRouteEndpoints(route: NetRoute, anchors: Record<string, EndpointAnchor>): NetRoute {
  let result = ensureRouteIds(route);
  for (const endpoint of result.vertices.filter((vertex) => vertex.kind === "endpoint" && vertex.terminal_id && anchors[vertex.terminal_id])) {
    const anchor = anchors[endpoint.terminal_id!];
    if (pointKey(endpoint.point) === pointKey(anchor.point)) continue;
    const attached = incident(result, endpoint.id);
    if (attached.length !== 1) continue;
    const segment = attached[0];
    const neighbourId = otherEnd(segment, endpoint.id);
    const neighbour = result.vertices.find((vertex) => vertex.id === neighbourId)!;
    if (neighbour.kind === "endpoint" && !segment.locked) {
      endpoint.point = { ...anchor.point };
      const stubId = uniqueId(result, "endpoint-stub");
      result.vertices.push({ id: stubId, kind: "bend", point: { ...anchor.stub } });
      if (segment.from_vertex === endpoint.id) segment.from_vertex = stubId;
      else segment.to_vertex = stubId;
      result.segments.push({ id: uniqueSegmentId(result, "endpoint-segment"), from_vertex: endpoint.id, to_vertex: stubId });
      result = repairMovedVertices(result, new Set([stubId]), undefined) ?? result;
    } else if (segment.locked || neighbour.locked) {
      const oldPoint = { ...endpoint.point };
      const fixedId = uniqueId(result, "locked-anchor");
      result.vertices.push({ id: fixedId, kind: "bend", point: oldPoint, locked: true });
      if (segment.from_vertex === endpoint.id) segment.from_vertex = fixedId;
      else segment.to_vertex = fixedId;
      endpoint.point = { ...anchor.point };
      const stubId = uniqueId(result, "endpoint-stub");
      result.vertices.push({ id: stubId, kind: "bend", point: { ...anchor.stub } });
      result.segments.push({ id: uniqueSegmentId(result, "endpoint-segment"), from_vertex: endpoint.id, to_vertex: stubId });
      const fixed = result.vertices.find((vertex) => vertex.id === fixedId)!;
      if (orthogonal(anchor.stub, fixed.point)) {
        result.segments.push({ id: uniqueSegmentId(result, "endpoint-segment"), from_vertex: stubId, to_vertex: fixedId });
      } else {
        const bendId = uniqueId(result, "endpoint-bend");
        result.vertices.push({ id: bendId, kind: "bend", point: { x: anchor.stub.x, y: fixed.point.y } });
        result.segments.push(
          { id: uniqueSegmentId(result, "endpoint-segment"), from_vertex: stubId, to_vertex: bendId },
          { id: uniqueSegmentId(result, "endpoint-segment"), from_vertex: bendId, to_vertex: fixedId },
        );
      }
    } else {
      endpoint.point = { ...anchor.point };
      neighbour.point = { ...anchor.stub };
      result = repairMovedVertices(result, new Set([endpoint.id, neighbour.id]), segment.id ?? undefined) ?? result;
    }
  }
  return simplifyRoute(result);
}

export function setAllRouteLocks(route: NetRoute, locked: boolean): NetRoute {
  const result = ensureRouteIds(route);
  result.segments = result.segments.map((segment) => ({ ...segment, locked }));
  result.vertices = result.vertices.map((vertex) => vertex.kind === "endpoint" ? vertex : { ...vertex, locked });
  return result;
}

function branchToFirstJunction(route: NetRoute, terminalId: string): string[] {
  const endpoint = route.vertices.find((vertex) => vertex.kind === "endpoint" && vertex.terminal_id === terminalId);
  if (!endpoint) return [];
  const path = [endpoint.id];
  let previous: string | undefined;
  let current = endpoint.id;
  while (true) {
    const attached = incident(route, current);
    if (current !== endpoint.id && (attached.length !== 2 || route.vertices.find((vertex) => vertex.id === current)?.locked)) break;
    const nextSegment = attached.find((segment) => otherEnd(segment, current) !== previous);
    if (!nextSegment || nextSegment.locked) break;
    const next = otherEnd(nextSegment, current);
    path.push(next); previous = current; current = next;
    if (path.length > route.vertices.length) return [];
  }
  return path;
}

/** Reset one endpoint branch while preserving the rest of a fanout route tree. */
export function resetRouteBranch(route: NetRoute, automaticRoute: NetRoute, terminalId: string): NetRoute {
  const current = ensureRouteIds(route);
  const automatic = ensureRouteIds(automaticRoute);
  const path = branchToFirstJunction(current, terminalId);
  if (path.length < 2) return current;
  const anchorId = path.at(-1)!;
  const anchor = current.vertices.find((vertex) => vertex.id === anchorId)!;
  if (anchor.kind !== "junction" && !anchor.locked) return automatic;
  const removable = new Set(path.slice(0, -1));
  const endpoint = current.vertices.find((vertex) => vertex.id === path[0])!;
  const automaticPath = branchToFirstJunction(automatic, terminalId);
  const autoEndpoint = automatic.vertices.find((vertex) => vertex.id === automaticPath[0]);
  const autoStub = automatic.vertices.find((vertex) => vertex.id === automaticPath[1]);
  if (!autoEndpoint || !autoStub) return current;
  current.vertices = current.vertices.filter((vertex) => !removable.has(vertex.id));
  current.segments = current.segments.filter((segment) => !removable.has(segment.from_vertex) && !removable.has(segment.to_vertex));
  current.vertices.push({ ...autoEndpoint, id: endpoint.id });
  const stubId = uniqueId(current, "reset-stub");
  current.vertices.push({ ...autoStub, id: stubId, kind: "bend", terminal_id: undefined });
  current.segments.push({ id: uniqueSegmentId(current, "reset-segment"), from_vertex: endpoint.id, to_vertex: stubId });
  if (orthogonal(autoStub.point, anchor.point)) {
    current.segments.push({ id: uniqueSegmentId(current, "reset-segment"), from_vertex: stubId, to_vertex: anchorId });
  } else {
    const bendId = uniqueId(current, "reset-bend");
    current.vertices.push({ id: bendId, kind: "bend", point: { x: autoStub.point.x, y: anchor.point.y } });
    current.segments.push(
      { id: uniqueSegmentId(current, "reset-segment"), from_vertex: stubId, to_vertex: bendId },
      { id: uniqueSegmentId(current, "reset-segment"), from_vertex: bendId, to_vertex: anchorId },
    );
  }
  return simplifyRoute(current, new Set([anchorId]));
}
