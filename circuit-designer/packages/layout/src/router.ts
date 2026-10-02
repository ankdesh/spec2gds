/** Orthogonal drawing routes for known nets and placed terminal positions.
 * Routing chooses geometry under obstacle constraints; it cannot invent or
 * repair electrical connectivity. A failed search throws so the caller can
 * report drawing failure without silently changing net endpoints. */
import type { NetRoute, NodeGeometry, Point, RouteVertex } from "@spec2gds/circuit-core";

export interface RouteAnchor {
  terminalId: string;
  point: Point;
  stub: Point;
  source: boolean;
}

export interface RouteRequest {
  netId: string;
  anchors: RouteAnchor[];
}

export interface RouteObstacle {
  id: string;
  geometry: NodeGeometry;
}

export interface OrthogonalRouterOptions {
  gridSize?: number;
  clearance?: number;
  fixedRoutes?: Record<string, NetRoute>;
}

interface SearchBounds { minX: number; minY: number; maxX: number; maxY: number }
type Direction = "H" | "V" | "";
interface SearchState { point: Point; direction: Direction; cost: number; score: number; key: string }

const pointKey = (point: Point) => `${point.x}:${point.y}`;
const edgeKey = (a: Point, b: Point) => [pointKey(a), pointKey(b)].sort().join("|");
const snapDown = (value: number, grid: number) => Math.floor(value / grid) * grid;
const snapUp = (value: number, grid: number) => Math.ceil(value / grid) * grid;

class MinHeap {
  private values: SearchState[] = [];

  get length() { return this.values.length; }

  push(value: SearchState) {
    this.values.push(value);
    let index = this.values.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.values[parent].score <= value.score) break;
      this.values[index] = this.values[parent];
      index = parent;
    }
    this.values[index] = value;
  }

  pop(): SearchState | undefined {
    const first = this.values[0];
    const last = this.values.pop();
    if (!first || !last || this.values.length === 0) return first;
    let index = 0;
    while (true) {
      const left = index * 2 + 1;
      const right = left + 1;
      if (left >= this.values.length) break;
      const child = right < this.values.length && this.values[right].score < this.values[left].score ? right : left;
      if (this.values[child].score >= last.score) break;
      this.values[index] = this.values[child];
      index = child;
    }
    this.values[index] = last;
    return first;
  }
}

function pointsOnSegment(start: Point, end: Point, grid: number): Point[] {
  if (start.x !== end.x && start.y !== end.y) return [];
  const distance = Math.abs(end.x - start.x) + Math.abs(end.y - start.y);
  const steps = Math.max(1, Math.ceil(distance / grid));
  return Array.from({ length: steps + 1 }, (_, index) => ({
    x: start.x + ((end.x - start.x) * index) / steps,
    y: start.y + ((end.y - start.y) * index) / steps,
  }));
}

function occupyRoute(route: NetRoute, points: Set<string>, edges: Set<string>, grid: number) {
  const vertices = new Map(route.vertices.map((vertex) => [vertex.id, vertex.point]));
  for (const segment of route.segments) {
    const start = vertices.get(segment.from_vertex);
    const end = vertices.get(segment.to_vertex);
    if (!start || !end) continue;
    const samples = pointsOnSegment(start, end, grid);
    for (const sample of samples) points.add(pointKey(sample));
    for (let index = 1; index < samples.length; index += 1) edges.add(edgeKey(samples[index - 1], samples[index]));
  }
}

function blockedGridPoints(obstacles: RouteObstacle[], bounds: SearchBounds, grid: number, clearance: number): Set<string> {
  const result = new Set<string>();
  for (const { geometry } of obstacles) {
    const left = geometry.x - clearance;
    const right = geometry.x + geometry.width + clearance;
    const top = geometry.y - clearance;
    const bottom = geometry.y + geometry.height + clearance;
    for (let x = Math.max(bounds.minX, snapDown(left, grid)); x <= Math.min(bounds.maxX, snapUp(right, grid)); x += grid) {
      for (let y = Math.max(bounds.minY, snapDown(top, grid)); y <= Math.min(bounds.maxY, snapUp(bottom, grid)); y += grid) {
        if (x > left && x < right && y > top && y < bottom) result.add(pointKey({ x, y }));
      }
    }
  }
  return result;
}

