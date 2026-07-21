import { describe, expect, test } from "vitest";
import { mixedFixture, validateGraph, type CommandBatch } from "@spec2gds/circuit-core";
import { LocalCircuitDesignerApi } from "../src/index";

async function editor() {
  const api = new LocalCircuitDesignerApi(mixedFixture());
  const lease = await api.acquireLease("test-ui", "human");
  return { api, lease };
}

describe("standalone circuit API", () => {
  test("has no server dependency and enables local editing", async () => {
    const api = new LocalCircuitDesignerApi(mixedFixture());
    const graph = await api.getGraph("mixed");
    expect(graph.capabilities?.edit_topology).toBe(true);
    expect((await api.getCatalog()).designs).toHaveLength(1);
  });

  test("applies revision-guarded commands and supports undo", async () => {
    const { api, lease } = await editor();
    const graph = await api.getGraph("mixed");
    const batch: CommandBatch = {
      batch_id: "rename",
      expected_source_revision_hash: graph.source_revision_hash,
      commands: [{ type: "rename_net", command_id: "rename", design_id: "mixed", net_id: "irq", name: "interrupt" }],
    };
    const applied = await api.apply(batch, lease.lease_id);
    expect(applied.candidate?.nets.find((net) => net.id === "irq")?.label).toBe("interrupt");
    expect((await api.getHistory()).can_undo).toBe(true);
    expect((await api.undo(lease.lease_id, "mixed")).graph.nets.find((net) => net.id === "irq")?.label).toBe("irq");
  });

  test("rejects stale revisions without changing the graph", async () => {
    const { api, lease } = await editor();
    const result = await api.apply({
      batch_id: "stale",
      expected_source_revision_hash: "stale:0",
      commands: [{ type: "set_layout_direction", command_id: "direction", design_id: "mixed", direction: "DOWN" }],
    }, lease.lease_id);
    expect(result.candidate).toBeUndefined();
    expect(result.diagnostics[0].code).toBe("revision_conflict");
    expect((await api.getGraph("mixed")).layout?.direction).not.toBe("DOWN");
  });

  test("keeps exclusive local human and agent leases", async () => {
    const api = new LocalCircuitDesignerApi(mixedFixture());
    await api.acquireLease("human", "human");
    await expect(api.acquireLease("assistant", "agent")).rejects.toMatchObject({ status: 409 });
  });

  test("creates a minimal component, port, and interconnect through commands", async () => {
    const { api, lease } = await editor();
    const graph = await api.getGraph("mixed");
    const result = await api.apply({
      batch_id: "draw_minimal_circuit",
      expected_source_revision_hash: graph.source_revision_hash,
      commands: [
        { type: "add_instance", command_id: "component", design_id: "mixed", node_id: "local_node", component_id: "local_component", name: "scratch" },
        { type: "add_terminal", command_id: "port", design_id: "mixed", node_id: "local_node", terminal_id: "local_node:port:data", name: "data", kind: "port", direction: "in" },
        { type: "create_net", command_id: "net", design_id: "mixed", net_id: "local_net", name: "scratch_data", kind: "ad_hoc", terminal_ids: ["peripheral_0:port:irq", "local_node:port:data"] },
      ],
    }, lease.lease_id);

    expect(result.diagnostics).toEqual([]);
    expect(result.candidate?.components.some((item) => item.id === "local_component")).toBe(true);
    expect(result.candidate?.terminals.some((item) => item.id === "local_node:port:data")).toBe(true);
    expect(validateGraph(result.candidate).valid).toBe(true);
  });

  test("round-trips locked route constraints through apply, export, and undo", async () => {
    const { api, lease } = await editor();
    const graph = await api.getGraph("mixed");
    const route = {
      vertices: [
        { id: "irq-source", kind: "endpoint" as const, terminal_id: "peripheral_0:port:irq", point: { x: 0, y: 0 } },
        { id: "irq-target", kind: "endpoint" as const, terminal_id: "cpu_0:port:irq", point: { x: 100, y: 0 } },
      ],
      segments: [{ id: "irq-trunk", from_vertex: "irq-source", to_vertex: "irq-target", locked: true }],
    };
    const result = await api.apply({
      batch_id: "manual_route",
      expected_source_revision_hash: graph.source_revision_hash,
      commands: [{ type: "set_net_route", command_id: "route", design_id: "mixed", net_id: "irq", route }],
    }, lease.lease_id);
    expect(result.diagnostics).toEqual([]);
    expect(api.exportGraph().layout?.net_routes?.irq.segments[0]).toMatchObject({ id: "irq-trunk", locked: true });
    expect((await api.undo(lease.lease_id, "mixed")).graph.layout?.net_routes?.irq).toBeUndefined();
  });

  test("rejects malformed non-orthogonal routes during preview and apply", async () => {
    const { api, lease } = await editor();
    const graph = await api.getGraph("mixed");
    const batch: CommandBatch = {
      batch_id: "diagonal",
      expected_source_revision_hash: graph.source_revision_hash,
      commands: [{
        type: "set_net_route", command_id: "diagonal", design_id: "mixed", net_id: "irq",
        route: {
          vertices: [
            { id: "a", kind: "endpoint", terminal_id: "peripheral_0:port:irq", point: { x: 0, y: 0 } },
            { id: "b", kind: "endpoint", terminal_id: "cpu_0:port:irq", point: { x: 20, y: 20 } },
          ],
          segments: [{ id: "bad", from_vertex: "a", to_vertex: "b" }],
        },
      }],
    };
    expect((await api.preview(batch)).diagnostics[0].message).toContain("not orthogonal");
    expect((await api.apply(batch, lease.lease_id)).candidate).toBeNull();
  });

  test("locks and restores automatic terminal placement through the common command API", async () => {
    const { api, lease } = await editor();
    let graph = await api.getGraph("mixed");
    const placed = await api.apply({
      batch_id: "place_port", expected_source_revision_hash: graph.source_revision_hash,
      commands: [{ type: "set_terminal_placement", command_id: "place", design_id: "mixed", terminal_id: "cpu_0:port:irq", placement: { side: "NORTH", order: 2, locked: true } }],
    }, lease.lease_id);
    expect(placed.candidate?.layout?.terminal_placements?.["cpu_0:port:irq"]).toEqual({ side: "NORTH", order: 2, locked: true });
    graph = placed.candidate!;
    const automatic = await api.apply({
      batch_id: "automatic_port", expected_source_revision_hash: graph.source_revision_hash,
      commands: [{ type: "set_terminal_placement", command_id: "automatic", design_id: "mixed", terminal_id: "cpu_0:port:irq", placement: null }],
    }, lease.lease_id);
    expect(automatic.candidate?.layout?.terminal_placements?.["cpu_0:port:irq"]).toBeUndefined();
  });
});
