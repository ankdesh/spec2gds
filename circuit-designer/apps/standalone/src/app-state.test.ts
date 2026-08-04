import { describe, expect, test } from "vitest";
import { createEmptyCircuitDocument, projectDocument, validateCircuitDocument } from "@spec2gds/circuit-core";
import { assistantCircuitUrl, linkedCircuitDocumentId } from "./launch-state";
import { graphLayoutKey, matchingLayout } from "./layout-state";

describe("standalone app state", () => {
  test("starts from a valid empty document", () => {
    const document = createEmptyCircuitDocument("local_test");
    expect(validateCircuitDocument(document).errors).toEqual([]);
    expect(document.components).toEqual([]);
    expect(document.design.instances).toEqual([]);
  });

  test("never applies a layout computed for another document", () => {
    const first = projectDocument(createEmptyCircuitDocument("local_first"), "1");
    const second = projectDocument(createEmptyCircuitDocument("local_second"), "1");
    const staleLayout = {
      graphKey: graphLayoutKey(first),
      result: { layout: { direction: "RIGHT" as const, node_geometry: {}, net_routes: {}, terminal_placements: {} }, boundary_geometry: {}, elapsed_ms: 1 },
    };

    expect(matchingLayout(first, staleLayout)).toBe(staleLayout.result);
    expect(matchingLayout(second, staleLayout)).toBeUndefined();
  });

  test("recognizes an editor-linked Circuit Designer session URL", () => {
    expect(linkedCircuitDocumentId("?document_id=spec_design_top_1234")).toBe("spec_design_top_1234");
    expect(linkedCircuitDocumentId("?other=value")).toBeUndefined();
  });

  test("builds a directly bound AI Assistant circuit URL", () => {
    expect(assistantCircuitUrl(
      "http://127.0.0.1:4200",
      "http://127.0.0.1:4100/api/circuit-designer/v1",
      "design/top",
    )).toBe(
      "http://127.0.0.1:4200/launch/circuit"
      + "?service_base_url=http%3A%2F%2F127.0.0.1%3A4100%2Fapi%2Fcircuit-designer%2Fv1"
      + "&document_id=design%2Ftop",
    );
  });
});
