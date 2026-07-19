import { describe, expect, it } from "vitest";

import { connectedNodeIds, createCommandBatch, fixtureCatalog, fixtures, validateCatalog, validateGraph } from "../src/index";

describe("generic circuit core", () => {
  it("validates every deterministic fixture", () => {
    for (const build of Object.values(fixtures)) {
      const result = validateGraph(build());
      expect(result.errors, JSON.stringify(result.errors, null, 2)).toEqual([]);
      expect(result.valid).toBe(true);
    }
  });

  it("queries connected nodes without source-format knowledge", () => {
    expect(connectedNodeIds(fixtures.hyperedge(), "source_0")).toEqual(["sink_0", "sink_1", "sink_2"]);
  });

  it("validates a design catalog independently of graph payloads", () => {
    expect(validateCatalog(fixtureCatalog())).toEqual({ valid: true, errors: [] });
  });

  it("builds a revision-guarded command batch", () => {
    const graph = fixtures.simple();
    const batch = createCommandBatch("batch_1", graph.source_revision_hash, [
      { command_id: "direction_1", design_id: graph.design.id, type: "set_layout_direction", direction: "DOWN" },
    ]);
    expect(batch.commands[0].type).toBe("set_layout_direction");
  });
});
