import { describe, expect, test } from "vitest";
import { simpleFixture, type NetRoute } from "@spec2gds/circuit-core";
import { buildCircuitFlowEdges, terminalHandleId, terminalIdFromHandle } from "../src/index";

describe("React Flow circuit model", () => {
  test("binds every rendered net to an explicit source and target terminal handle", () => {
    const graph = simpleFixture();
    const route: NetRoute = {
      vertices: [
        { id: "a", kind: "endpoint", terminal_id: "producer_0:port:data", point: { x: 0, y: 0 } },
        { id: "b", kind: "endpoint", terminal_id: "consumer_0:port:data", point: { x: 100, y: 0 } },
      ],
      segments: [{ from_vertex: "a", to_vertex: "b" }],
    };

    const edges = buildCircuitFlowEdges(graph, { data: route });

    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({
      source: "producer_0",
      target: "consumer_0",
      sourceHandle: terminalHandleId("producer_0:port:data", "source"),
      targetHandle: terminalHandleId("consumer_0:port:data", "target"),
    });
  });

  test("does not hand React Flow an edge until its route exists", () => {
    expect(buildCircuitFlowEdges(simpleFixture(), {})).toEqual([]);
  });

  test("maps either connection-handle role back to its semantic terminal", () => {
    expect(terminalIdFromHandle("node:port:data:source")).toBe("node:port:data");
    expect(terminalIdFromHandle("node:port:data:target")).toBe("node:port:data");
  });
});