function searchBounds(requests: RouteRequest[], obstacles: RouteObstacle[], fixedRoutes: Record<string, NetRoute>, grid: number): SearchBounds {
  const points: Point[] = [];
  for (const request of requests) for (const anchor of request.anchors) points.push(anchor.point, anchor.stub);
  for (const obstacle of obstacles) {
    const { x, y, width, height } = obstacle.geometry;
    points.push({ x, y }, { x: x + width, y: y + height });
  }
  for (const route of Object.values(fixedRoutes)) points.push(...route.vertices.map((vertex) => vertex.point));
  const laneCount = Math.min(24, requests.length + Object.keys(fixedRoutes).length + 4);
  const margin = laneCount * grid;
  return {
    minX: snapDown(Math.min(...points.map((point) => point.x), 0) - margin, grid),
    minY: snapDown(Math.min(...points.map((point) => point.y), 0) - margin, grid),
    maxX: snapUp(Math.max(...points.map((point) => point.x), 0) + margin, grid),
    maxY: snapUp(Math.max(...points.map((point) => point.y), 0) + margin, grid),
  };
}

// Sampling large trees bounds scoring cost; this heuristic is a drawing aid,
// not a guarantee that the returned path is the globally shortest route.
function heuristic(point: Point, goals: Point[], grid: number): number {
  let best = Number.POSITIVE_INFINITY;
  const stride = Math.max(1, Math.floor(goals.length / 96));
  for (let index = 0; index < goals.length; index += stride) {
    const goal = goals[index];
    best = Math.min(best, (Math.abs(point.x - goal.x) + Math.abs(point.y - goal.y)) / grid);
  }
  return best;
}

// Search states include the incoming orientation because reaching one point
// horizontally and vertically has different future bend cost. Search attaches
// an anchor to any point in this net's existing tree, rather than to one sink.
function findPath(
  start: Point,
  tree: Set<string>,
  bounds: SearchBounds,
  blocked: Set<string>,
  occupiedPoints: Set<string>,
  occupiedEdges: Set<string>,
  grid: number,
  permitCrossing: boolean,
  congestionPenalty: number,
): Point[] | undefined {
  if (tree.has(pointKey(start))) return [start];
  const goals = [...tree].map((key) => {
    const [x, y] = key.split(":").map(Number);
    return { x, y };
  });
  const queue = new MinHeap();
  const best = new Map<string, number>();
  const previous = new Map<string, string>();
  const states = new Map<string, SearchState>();
  const startKey = `${pointKey(start)}:`;
  const initial = { point: start, direction: "" as Direction, cost: 0, score: heuristic(start, goals, grid), key: startKey };
  queue.push(initial); best.set(startKey, 0); states.set(startKey, initial);
  const moves = [
    { x: grid, y: 0, direction: "H" as Direction },
    { x: -grid, y: 0, direction: "H" as Direction },
    { x: 0, y: grid, direction: "V" as Direction },
    { x: 0, y: -grid, direction: "V" as Direction },
  ];
  while (queue.length) {
    const current = queue.pop()!;
    // Improved states leave older heap entries behind; ignore their stale cost.
    if (current.cost !== best.get(current.key)) continue;
    if (tree.has(pointKey(current.point))) {
      const path: Point[] = [];
      let key: string | undefined = current.key;
      while (key) { path.push(states.get(key)!.point); key = previous.get(key); }
      return path.reverse();
    }
    for (const move of moves) {
      const next = { x: current.point.x + move.x, y: current.point.y + move.y };
      const nextPointKey = pointKey(next);
      if (next.x < bounds.minX || next.x > bounds.maxX || next.y < bounds.minY || next.y > bounds.maxY) continue;
      if (blocked.has(nextPointKey) && nextPointKey !== pointKey(start) && !tree.has(nextPointKey)) continue;
      const congested = occupiedPoints.has(nextPointKey) || occupiedEdges.has(edgeKey(current.point, next));
      if (congested && !permitCrossing && !tree.has(nextPointKey)) continue;
      let cost = current.cost + 1;
      if (current.direction && current.direction !== move.direction) cost += 8;
      if (congested && !tree.has(nextPointKey)) cost += congestionPenalty;
      if (moves.some((near) => occupiedPoints.has(pointKey({ x: next.x + near.x, y: next.y + near.y })))) cost += 2;
      const key = `${nextPointKey}:${move.direction}`;
      if (cost >= (best.get(key) ?? Number.POSITIVE_INFINITY)) continue;
      const state = { point: next, direction: move.direction, cost, score: cost + heuristic(next, goals, grid), key };
      best.set(key, cost); previous.set(key, current.key); states.set(key, state); queue.push(state);
    }
  }
  return undefined;
}

