import { describe, expect, it } from "vitest";
import { componentTitlePresentation, renderCircuitSvg, simpleDocumentFixture } from "../src/index";

describe("Component title presentation", () => {
  it("keeps the visible title between 12 and 20 screen pixels at each zoom", () => {
    for (const zoom of [.1, .5, 1, 2, 8]) {
      for (const width of [40, 180, 1000]) {
        const title = componentTitlePresentation(width, 200, zoom);
        expect(title.fontSize * zoom).toBeCloseTo(Math.min(20, Math.max(12, width * zoom / 14)));
        expect(title.visible).toBe(true);
      }
    }
  });
  it("hides titles only below 16 projected pixels of node height", () => {
    expect(componentTitlePresentation(180, 100, .159).visible).toBe(false);
    expect(componentTitlePresentation(180, 100, .16).visible).toBe(true);
  });
  it("exports one Component title per instance without changing the document", () => {
    const document = simpleDocumentFixture();
    document.design.instances[1].component_id = document.design.instances[0].component_id;
    document.components[0].label = "Repeated Component";
    const before = JSON.stringify(document);
    const svg = renderCircuitSvg(document);
    const instances = svg.match(/<g data-instance-id="[^"]+">[\s\S]*?<\/g>/g)!;
    expect(instances).toHaveLength(2);
    for (const instance of instances) expect(instance.match(/class="component-label"/g)).toHaveLength(1);
    expect(svg.match(/>Repeated Component<\/text>/g)).toHaveLength(2);
    expect(svg).toContain("Instance producer_0");
    expect(svg).toContain("Instance consumer_0");
    expect(renderCircuitSvg(document)).toBe(svg);
    expect(JSON.stringify(document)).toBe(before);
    document.components[0].label = "";
    expect(renderCircuitSvg(document)).toContain(">producer</text>");
  });
});
