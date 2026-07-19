import { describe, expect, test } from "vitest";
import { validateGraph } from "@spec2gds/circuit-core";
import { standaloneExamples } from "./examples";
import { graphLayoutKey, matchingLayout } from "./layout-state";

describe("standalone examples", () => {
  test.each(Object.entries(standaloneExamples))("%s satisfies the shared circuit contract", (_id, example) => {
    const graph = example.build();
    expect(validateGraph(graph).errors).toEqual([]);
    expect(graph.document_id).toMatch(/^standalone_/);
    expect(graph.design.vlnv).toMatch(/^example:standalone:/);
  });

  test("never applies the previous example's asynchronous layout", () => {
    const subsystem = standaloneExamples.subsystem.build();
    const datapath = standaloneExamples.datapath.build();
    const staleLayout = {
      graphKey: graphLayoutKey(subsystem),
      result: { layout: { node_geometry: {}, net_routes: {}, terminal_placements: {} }, boundary_geometry: {}, elapsed_ms: 1 },
    };

    expect(matchingLayout(subsystem, staleLayout)).toBe(staleLayout.result);
    expect(matchingLayout(datapath, staleLayout)).toBeUndefined();
  });
});
