import { describe, expect, test } from "vitest";
import { crossingFixture, fixtures, setAllRouteLocks, simpleDocumentFixture, stageForHorizontalSpan, validateNetRoute } from "@spec2gds/circuit-core";
import {
  layoutCircuitDocument,
  layoutCircuitGraph,
  reanchorRoutesForNode,
  routeCircuitNets,
  routeIntersectsGeometry,
  routesCrossOrOverlap,
  terminalSide,
} from "../src/index";

describe("deterministic circuit layout", () => {
  for (const [name, build] of Object.entries(fixtures)) {
    if (name === "large") continue;
    test(`places and routes ${name}`, async () => {
      const graph = build();
      const result = await layoutCircuitGraph(graph);
      expect(Object.keys(result.layout.node_geometry)).toHaveLength(graph.nodes.length);
      expect(Object.keys(result.layout.net_routes)).toHaveLength(graph.nets.length);
      for (const geometry of Object.values(result.layout.node_geometry)) {
        expect(geometry.x % 20).toBe(0);
        expect(geometry.y % 20).toBe(0);
      }
      const geometries = Object.values(result.layout.node_geometry);
      for (let first = 0; first < geometries.length; first += 1) for (let second = first + 1; second < geometries.length; second += 1) {
        const a = geometries[first]; const b = geometries[second];
        const overlap = a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
        expect(overlap).toBe(false);
      }
      for (const net of graph.nets) {
        const route = result.layout.net_routes![net.id];
        expect(validateNetRoute(graph, net.id, route)).toEqual([]);
        for (const geometry of Object.values(result.layout.node_geometry)) expect(routeIntersectsGeometry(route, geometry)).toBe(false);
      }
    });
  }

  test("routes automatic nets jointly without crossings or overlaps", async () => {
    for (const graph of [fixtures.mixed(), fixtures.cycle()]) {
      const result = await layoutCircuitGraph(graph);
      const routes = Object.values(result.layout.net_routes!);
      for (let first = 0; first < routes.length; first += 1) {
        for (let second = first + 1; second < routes.length; second += 1) {
          expect(routesCrossOrOverlap(routes[first], routes[second])).toBe(false);
        }
      }
    }
  });

  test("places bidirectional terminals on the neutral south side", async () => {
    const graph = fixtures.bidirectional();
    expect(graph.terminals.every((terminal) => terminal.direction === "inout")).toBe(true);
    expect(graph.terminals.map(terminalSide)).toEqual(["SOUTH", "SOUTH"]);
    const result = await layoutCircuitGraph(graph);
    expect(Object.values(result.layout.terminal_placements).map((placement) => placement.side))
      .toEqual(["SOUTH", "SOUTH"]);
  });

  test("reroutes around fixed blocks and a user-locked net", async () => {
    const graph = crossingFixture();
    const initial = await layoutCircuitGraph(graph);
    const horizontal = setAllRouteLocks(initial.layout.net_routes!.horizontal, true);
    const layout = {
      ...initial.layout,
      net_routes: { ...initial.layout.net_routes, horizontal },
    };
    const rerouted = routeCircuitNets(graph, layout, initial.boundary_geometry, ["horizontal", "vertical"], true);
    expect(rerouted.horizontal).toEqual(horizontal);
    expect(routesCrossOrOverlap(rerouted.horizontal, rerouted.vertical)).toBe(false);
    for (const route of Object.values(rerouted)) {
      for (const geometry of Object.values(layout.node_geometry!)) expect(routeIntersectsGeometry(route, geometry)).toBe(false);
    }
  });

  test("keeps endpoint stubs perpendicular to their component sides", async () => {
    const graph = fixtures.hyperedge();
    const result = await layoutCircuitGraph(graph);
    const route = result.layout.net_routes!.broadcast;
    for (const endpoint of route.vertices.filter((vertex) => vertex.kind === "endpoint")) {
      const segment = route.segments.find((item) => item.from_vertex === endpoint.id || item.to_vertex === endpoint.id)!;
      const neighbourId = segment.from_vertex === endpoint.id ? segment.to_vertex : segment.from_vertex;
      const neighbour = route.vertices.find((vertex) => vertex.id === neighbourId)!;
      const placement = result.layout.terminal_placements[endpoint.terminal_id!];
      if (placement.side === "EAST") expect(neighbour.point).toMatchObject({ x: endpoint.point.x + 20, y: endpoint.point.y });
      if (placement.side === "WEST") expect(neighbour.point).toMatchObject({ x: endpoint.point.x - 20, y: endpoint.point.y });
      if (placement.side === "NORTH") expect(neighbour.point).toMatchObject({ x: endpoint.point.x, y: endpoint.point.y - 20 });
      if (placement.side === "SOUTH") expect(neighbour.point).toMatchObject({ x: endpoint.point.x, y: endpoint.point.y + 20 });
    }
  });

  test("component drag reroutes unlocked nets but preserves locked geometry", async () => {
    const graph = fixtures.simple();
    const initial = await layoutCircuitGraph(graph);
    const node = initial.layout.node_geometry!.producer_0;
    const moved = { ...node, x: node.x + 80, y: node.y + 80, pinned: true };
    const unlocked = reanchorRoutesForNode(graph, initial.layout, initial.boundary_geometry, "producer_0", moved).data;
    expect(unlocked).not.toEqual(initial.layout.net_routes!.data);

    const locked = setAllRouteLocks(initial.layout.net_routes!.data, true);
    const lockedLayout = { ...initial.layout, net_routes: { data: locked } };
    const preserved = reanchorRoutesForNode(graph, lockedLayout, initial.boundary_geometry, "producer_0", moved).data;
    for (const segment of locked.segments) {
      expect(preserved.segments.find((item) => item.id === segment.id)?.locked).toBe(true);
    }
  });

  test("route optimization leaves component geometry unchanged", async () => {
    const graph = fixtures.mixed();
    const result = await layoutCircuitGraph(graph);
    const before = structuredClone(result.layout.node_geometry);
    routeCircuitNets(graph, result.layout, result.boundary_geometry, graph.nets.map((net) => net.id), false);
    expect(result.layout.node_geometry).toEqual(before);
  });

  test("auto layout preserves pinned geometry and replaces unpinned geometry", async () => {
    const graph = fixtures.simple();
    graph.layout = {
      direction: "RIGHT",
      terminal_placements: {}, net_routes: {},
      node_geometry: {
        producer_0: { x: 1000, y: 1000, width: 180, height: 100, pinned: true },
        consumer_0: { x: 1200, y: 1200, width: 180, height: 100, pinned: false },
      },
    };
    const result = await layoutCircuitGraph(graph, { preserveNodeGeometry: "pinned" });
    expect(result.layout.node_geometry?.producer_0).toMatchObject({ x: 1000, y: 1000, pinned: true });
    expect(result.layout.node_geometry?.consumer_0).not.toMatchObject({ x: 1200, y: 1200 });
  });

  test("auto layout preserves each instance's timing stage", async () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry.producer_0 = { x: 80, y: 80, width: 180, height: 100, pinned: false };
    document.layout.instance_geometry.consumer_0 = { x: 420, y: 80, width: 180, height: 100, pinned: false };
    document.timing = {
      schema_version: 1,
      clock_domains: [{ id: "default", label: "clk" }],
      cycle_edges: [{ id: "edge_1", x: 340, locked: false }],
      subject_domain_overrides: {},
    };

    const result = await layoutCircuitDocument(document, { preserveNodeGeometry: "none" });
    const edge = result.document.timing!.cycle_edges[0];
    expect(stageForHorizontalSpan(result.document.timing!, result.document.layout.instance_geometry.producer_0.x, result.document.layout.instance_geometry.producer_0.x + result.document.layout.instance_geometry.producer_0.width)).toBe(0);
    expect(stageForHorizontalSpan(result.document.timing!, result.document.layout.instance_geometry.consumer_0.x, result.document.layout.instance_geometry.consumer_0.x + result.document.layout.instance_geometry.consumer_0.width)).toBe(1);
    expect(edge.x % document.layout.grid_size).toBe(0);
  });

  test("handles the 200-node scale fixture", async () => {
    const graph = fixtures.large();
    const result = await layoutCircuitGraph(graph);
    expect(Object.keys(result.layout.node_geometry)).toHaveLength(200);
    expect(Object.keys(result.layout.net_routes)).toHaveLength(graph.nets.length);
  }, 20_000);
});
