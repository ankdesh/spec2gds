import { describe, expect, it } from "vitest";
import {
  simpleDocumentFixture,
  type CircuitOperationBatch,
  type CircuitProposal,
} from "@spec2gds/circuit-core";
import { MemoryCircuitDesignerBackend } from "../src/index";

describe("memory circuit backend", () => {
  it("commits atomically, guards revisions, and replays request ids", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    const snapshot = await backend.get("fixture_simple");
    const batch: CircuitOperationBatch = {
      request_id: "rename_1",
      expected_revision: snapshot.revision,
      operations: [{
        operation_id: "rename_instance",
        type: "update_instance",
        instance: {
          ...snapshot.document.design.instances[0],
          label: "Renamed producer",
        },
      }],
    };
    const committed = await backend.commit("fixture_simple", batch);
    expect(committed.status).toBe("accepted");
    expect(committed.snapshot?.revision).toBe("2");
    expect((await backend.commit("fixture_simple", batch)).snapshot?.revision).toBe("2");
    expect((await backend.preview("fixture_simple", { ...batch, request_id: "other" })).status).toBe("conflict");
  });

  it("allows a draft owner to save and rejects other commits while locked", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    const lease = await backend.acquireLease("fixture_simple", "canvas");
    const snapshot = await backend.get("fixture_simple");
    const batch: CircuitOperationBatch = {
      request_id: "move_1",
      expected_revision: snapshot.revision,
      operations: [{
        operation_id: "move",
        type: "set_instance_geometry",
        instance_id: "producer_0",
        geometry: { x: 40, y: 80, width: 180, height: 100 },
      }],
    };
    expect((await backend.commit("fixture_simple", batch)).status).toBe("locked");
    expect((await backend.commit("fixture_simple", batch, lease.lease_id)).status).toBe("accepted");
    await backend.releaseLease("fixture_simple", lease.lease_id);
  });

  it("marks proposals stale and deletes them after a decision", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    const snapshot = await backend.get("fixture_simple");
    const proposal: CircuitProposal = {
      proposal_id: "proposal_1",
      document_id: "fixture_simple",
      base_revision: snapshot.revision,
      title: "Move producer",
      summary: "Move the producer.",
      status: "pending",
      batch: {
        request_id: "proposal_batch_1",
        expected_revision: snapshot.revision,
        operations: [{
          operation_id: "proposal_move",
          type: "set_instance_geometry",
          instance_id: "producer_0",
          geometry: { x: 100, y: 100, width: 180, height: 100 },
        }],
      },
      diagnostics: [],
      diff: { added: [], removed: [], changed: [], connections_changed: [] },
      created_at: new Date(0).toISOString(),
    };
    await backend.submitProposal(proposal);
    expect(await backend.listProposals("fixture_simple")).toHaveLength(1);
    expect((await backend.decideProposal("fixture_simple", "proposal_1", "accept"))?.status).toBe("accepted");
    expect(await backend.listProposals("fixture_simple")).toHaveLength(0);
  });

  it("exports portable JSON and deterministic SVG", async () => {
    const backend = new MemoryCircuitDesignerBackend({ documents: [simpleDocumentFixture()] });
    const json = await backend.export("fixture_simple", { format: "json" });
    const svg = await backend.export("fixture_simple", { format: "svg" });
    expect(String(json.data)).toContain('"protocol_version": "circuit-designer.v1"');
    expect(String(svg.data)).toContain("<svg");
    expect(String(svg.data)).toContain('data-instance-id="producer_0"');
  });

  it("expires and reacquires whole-document leases", async () => {
    let current = new Date("2026-01-01T00:00:00.000Z");
    const backend = new MemoryCircuitDesignerBackend({
      documents: [simpleDocumentFixture()],
      now: () => current,
    });
    const first = await backend.acquireLease("fixture_simple", "first", 1);
    expect((await backend.getLease("fixture_simple"))?.lease_id).toBe(first.lease_id);
    current = new Date("2026-01-01T00:00:02.000Z");
    expect(await backend.getLease("fixture_simple")).toBeNull();
    const second = await backend.acquireLease("fixture_simple", "second", 1);
    expect(second.owner_id).toBe("second");
    expect(second.lease_id).not.toBe(first.lease_id);
  });
});
