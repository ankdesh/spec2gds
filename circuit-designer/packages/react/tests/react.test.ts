import { describe, expect, test } from "vitest";
import { simpleFixture, type NetRoute } from "@spec2gds/circuit-core";
import {
  buildCircuitFlowEdges,
  circuitSelectionsEqual,
  connectionRejectionReason,
  terminalDisplayLabel,
  terminalHandleId,
  terminalIdFromHandle,
} from "../src/index";

describe("React Flow circuit model", () => {
  test("binds every rendered net to an explicit source and target terminal handle", () => {
    const graph = simpleFixture();
    const route: NetRoute = {
      vertices: [
        { id: "a", kind: "endpoint", terminal_id: "producer_0:data", point: { x: 0, y: 0 } },
        { id: "b", kind: "endpoint", terminal_id: "consumer_0:data", point: { x: 100, y: 0 } },
      ],
      segments: [{ from_vertex: "a", to_vertex: "b" }],
    };

    const edges = buildCircuitFlowEdges(graph, { data: route });

    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({
      source: "producer_0",
      target: "consumer_0",
      sourceHandle: terminalHandleId("producer_0:data", "source"),
      targetHandle: terminalHandleId("consumer_0:data", "target"),
    });
  });

  test("does not hand React Flow an edge until its route exists", () => {
    expect(buildCircuitFlowEdges(simpleFixture(), {})).toEqual([]);
  });

  test("uses one role-independent connection handle per terminal", () => {
    expect(terminalHandleId("node:port:data")).toBe("node:port:data");
    expect(terminalIdFromHandle("node:port:data")).toBe("node:port:data");
  });

  test("renders symbolic width text without changing numeric terminal labels", () => {
    expect(terminalDisplayLabel({ label: "data", width: "[DATA_WIDTH-1:0]" }))
      .toBe("data [DATA_WIDTH-1:0]");
    expect(terminalDisplayLabel({ label: "valid", width: 1 })).toBe("valid");
  });

  test("only permits new connections between two distinct free terminals", () => {
    const occupied = simpleFixture();
    expect(connectionRejectionReason(occupied, "producer_0:data", "consumer_0:data")).toBe("terminal_in_use");
    const free = { ...occupied, nets: [] };
    expect(connectionRejectionReason(free, "producer_0:data", "producer_0:data")).toBe("same_terminal");
    expect(connectionRejectionReason(free, "producer_0:data", "missing:data")).toBe("invalid_target");
    expect(connectionRejectionReason(free, "producer_0:data", "consumer_0:data")).toBeUndefined();
  });

  test("does not emit controlled selection changes for order-only differences", () => {
    expect(circuitSelectionsEqual(
      [{ kind: "node", id: "producer_0" }, { kind: "net", id: "data" }],
      [{ kind: "net", id: "data" }, { kind: "node", id: "producer_0" }],
    )).toBe(true);
    expect(circuitSelectionsEqual([{ kind: "node", id: "producer_0" }], [])).toBe(false);
  });

  test("provides stable editable segment identity without changing semantic connectivity", () => {
    const graph = simpleFixture();
    const route: NetRoute = {
      vertices: [
        { id: "a", kind: "endpoint", terminal_id: "producer_0:data", point: { x: 0, y: 0 } },
        { id: "b", kind: "endpoint", terminal_id: "consumer_0:data", point: { x: 100, y: 0 } },
      ],
      segments: [{ id: "data-trunk", from_vertex: "a", to_vertex: "b", locked: true }],
    };
    const edges = buildCircuitFlowEdges(graph, { data: route }, { routeEditableNetId: "data", gridSize: 20 });
    expect(edges[0].data?.routeEditable).toBe(true);
    expect(edges[0].data?.route.segments[0]).toMatchObject({ id: "data-trunk", locked: true });
    expect(edges[0].source).toBe("producer_0");
    expect(edges[0].target).toBe("consumer_0");
  });
});
