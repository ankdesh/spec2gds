import { describe, expect, test } from "vitest";
import { projectDocument, validateCircuitDocument } from "@spec2gds/circuit-core";
import { standaloneExamples } from "./examples";
import { graphLayoutKey, matchingLayout } from "./layout-state";

describe("standalone examples", () => {
  test.each(Object.entries(standaloneExamples))("%s satisfies the shared circuit contract", (_id, example) => {
    const document = example.build();
    expect(validateCircuitDocument(document).errors).toEqual([]);
    expect(document.document_id).toMatch(/^standalone_/);
    expect(document.design.id).toBeTruthy();
  });

  test("never applies the previous example's asynchronous layout", () => {
    const subsystem = projectDocument(standaloneExamples.subsystem.build(), "1");
    const datapath = projectDocument(standaloneExamples.datapath.build(), "1");
    const staleLayout = {
      graphKey: graphLayoutKey(subsystem),
      result: { layout: { direction: "RIGHT" as const, node_geometry: {}, net_routes: {}, terminal_placements: {} }, boundary_geometry: {}, elapsed_ms: 1 },
    };

    expect(matchingLayout(subsystem, staleLayout)).toBe(staleLayout.result);
    expect(matchingLayout(datapath, staleLayout)).toBeUndefined();
  });
});
