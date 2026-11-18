import { describe, expect, it } from "vitest";
import { CIRCUIT_FRAME_HEADER_HEIGHT, circuitFrameGeometry, circuitTerminalPoint, createEmptyCircuitDocument, effectiveCircuitTerminalPlacements, projectDocument, renderCircuitSvg, simpleDocumentFixture } from "../src/index";

describe("Component and Design frames", () => {
  it("shows an empty frame without adding hardware or changing the document", () => {
    const document = createEmptyCircuitDocument("empty");
    const before = structuredClone(document);
    const graph = projectDocument(document);
    const frame = circuitFrameGeometry(graph, {});
    expect(frame.container_geometry.width).toBeGreaterThanOrEqual(640);
    expect(frame.container_geometry.height).toBeGreaterThanOrEqual(360);
    expect(frame.boundary_geometry).toEqual({});
    expect(renderCircuitSvg(document)).toContain('data-design-frame="top"');
    expect(document).toEqual(before);
    expect(renderCircuitSvg(document, { container: false })).not.toContain('data-design-frame=');
  });

  it("puts inward handles on the frame with input, output, and bidirectional defaults", () => {
    const document = createEmptyCircuitDocument("ports");
    document.design.boundary_terminals = [
      { id: "a", label: "a", direction: "input", width: 16 },
      { id: "y", label: "y", direction: "output", width: 16 },
      { id: "io", label: "io", direction: "inout", width: 1 },
    ];
    const graph = projectDocument(document);
    const placements = effectiveCircuitTerminalPlacements(graph);
    const frame = circuitFrameGeometry(graph, {}, placements);
    const box = frame.container_geometry;
    const point = (id: string) => circuitTerminalPoint(frame.boundary_geometry[`boundary:${id}`], placements[`boundary:${id}`]);
    expect(point("a").x).toBe(box.x);
    expect(point("y").x).toBe(box.x + box.width);
    expect(point("io").y).toBe(box.y + box.height);
    const svg = renderCircuitSvg(document);
    expect(svg).toContain(`x="${point("a").x + 40}"`);
    expect(svg).toContain(`x="${point("y").x - 40}"`);
    expect(svg).toContain('data-boundary-id="a"/>');
  });

  it("preserves all saved inward sides and port order", () => {
    const document = createEmptyCircuitDocument("sides");
    const sides = ["EAST", "WEST", "SOUTH", "NORTH"] as const;
    for (const [index, side] of sides.entries()) {
      document.design.boundary_terminals.push({ id: `p${index}`, label: `p${index}`, direction: "input", width: 1 });
      document.layout.terminal_placements[`boundary:p${index}`] = { side, order: 9 - index, locked: true };
    }
    const graph = projectDocument(document), placements = effectiveCircuitTerminalPlacements(graph);
    expect(placements).toEqual(document.layout.terminal_placements);
    const frame = circuitFrameGeometry(graph, {}, placements), box = frame.container_geometry;
    const points = sides.map((_, index) => circuitTerminalPoint(frame.boundary_geometry[`boundary:p${index}`], placements[`boundary:p${index}`]));
    expect(points[0].x).toBe(box.x);
    expect(points[1].x).toBe(box.x + box.width);
    expect(points[2].y).toBe(box.y + CIRCUIT_FRAME_HEADER_HEIGHT);
    expect(points[3].y).toBe(box.y + box.height);
  });

  it("fits many ports with readable spacing and stable geometry", () => {
    const document = createEmptyCircuitDocument("many");
    document.design.boundary_terminals = Array.from({ length: 40 }, (_, index) => ({ id: `p${index}`, label: `Long port ${index}`, direction: "input" as const, width: 32 }));
    const graph = projectDocument(document), placements = effectiveCircuitTerminalPlacements(graph);
    const first = circuitFrameGeometry(graph, {}, placements);
    const ys = Object.entries(first.boundary_geometry).map(([id, box]) => circuitTerminalPoint(box, placements[id]).y).sort((a, b) => a - b);
    expect(ys.every((y, index) => !index || y - ys[index - 1] >= 40)).toBe(true);
    expect(ys.at(-1)).toBeLessThan(first.container_geometry.y + first.container_geometry.height);
    expect(circuitFrameGeometry(graph, {}, placements)).toEqual(first);
  });

  it("accepts the previous layout while a new port awaits asynchronous layout", () => {
    const document = createEmptyCircuitDocument("new_port");
    const oldPlacements = effectiveCircuitTerminalPlacements(projectDocument(document));
    document.design.boundary_terminals.push({ id: "result", label: "result", direction: "output", width: 16 });
    const frame = circuitFrameGeometry(projectDocument(document), {}, oldPlacements);
    expect(frame.boundary_geometry["boundary:result"].x).toBe(frame.container_geometry.x + frame.container_geometry.width);
  });

  it("includes route interiors and preserves instance coordinates", () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry.producer_0 = { x: -400, y: -200, width: 180, height: 100 };
    document.layout.net_routes.data = { vertices: [{ id: "bend", kind: "bend", point: { x: -800, y: 900 } }], segments: [] };
    const graph = projectDocument(document), nodes = structuredClone(graph.layout.node_geometry);
    const box = circuitFrameGeometry(graph, nodes).container_geometry;
    expect(box.x).toBeLessThan(-800);
    expect(box.y + box.height).toBeGreaterThan(900);
    expect(graph.layout.node_geometry).toEqual(nodes);
  });

  it("reanchors legacy boundary routes in exports without changing saved data", () => {
    const document = simpleDocumentFixture();
    document.design.instances = [document.design.instances[1]];
    document.layout.instance_geometry = { consumer_0: { x: 320, y: 80, width: 180, height: 100 } };
    document.design.boundary_terminals = [{ id: "input", label: "input", direction: "input", width: 1 }];
    document.design.nets[0].endpoints[0] = { kind: "boundary", terminal_id: "input" };
    document.layout.net_routes.data = { vertices: [
      { id: "source", kind: "endpoint", terminal_id: "boundary:input", point: { x: -40, y: 140 } },
      { id: "target", kind: "endpoint", terminal_id: "consumer_0:data", point: { x: 320, y: 140 } },
    ], segments: [{ id: "wire", from_vertex: "source", to_vertex: "target" }] };
    const before = structuredClone(document), graph = projectDocument(document);
    const placements = effectiveCircuitTerminalPlacements(graph);
    const frame = circuitFrameGeometry(graph, graph.layout.node_geometry, placements);
    const point = circuitTerminalPoint(frame.boundary_geometry["boundary:input"], placements["boundary:input"]);
    const svg = renderCircuitSvg(document);
    expect(svg).toContain(`M ${point.x} ${point.y} L`);
    expect(svg).toContain(`cx="${point.x}" cy="${point.y}"`);
    expect(svg).not.toContain('d="M -40 140');
    expect(document).toEqual(before);
  });
});