function addGraphEdge(adjacency: Map<string, Set<string>>, a: Point, b: Point) {
  const aKey = pointKey(a);
  const bKey = pointKey(b);
  if (aKey === bKey) return;
  if (!adjacency.has(aKey)) adjacency.set(aKey, new Set());
  if (!adjacency.has(bKey)) adjacency.set(bKey, new Set());
  adjacency.get(aKey)!.add(bKey);
  adjacency.get(bKey)!.add(aKey);
}

function addPath(adjacency: Map<string, Set<string>>, path: Point[]) {
  for (let index = 1; index < path.length; index += 1) addGraphEdge(adjacency, path[index - 1], path[index]);
}

// Collapse straight degree-two grid samples while retaining terminal stubs,
// turns and branches. The stable IDs come from net/terminal identity and points,
// so route compaction changes drawing granularity without changing connectivity.
function compactRoute(request: RouteRequest, adjacency: Map<string, Set<string>>): NetRoute {
  const pointByKey = new Map<string, Point>();
  for (const key of adjacency.keys()) {
    const [x, y] = key.split(":").map(Number);
    pointByKey.set(key, { x, y });
  }
  const endpointByKey = new Map(request.anchors.map((anchor) => [pointKey(anchor.point), anchor.terminalId]));
  const required = new Set(request.anchors.flatMap((anchor) => [pointKey(anchor.point), pointKey(anchor.stub)]));
  const important = new Set<string>();
  for (const [key, neighbours] of adjacency) {
    if (required.has(key) || neighbours.size !== 2) { important.add(key); continue; }
    const [a, b] = [...neighbours].map((neighbour) => pointByKey.get(neighbour)!);
    const point = pointByKey.get(key)!;
    if (!((a.x === point.x && point.x === b.x) || (a.y === point.y && point.y === b.y))) important.add(key);
  }
  const idByKey = new Map<string, string>();
  const vertices: RouteVertex[] = [...important].sort().map((key) => {
    const terminalId = endpointByKey.get(key);
    const degree = adjacency.get(key)?.size ?? 0;
    const id = terminalId ? `endpoint:${terminalId}` : `route:${request.netId}:${key}`;
    idByKey.set(key, id);
    return { id, kind: terminalId ? "endpoint" : degree >= 3 ? "junction" : "bend", point: pointByKey.get(key)!, ...(terminalId ? { terminal_id: terminalId } : {}) } as RouteVertex;
  });
  const segments: NetRoute["segments"] = [];
  const visited = new Set<string>();
  for (const startKey of important) {
    for (const firstKey of adjacency.get(startKey) ?? []) {
      const firstEdge = [startKey, firstKey].sort().join("|");
      if (visited.has(firstEdge)) continue;
      let previous = startKey;
      let current = firstKey;
      visited.add(firstEdge);
      while (!important.has(current)) {
        const next = [...(adjacency.get(current) ?? [])].find((key) => key !== previous);
        if (!next) break;
        visited.add([current, next].sort().join("|"));
        previous = current;
        current = next;
      }
      if (!important.has(current)) continue;
      segments.push({
        id: `segment:${request.netId}:${segments.length}`,
        from_vertex: idByKey.get(startKey)!,
        to_vertex: idByKey.get(current)!,
      });
    }
  }
  return { vertices, segments };
}

function requestSpan(request: RouteRequest): number {
  const xs = request.anchors.map((anchor) => anchor.stub.x);
  const ys = request.anchors.map((anchor) => anchor.stub.y);
  return Math.max(...xs) - Math.min(...xs) + Math.max(...ys) - Math.min(...ys);
}

/**
 * Route all requested nets together on a rectilinear grid. Blocks and fixed
 * block interiors are excluded. Occupied routes carry congestion penalties;
 * small batches try avoiding crossings first, while large batches permit them.
 */
