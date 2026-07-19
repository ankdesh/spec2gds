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
      for (const route of Object.values(result.layout.net_routes)) {
        for (const segment of route.segments) {
          const start = route.vertices.find((vertex) => vertex.id === segment.from_vertex)!.point;
          const end = route.vertices.find((vertex) => vertex.id === segment.to_vertex)!.point;
          expect(start.x === end.x || start.y === end.y).toBe(true);
        }
      }
    });
  }

  test("handles the 200-node scale fixture", async () => {
    const result = await layoutCircuitGraph(largeFixture());
    expect(Object.keys(result.layout.node_geometry)).toHaveLength(200);
    expect(Object.keys(result.layout.net_routes)).toHaveLength(398);
  }, 20_000);
});
