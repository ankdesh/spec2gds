import { describe, expect, it } from "vitest";
import { compactCircuitInstanceLabel, compactCircuitTerminalLabel, hierarchyDocumentFixture, circuitFrameGeometry, effectiveCircuitTerminalPlacements, projectDocument, renderCircuitSvg, simpleDocumentFixture } from "../src/index";

describe("Circuit Designer visual export", () => {
  it("keeps instance identification in metadata and one Component title in exports", () => {
    const document = simpleDocumentFixture();
    document.design.instances[0].label = "enabled_eight_bit_register_12";
    const compact = compactCircuitInstanceLabel(document.design.instances[0].label, 17);
    expect(compact).toHaveLength(17);
    expect(compact).toMatch(/…_12$/);
    const svg = renderCircuitSvg(document);
    expect(svg).toContain(" · Instance enabled_eight_bit_register_12</title>");
    expect(svg).not.toMatch(/>enabled_eight_bit_register_12<\/text>/);
    expect(compactCircuitInstanceLabel("u_lane0", 17)).toBe("u_lane0");
  });
  it("preserves width suffixes and full inspection labels when names are shortened", () => {
    const document = simpleDocumentFixture();
    for (const component of document.components) component.terminals[0] = { ...component.terminals[0], label: "long_operand_name", width: 32 };
    const compact = compactCircuitTerminalLabel(document.components[0].terminals[0], 13);
    expect(compact).toMatch(/… · 32b$/);
    const svg = renderCircuitSvg(document);
    expect(svg).toContain(compact);
    expect(svg).toContain("<title>long_operand_name · 32 bits</title>");
    expect(compactCircuitTerminalLabel({ label: "a", width: "[N-1:0]" }, 13)).toContain("[N-1:0]");
  });

  it("does not repeat an identical Component and instance name", () => {
    const document = simpleDocumentFixture();
    for (const instance of document.design.instances) instance.label = document.components.find(item => item.id === instance.component_id)!.label;
    const svg = renderCircuitSvg(document);
    expect(svg).not.toContain('class="component-eyebrow"');
    expect(svg).toContain('class="component-label"');
    expect(svg).toContain(`data-component-id="${document.components[0].id}"`);
  });
  it("renders canvas colors, component details, ports, routes, and explicit dimensions", () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry = {
      producer_0: { x: 20, y: 40, width: 180, height: 100, pinned: true },
      consumer_0: { x: 320, y: 40, width: 180, height: 100, pinned: true },
    };
    document.layout.terminal_placements = {
      "producer_0:data": { side: "EAST", order: 0, locked: false },
      "consumer_0:data": { side: "WEST", order: 0, locked: false },
    };
    document.layout.net_routes.data = {
      vertices: [
        { id: "source", kind: "endpoint", terminal_id: "producer_0:data", point: { x: 200, y: 100 } },
        { id: "target", kind: "endpoint", terminal_id: "consumer_0:data", point: { x: 320, y: 100 } },
      ],
      segments: [{ id: "trunk", from_vertex: "source", to_vertex: "target", locked: true }],
    };

    const svg = renderCircuitSvg(document);

    expect(svg).toMatch(/^<svg[^>]+width="1000"[^>]+height="440"/);
    expect(svg).toContain(".canvas-background{fill:#f7f9fc}");
    expect(svg).toContain('pattern id="canvas-grid" width="20" height="20"');
    expect(svg).toContain('fill="url(#canvas-grid)"');
    expect(svg).toContain(".component{fill:#ffffff;stroke:#7b8fa1");
    expect(svg).toContain('data-instance-id="producer_0"');
    expect(svg).toContain('data-terminal-id="producer_0:data"');
    expect(svg).toContain('class="net net--locked"');
    expect(svg).toContain(" · Instance producer_0</title>");
  });

  it("includes the Design frame and its visible boundary terminals from effective canvas geometry", () => {
    const document = hierarchyDocumentFixture();
    document.layout.instance_geometry.pipeline_0 = { x: 100, y: 100, width: 180, height: 100 };
    document.layout.terminal_placements = {
      "pipeline_0:request": { side: "WEST", order: 0 },
      "pipeline_0:response": { side: "EAST", order: 0 },
      "boundary:request": { side: "EAST", order: 0 },
      "boundary:response": { side: "WEST", order: 0 },
    };
    const graph = projectDocument(document);
    const frame = circuitFrameGeometry(graph, graph.layout.node_geometry, effectiveCircuitTerminalPlacements(graph));
    const svg = renderCircuitSvg(document, { boundaryGeometry: frame.boundary_geometry, containerGeometry: frame.container_geometry });

    expect(svg).toContain('data-boundary-id="request"');
    expect(svg).toContain('data-boundary-id="response"');
    expect(svg).toContain('data-terminal-id="boundary:request"');
    expect(svg).toContain('data-terminal-id="boundary:response"');
    expect(svg).not.toContain('<title>boundary</title>');
    expect(svg).toContain('data-design-frame=');
    expect(svg).not.toMatch(/<g data-boundary-id="[^"]+"><rect/);
    const view = svg.match(/viewBox="([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)"/)!;
    expect(Number(view[1])).toBeLessThan(frame.container_geometry.x);
    expect(Number(view[1]) + Number(view[3])).toBeGreaterThan(frame.container_geometry.x + frame.container_geometry.width);
  });

  it("renders human-readable component labels in SVG title and preserves internal ID in diagnostics (UI-CIRCUIT-007)", () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry = {
      producer_0: { x: 20, y: 40, width: 140, height: 100, pinned: true },
    };
    const comp = document.components.find((item) => item.id === "producer");
    if (comp) {
      comp.id = "long_internal_uuid_producer_hw_block_1234567890";
      comp.label = "Sensor Stream Producer";
      document.design.instances[0].component_id = comp.id;
    }
    const svg = renderCircuitSvg(document);
    // Use the Component display name for the visible title.
    expect(svg).toContain("Sensor Stream");
    expect(svg).not.toMatch(/class="component-eyebrow"[^>]*>long_internal_uuid/);
    // Preserve the Component ID in metadata and the instance name in the tooltip.
    expect(svg).toContain('data-component-id="long_internal_uuid_producer_hw_block_1234567890"');
    expect(svg).toContain("<title>Sensor Stream Producer · Instance producer_0</title>");
  });
});
