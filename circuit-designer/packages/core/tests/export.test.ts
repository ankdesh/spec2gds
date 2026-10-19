import { describe, expect, it } from "vitest";
import { hierarchyDocumentFixture, renderCircuitSvg, simpleDocumentFixture } from "../src/index";

describe("Circuit Designer visual export", () => {
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

    expect(svg).toMatch(/^<svg[^>]+width="560"[^>]+height="180"/);
    expect(svg).toContain(".canvas-background{fill:#f7f9fc}");
    expect(svg).toContain('pattern id="canvas-grid" width="20" height="20"');
    expect(svg).toContain('fill="url(#canvas-grid)"');
    expect(svg).toContain(".component{fill:#ffffff;stroke:#7b8fa1");
    expect(svg).toContain('data-instance-id="producer_0"');
    expect(svg).toContain('data-terminal-id="producer_0:data"');
    expect(svg).toContain('class="net net--locked"');
    expect(svg).toContain(">producer_0<");
  });

  it("includes boundary boxes and their visible terminals from effective canvas geometry", () => {
    const document = hierarchyDocumentFixture();
    document.layout.instance_geometry.pipeline_0 = { x: 100, y: 100, width: 180, height: 100 };
    document.layout.terminal_placements = {
      "pipeline_0:request": { side: "WEST", order: 0 },
      "pipeline_0:response": { side: "EAST", order: 0 },
      "boundary:request": { side: "EAST", order: 0 },
      "boundary:response": { side: "WEST", order: 0 },
    };
    const svg = renderCircuitSvg(document, {
      boundaryGeometry: {
        "boundary:request": { x: -40, y: 100, width: 20, height: 40 },
        "boundary:response": { x: 400, y: 100, width: 20, height: 40 },
      },
    });

    expect(svg).toContain('data-boundary-id="request"');
    expect(svg).toContain('data-boundary-id="response"');
    expect(svg).toContain('data-terminal-id="boundary:request"');
    expect(svg).toContain('data-terminal-id="boundary:response"');
    expect(svg).not.toContain('<title>boundary</title>');
    // Outside pin labels fit in the exported view instead of being cut by it.
    const view = svg.match(/viewBox="([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)"/)!;
    expect(Number(view[1])).toBeLessThan(-40 - 156);
    expect(Number(view[1]) + Number(view[3])).toBeGreaterThan(420 + 156);
  });

  it("renders human-readable component labels in SVG eyebrow and preserves internal ID in diagnostics (UI-CIRCUIT-007)", () => {
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
    // Eyebrow should prefer the readable label rather than raw long ID as visible text
    expect(svg).toContain("Sensor Stream");
    expect(svg).not.toMatch(/class="component-eyebrow"[^>]*>long_internal_uuid/);
    // Internal ID should be preserved in diagnostics (<title> and data-component-id)
    expect(svg).toContain('data-component-id="long_internal_uuid_producer_hw_block_1234567890"');
    expect(svg).toContain("<title>long_internal_uuid_producer_hw_block_1234567890</title>");
  });
});
