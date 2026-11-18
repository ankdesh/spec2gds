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

function dataflowFixture(edges: Array<[string, string]>) {
  const document = simpleDocumentFixture();
  const ids = [...new Set(edges.flat())];
  document.components = ids.map(id => ({
    id, label: id, origin: "local" as const, editable: true, parameters: [],
    appearance: { renderer_key: "generic", properties: {} },
    terminals: [
      { id: "clk", label: "clk", direction: "input" as const, width: 1, category: "port" as const },
      ...edges.flatMap(([source, target], n) => source === id
        ? [{ id: `out${n}`, label: `out${n}`, direction: "output" as const, width: 1, category: "port" as const }]
        : target === id ? [{ id: `in${n}`, label: `in${n}`, direction: "input" as const, width: 1, category: "port" as const }] : []),
    ],
  }));
  document.design.instances = ids.map(id => ({ id, label: id, component_id: id, parameter_values: {} }));
  document.design.boundary_terminals = [{ id: "clk", label: "clk", direction: "input", width: 1, category: "port" }];
  document.design.nets = edges.map(([source, target], n) => ({ id: `net${n}`, label: `net${n}`, endpoints: [
    { kind: "instance" as const, instance_id: source, terminal_id: `out${n}` },
    { kind: "instance" as const, instance_id: target, terminal_id: `in${n}` },
  ] }));
  document.design.nets.push({ id: "clock", label: "clock", endpoints: [
    ...[...ids].reverse().map(id => ({ kind: "instance" as const, instance_id: id, terminal_id: "clk" })),
    { kind: "boundary", terminal_id: "clk" },
  ] });
  document.layout.instance_geometry = Object.fromEntries(ids.map((id, index) => [id, { x: 80, y: 80 + 260 * index, width: 180, height: 160, pinned: false }]));
  document.layout.net_routes = {};
  document.layout.terminal_placements = {};
  return document;
}

describe("deterministic circuit layout", () => {
  test("keeps framed routes inside the content area across save and reopen", async () => {
    const document = dataflowFixture([["input", "output"]]);
    const original = structuredClone(document.layout.instance_geometry);
    const first = await layoutCircuitDocument(document);
    const second = await layoutCircuitDocument(first.document);
    expect(first.document.layout.instance_geometry).toEqual(original);
    expect(second.container_geometry).toEqual(first.container_geometry);
    expect(second.boundary_geometry).toEqual(first.boundary_geometry);
    const frame = first.container_geometry;
    for (const route of Object.values(first.layout.net_routes)) for (const vertex of route.vertices) {
      expect(vertex.point.x).toBeGreaterThanOrEqual(frame.x);
      expect(vertex.point.x).toBeLessThanOrEqual(frame.x + frame.width);
      expect(vertex.point.y).toBeGreaterThanOrEqual(frame.y + 60);
      expect(vertex.point.y).toBeLessThanOrEqual(frame.y + frame.height);
    }
  });

  test("expands the frame after an instance moves without moving its peers", async () => {
    const document = simpleDocumentFixture();
    const first = await layoutCircuitDocument(document);
    const moved = structuredClone(first.document);
    moved.layout.instance_geometry.consumer_0.x += 2000;
    moved.layout.net_routes = {};
    const next = await layoutCircuitDocument(moved);
    expect(next.layout.node_geometry.consumer_0.x).toBe(moved.layout.instance_geometry.consumer_0.x);
    expect(next.layout.node_geometry.producer_0).toEqual(first.layout.node_geometry.producer_0);
    expect(next.container_geometry.width).toBeGreaterThan(first.container_geometry.width);
  });

  test("places a new disconnected instance clear of saved coordinates", async () => {
    const document = simpleDocumentFixture();
    document.design.nets = [];
    document.layout.instance_geometry = { producer_0: { x: 80, y: 80, width: 180, height: 100, pinned: true } };
    const result = await layoutCircuitDocument(document);
    const producer = result.layout.node_geometry.producer_0, consumer = result.layout.node_geometry.consumer_0;
    expect(producer).toEqual(document.layout.instance_geometry.producer_0);
    expect(consumer.y).toBeGreaterThanOrEqual(producer.y + producer.height);
  });

  test("arranges data flow despite reverse-ordered shared boundary fan-out", async () => {
    const document = dataflowFixture([["z_input", "m_add"], ["m_add", "a_output"]]);
    const result = await layoutCircuitDocument(document, { preserveNodeGeometry: "pinned" });
    const geometry = result.document.layout.instance_geometry;
    expect(geometry.z_input.x).toBeLessThan(geometry.m_add.x);
    expect(geometry.m_add.x).toBeLessThan(geometry.a_output.x);
    expect(document.layout.instance_geometry.a_output.x).toBe(80);
  });

  test("keeps parallel arithmetic before its selector and output register", async () => {
    const document = dataflowFixture([["add", "select"], ["sub", "select"], ["select", "result"]]);
    const result = await layoutCircuitDocument(document, { preserveNodeGeometry: "pinned" });
    const geometry = result.document.layout.instance_geometry;
    expect(geometry.add.x).toBe(geometry.sub.x);
    expect(geometry.select.x).toBeGreaterThan(geometry.add.x);
    expect(geometry.result.x).toBeGreaterThan(geometry.select.x);
  });

  test("arranges feedback deterministically without inferring protocol direction", async () => {
    const document = dataflowFixture([["fifo", "slice"], ["slice", "fifo"]]);
    const first = await layoutCircuitDocument(document, { preserveNodeGeometry: "pinned" });
    const second = await layoutCircuitDocument(document, { preserveNodeGeometry: "pinned" });
    expect(first.document.layout).toEqual(second.document.layout);
    expect(first.document.layout.instance_geometry.fifo.x).not.toBe(first.document.layout.instance_geometry.slice.x);
  });
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

  test("Arrange keeps pinned geometry and route locks with timing markers", async () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry = {
      producer_0: { x: 80, y: 80, width: 180, height: 100, pinned: true },
      consumer_0: { x: 500, y: 80, width: 180, height: 100, pinned: false },
    };
    document.timing = { schema_version: 1, clock_domains: [{ id: "default", label: "clk" }], cycle_edges: [{ id: "edge", x: 340, locked: true }], subject_domain_overrides: {} };
    const initial = await layoutCircuitDocument(document);
    expect(initial.document.layout.instance_geometry.producer_0).toEqual(document.layout.instance_geometry.producer_0);
    initial.document.layout.net_routes.data = setAllRouteLocks(initial.document.layout.net_routes.data, true);
    const pinned = structuredClone(initial.document.layout.instance_geometry.producer_0);
    const arranged = await layoutCircuitDocument(initial.document, { preserveNodeGeometry: "pinned" });
    expect(arranged.document.layout.instance_geometry.producer_0).toEqual(pinned);
    expect(arranged.document.layout.instance_geometry.consumer_0).toEqual(initial.document.layout.instance_geometry.consumer_0);
    expect(arranged.document.timing!.cycle_edges).toEqual(document.timing.cycle_edges);
    for (const segment of initial.document.layout.net_routes.data.segments) {
      expect(arranged.document.layout.net_routes.data.segments.find(item => item.id === segment.id)?.locked).toBe(true);
    }
  });

  test("handles the 200-node scale fixture", async () => {
    const graph = fixtures.large();
    const result = await layoutCircuitGraph(graph);
    expect(Object.keys(result.layout.node_geometry)).toHaveLength(200);
    expect(Object.keys(result.layout.net_routes)).toHaveLength(graph.nets.length);
  }, 20_000);
});
