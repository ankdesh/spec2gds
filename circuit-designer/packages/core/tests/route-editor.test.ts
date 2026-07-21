import { describe, expect, test } from "vitest";
import {
  ensureRouteIds,
  insertRouteBend,
  moveRouteSegment,
  moveRouteVertex,
  reanchorRouteEndpoints,
  removeRouteBend,
  setAllRouteLocks,
  simpleFixture,
  toggleRouteSegmentLock,
  validateNetRoute,
  type NetRoute,
} from "../src/index";

function lineRoute(): NetRoute {
  return ensureRouteIds({
    vertices: [
      { id: "source", kind: "endpoint", terminal_id: "producer_0:port:data", point: { x: 0, y: 0 } },
      { id: "source-stub", kind: "bend", point: { x: 20, y: 0 } },
      { id: "target-stub", kind: "bend", point: { x: 80, y: 0 } },
      { id: "target", kind: "endpoint", terminal_id: "consumer_0:port:data", point: { x: 100, y: 0 } },
    ],
    segments: [
      { id: "source-segment", from_vertex: "source", to_vertex: "source-stub" },
      { id: "trunk", from_vertex: "source-stub", to_vertex: "target-stub" },
      { id: "target-segment", from_vertex: "target-stub", to_vertex: "target" },
    ],
  });
}

function expectOrthogonal(route: NetRoute): void {
  const vertices = new Map(route.vertices.map((vertex) => [vertex.id, vertex]));
  for (const segment of route.segments) {
    const start = vertices.get(segment.from_vertex)!.point;
    const end = vertices.get(segment.to_vertex)!.point;
    expect(start.x === end.x || start.y === end.y).toBe(true);
    expect(start).not.toEqual(end);
  }
}

describe("renderer-independent route editing", () => {
  test("drags a horizontal segment only vertically and snaps to the route grid", () => {
    const moved = moveRouteSegment(lineRoute(), "trunk", 37, 20);
    expect(moved.vertices.find((vertex) => vertex.id === "source-stub")?.point).toEqual({ x: 20, y: 40 });
    expect(moved.vertices.find((vertex) => vertex.id === "target-stub")?.point).toEqual({ x: 80, y: 40 });
    expectOrthogonal(moved);
    expect(validateNetRoute(simpleFixture(), "data", moved)).toEqual([]);
  });

  test("inserts and removes a stable degree-two bend", () => {
    const inserted = insertRouteBend(lineRoute(), "trunk", { x: 43, y: 99 }, 20);
    const bend = inserted.vertices.find((vertex) => vertex.id.startsWith("manual-bend"));
    expect(bend?.point).toEqual({ x: 40, y: 0 });
    expect(inserted.segments).toHaveLength(4);
    const removed = removeRouteBend(inserted, bend!.id);
    expect(removed.vertices.map((vertex) => vertex.id)).not.toContain(bend!.id);
    expect(removed.segments).toHaveLength(3);
    expectOrthogonal(removed);
  });

  test("locked route corridors reject direct manipulation", () => {
    const locked = toggleRouteSegmentLock(lineRoute(), "trunk");
    expect(moveRouteSegment(locked, "trunk", 40)).toEqual(locked);
    expect(setAllRouteLocks(locked, true).segments.every((segment) => segment.locked)).toBe(true);
  });

  test("reanchors one moved endpoint without changing the opposite endpoint or trunk id", () => {
    const route = lineRoute();
    const moved = reanchorRouteEndpoints(route, {
      "producer_0:port:data": { point: { x: 20, y: 80 }, stub: { x: 40, y: 80 } },
    });
    expect(moved.vertices.find((vertex) => vertex.id === "source")?.point).toEqual({ x: 20, y: 80 });
    expect(moved.vertices.find((vertex) => vertex.id === "target")?.point).toEqual({ x: 100, y: 0 });
    expect(moved.segments.some((segment) => segment.id === "trunk")).toBe(true);
    expectOrthogonal(moved);
  });

  test("moves a junction while repairing every branch orthogonally", () => {
    const route = ensureRouteIds({
      vertices: [
        { id: "a", kind: "endpoint", terminal_id: "a", point: { x: 0, y: 40 } },
        { id: "as", kind: "bend", point: { x: 20, y: 40 } },
        { id: "j", kind: "junction", point: { x: 60, y: 40 } },
        { id: "b", kind: "endpoint", terminal_id: "b", point: { x: 100, y: 0 } },
        { id: "bs", kind: "bend", point: { x: 80, y: 0 } },
        { id: "c", kind: "endpoint", terminal_id: "c", point: { x: 100, y: 80 } },
        { id: "cs", kind: "bend", point: { x: 80, y: 80 } },
      ],
      segments: [
        { id: "a0", from_vertex: "a", to_vertex: "as" }, { id: "a1", from_vertex: "as", to_vertex: "j" },
        { id: "b0", from_vertex: "b", to_vertex: "bs" }, { id: "b1", from_vertex: "bs", to_vertex: "j" },
        { id: "c0", from_vertex: "c", to_vertex: "cs" }, { id: "c1", from_vertex: "cs", to_vertex: "j" },
      ],
    });
    const moved = moveRouteVertex(route, "j", { x: 77, y: 57 }, 20);
    expect(moved.vertices.find((vertex) => vertex.id === "j")?.point).toEqual({ x: 80, y: 60 });
    expectOrthogonal(moved);
    expect(moved.vertices.find((vertex) => vertex.id === "j")?.kind).toBe("junction");
  });
});
