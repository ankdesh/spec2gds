import { describe, expect, it } from "vitest";
import { simpleDocumentFixture, obsidianTheme } from "@spec2gds/circuit-core";
import { layoutCircuitGraph } from "@spec2gds/circuit-layout";
import { projectDocument, renderCircuitSvg } from "@spec2gds/circuit-core";

import {
  circuitSvgFilename,
  readDesignTopologyOptions,
  renderDesignTopology,
} from "../src/topology-live-view";

describe("design topology live views", () => {
  it("matches the saved canvas geometry, bends, and timing without changing the source", async () => {
    const document = simpleDocumentFixture();
    document.layout.instance_geometry = {
      producer_0: { x: 200, y: 120, width: 180, height: 120, pinned: false },
      consumer_0: { x: 200, y: 600, width: 180, height: 120, pinned: false },
    };
    const effective = await layoutCircuitGraph(projectDocument(document));
    document.layout.net_routes = effective.layout.net_routes;
    document.layout.terminal_placements = effective.layout.terminal_placements;
    document.timing = { schema_version: 1, clock_domains: [{ id: "default", label: "clk" }], cycle_edges: [{ id: "edge", x: 500, locked: false }], subject_domain_overrides: {} };
    const before = structuredClone(document);
    const preview = await renderDesignTopology(document);
    expect(preview.svg).toBe(renderCircuitSvg(document, { boundaryGeometry: effective.boundary_geometry }));
    expect(document).toEqual(before);
  });
  it("validates, lays out, and renders the shared Circuit Designer SVG", async () => {
    const rendered = await renderDesignTopology(simpleDocumentFixture());

    expect(rendered.width).toBeGreaterThan(0);
    expect(rendered.height).toBeGreaterThan(0);
    expect(rendered.svg).toContain('data-instance-id="producer_0"');
    expect(rendered.svg).toContain('data-terminal-id="producer_0:data"');
    expect(rendered.svg).toContain('fill="url(#canvas-grid)"');
    expect(rendered.svg).toContain('class="net"');
  });

  it("rejects malformed payloads and invalid circuit documents", async () => {
    expect(readDesignTopologyOptions({ schema_version: 1, status: "ready" })).toBeUndefined();
    expect(readDesignTopologyOptions({
      schema_version: 1,
      status: "empty",
      omitted_bus_items: [],
      omitted_ports: [],
    })?.status).toBe("empty");
    await expect(renderDesignTopology({} as never)).rejects.toThrow("required property");
  });

  it("renders the selected dark theme without changing Circuit geometry", async () => {
    const document = simpleDocumentFixture();
    const light = await renderDesignTopology(document);
    const dark = await renderDesignTopology(document, "obsidian");
    expect(dark.svg).toContain(`.canvas-background{fill:${obsidianTheme.colors.canvas}}`);
    expect([dark.width, dark.height]).toEqual([light.width, light.height]);
  });

  it("creates portable, bounded SVG filenames", () => {
    expect(circuitSvgFilename("Editor Test", "Top / Main")).toBe("editor-test-top-main-circuit.svg");
    expect(circuitSvgFilename("x".repeat(200), "design").length).toBeLessThanOrEqual(124);
  });
});
