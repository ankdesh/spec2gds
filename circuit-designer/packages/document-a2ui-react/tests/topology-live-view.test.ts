import { describe, expect, it } from "vitest";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";

import {
  circuitSvgFilename,
  readDesignTopologyOptions,
  renderDesignTopology,
} from "../src/topology-live-view";

describe("design topology live views", () => {
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

  it("creates portable, bounded SVG filenames", () => {
    expect(circuitSvgFilename("Editor Test", "Top / Main")).toBe("editor-test-top-main-circuit.svg");
    expect(circuitSvgFilename("x".repeat(200), "design").length).toBeLessThanOrEqual(124);
  });
});
