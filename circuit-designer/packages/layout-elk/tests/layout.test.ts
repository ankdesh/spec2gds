import { describe, expect, test } from "vitest";
import { fixtures, largeFixture, validateGraph } from "@spec2gds/circuit-core";
import { layoutCircuitGraph } from "../src/index";

describe("ELK layout adapter", () => {
  for (const [name, build] of Object.entries(fixtures)) {
    if (name === "large") continue;
    test(`lays out ${name}`, async () => {
      const graph = build();
      expect(validateGraph(graph).valid).toBe(true);
      const result = await layoutCircuitGraph(graph);
      expect(Object.keys(result.layout.node_geometry)).toHaveLength(graph.nodes.length);
      expect(Object.keys(result.layout.net_routes)).toHaveLength(graph.nets.length);
      for (const geometry of Object.values(result.layout.node_geometry)) {
        expect(geometry.x % 20).toBe(0);
        expect(geometry.y % 20).toBe(0);
      }
      for (const route of Object.values(result.layout.net_routes)) {
        for (const segment of route.segments) {
          const start = route.vertices.find((vertex) => vertex.id === segment.from_vertex)!.point;
          const end = route.vertices.find((vertex) => vertex.id === segment.to_vertex)!.point;
          expect(start.x === end.x || start.y === end.y).toBe(true);
        }
        for (const endpoint of route.vertices.filter((vertex) => vertex.kind === "endpoint")) {
          const adjacentSegment = route.segments.find((segment) => segment.from_vertex === endpoint.id || segment.to_vertex === endpoint.id)!;
          const adjacentId = adjacentSegment.from_vertex === endpoint.id ? adjacentSegment.to_vertex : adjacentSegment.from_vertex;
          const adjacent = route.vertices.find((vertex) => vertex.id === adjacentId)!;
          const placement = result.layout.terminal_placements[endpoint.terminal_id!];
          if (placement.side === "EAST") expect(adjacent.point.x).toBeGreaterThan(endpoint.point.x);
          if (placement.side === "WEST") expect(adjacent.point.x).toBeLessThan(endpoint.point.x);
          if (placement.side === "NORTH") expect(adjacent.point.y).toBeLessThan(endpoint.point.y);
          if (placement.side === "SOUTH") expect(adjacent.point.y).toBeGreaterThan(endpoint.point.y);
          if (placement.side === "EAST" || placement.side === "WEST") expect(adjacent.point.y).toBe(endpoint.point.y);
          else expect(adjacent.point.x).toBe(endpoint.point.x);
        }
      }
    });
  }

  test("handles the 200-node scale fixture", async () => {
    const result = await layoutCircuitGraph(largeFixture());
    expect(Object.keys(result.layout.node_geometry)).toHaveLength(200);
    expect(Object.keys(result.layout.net_routes)).toHaveLength(398);
  }, 20_000);

  test("uses circuit route trees and preserves pinned geometry overrides", async () => {
    const graph = fixtures.simple();
    graph.layout = {
      direction: "RIGHT",
      node_geometry: { producer_0: { x: 25, y: 35, width: 180, height: 84, pinned: true } },
      terminal_placements: {},
      net_routes: {},
    };
    const result = await layoutCircuitGraph(graph);
    expect(result.layout.node_geometry?.producer_0).toMatchObject({ x: 20, y: 40, pinned: true });
    expect(result.layout.net_routes?.data.vertices.some((vertex) => vertex.id.startsWith("stub:"))).toBe(true);
    expect(result.layout.net_routes?.data.vertices.some((vertex) => vertex.id.startsWith("route:"))).toBe(false);
  });

  test("routes fanout as one shared trunk without duplicate ELK branches", async () => {
    const result = await layoutCircuitGraph(fixtures.hyperedge());
    const route = result.layout.net_routes?.broadcast;
    expect(route).toBeDefined();
    const trunks = route!.vertices.filter((vertex) => vertex.id.startsWith("trunk:"));
    expect(trunks).toHaveLength(4);
    expect(new Set(trunks.map((vertex) => vertex.point.x))).toHaveLength(1);
    expect(route!.vertices.some((vertex) => vertex.id.startsWith("route:"))).toBe(false);
    const segmentKeys = route!.segments.map((segment) => [segment.from_vertex, segment.to_vertex].sort().join("|"));
    expect(new Set(segmentKeys).size).toBe(segmentKeys.length);
  });
});