export function routeOrthogonalNets(
  requests: RouteRequest[],
  obstacles: RouteObstacle[],
  options: OrthogonalRouterOptions = {},
): Record<string, NetRoute> {
  const grid = options.gridSize ?? 20;
  const clearance = options.clearance ?? grid / 2;
  const fixedRoutes = options.fixedRoutes ?? {};
  const bounds = searchBounds(requests, obstacles, fixedRoutes, grid);
  const blocked = blockedGridPoints(obstacles, bounds, grid, clearance);
  const occupiedPoints = new Set<string>();
  const occupiedEdges = new Set<string>();
  for (const route of Object.values(fixedRoutes)) occupyRoute(route, occupiedPoints, occupiedEdges, grid);
  const result: Record<string, NetRoute> = {};
  // Route high-fanout/wide nets first with an ID tie-breaker; later nets pay
  // congestion against the accepted routes instead of rerouting earlier nets.
  const ordered = [...requests].sort((a, b) => b.anchors.length - a.anchors.length || requestSpan(b) - requestSpan(a) || a.netId.localeCompare(b.netId));
  const strictCongestion = requests.length <= 64;
  for (const request of ordered) {
    if (request.anchors.length < 2) continue;
    const anchors = [...request.anchors].sort((a, b) => Number(b.source) - Number(a.source) || a.terminalId.localeCompare(b.terminalId));
    const adjacency = new Map<string, Set<string>>();
    const tree = new Set<string>([pointKey(anchors[0].stub)]);
    addGraphEdge(adjacency, anchors[0].point, anchors[0].stub);
    for (const anchor of anchors.slice(1)) {
      addGraphEdge(adjacency, anchor.point, anchor.stub);
      let path = strictCongestion
        ? findPath(anchor.stub, tree, bounds, blocked, occupiedPoints, occupiedEdges, grid, false, 250)
        : undefined;
      // A crossing relaxes drawing congestion, never the obstacle or net model.
      path ??= findPath(anchor.stub, tree, bounds, blocked, occupiedPoints, occupiedEdges, grid, true, strictCongestion ? 250 : 12);
      if (!path) throw new Error(`Unable to find an orthogonal route for net ${request.netId}.`);
      addPath(adjacency, path);
      for (const point of path) tree.add(pointKey(point));
    }
    const route = compactRoute(request, adjacency);
    result[request.netId] = route;
    occupyRoute(route, occupiedPoints, occupiedEdges, grid);
  }
  return result;
}

export function routeIntersectsGeometry(route: NetRoute, geometry: NodeGeometry): boolean {
  const vertices = new Map(route.vertices.map((vertex) => [vertex.id, vertex.point]));
  return route.segments.some((segment) => {
    const start = vertices.get(segment.from_vertex)!;
    const end = vertices.get(segment.to_vertex)!;
    if (start.x === end.x) return start.x > geometry.x && start.x < geometry.x + geometry.width
      && Math.max(Math.min(start.y, end.y), geometry.y) < Math.min(Math.max(start.y, end.y), geometry.y + geometry.height);
    return start.y > geometry.y && start.y < geometry.y + geometry.height
      && Math.max(Math.min(start.x, end.x), geometry.x) < Math.min(Math.max(start.x, end.x), geometry.x + geometry.width);
  });
}

export function routesCrossOrOverlap(first: NetRoute, second: NetRoute): boolean {
  const firstVertices = new Map(first.vertices.map((vertex) => [vertex.id, vertex.point]));
  const secondVertices = new Map(second.vertices.map((vertex) => [vertex.id, vertex.point]));
  for (const a of first.segments) for (const b of second.segments) {
    const a1 = firstVertices.get(a.from_vertex)!; const a2 = firstVertices.get(a.to_vertex)!;
    const b1 = secondVertices.get(b.from_vertex)!; const b2 = secondVertices.get(b.to_vertex)!;
    if (a1.y === a2.y && b1.y === b2.y && a1.y === b1.y
      && Math.max(Math.min(a1.x, a2.x), Math.min(b1.x, b2.x)) <= Math.min(Math.max(a1.x, a2.x), Math.max(b1.x, b2.x))) return true;
    if (a1.x === a2.x && b1.x === b2.x && a1.x === b1.x
      && Math.max(Math.min(a1.y, a2.y), Math.min(b1.y, b2.y)) <= Math.min(Math.max(a1.y, a2.y), Math.max(b1.y, b2.y))) return true;
    const horizontal = a1.y === a2.y ? [a1, a2, b1, b2] : b1.y === b2.y ? [b1, b2, a1, a2] : undefined;
    if (horizontal) {
      const [h1, h2, v1, v2] = horizontal;
      if (v1.x >= Math.min(h1.x, h2.x) && v1.x <= Math.max(h1.x, h2.x)
        && h1.y >= Math.min(v1.y, v2.y) && h1.y <= Math.max(v1.y, v2.y)) return true;
    }
  }
  return false;
}
