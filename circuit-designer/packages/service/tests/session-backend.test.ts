import { describe, expect, it } from "vitest";
import {
  simpleDocumentFixture,
  type CircuitOperationBatch,
  type CircuitProposalCreateRequest,
} from "@spec2gds/circuit-core";
import { EphemeralCircuitSessionBackend } from "../src/session-backend";

describe("ephemeral circuit session backend", () => {
  it("commits atomically, guards revisions, and replays request ids", async () => {
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
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
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
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
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
    const snapshot = await backend.get("fixture_simple");
    const proposal: CircuitProposalCreateRequest = {
      proposal_id: "proposal_1",
      document_id: "fixture_simple",
      base_revision: snapshot.revision,
      title: "Move producer",
      summary: "Move the producer.",
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
    };
    const saved = await backend.submitProposal(proposal);
    expect(saved.status).toBe("pending");
    expect(saved.created_at).toBeTruthy();
    expect(await backend.listProposals("fixture_simple")).toHaveLength(1);
    expect((await backend.decideProposal("fixture_simple", "proposal_1", "accept"))?.status).toBe("accepted");
    expect(await backend.listProposals("fixture_simple")).toHaveLength(0);
  });

  it("retains a proposal when acceptance is blocked by an edit lease", async () => {
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
    const snapshot = await backend.get("fixture_simple");
    await backend.submitProposal({
      proposal_id: "proposal_locked",
      document_id: "fixture_simple",
      base_revision: snapshot.revision,
      title: "Move producer",
      summary: "Move the producer while another editor has the lease.",
      batch: {
        request_id: "proposal_locked_batch",
        expected_revision: snapshot.revision,
        operations: [{
          operation_id: "proposal_locked_move",
          type: "set_instance_geometry",
          instance_id: "producer_0",
          geometry: { x: 120, y: 100, width: 180, height: 100 },
        }],
      },
    });
    const lease = await backend.acquireLease("fixture_simple", "canvas");
    expect(
      (await backend.decideProposal("fixture_simple", "proposal_locked", "accept"))?.status,
    ).toBe("locked");
    expect(await backend.listProposals("fixture_simple")).toHaveLength(1);
    await backend.releaseLease("fixture_simple", lease.lease_id);
    expect(
      (await backend.decideProposal("fixture_simple", "proposal_locked", "accept"))?.status,
    ).toBe("accepted");
    expect(await backend.listProposals("fixture_simple")).toHaveLength(0);
  });

  it("exports portable JSON, deterministic SVG, and PNG", async () => {
    const backend = new EphemeralCircuitSessionBackend({ documents: [simpleDocumentFixture()] });
    const json = await backend.export("fixture_simple", { format: "json" });
    const svg = await backend.export("fixture_simple", { format: "svg" });
    const png = await backend.export("fixture_simple", { format: "png" });
    expect(json.filename).toBe("fixture_simple.circuit.json");
    expect(String(json.data)).toContain('"protocol_version": "circuit-designer.v1"');
    expect(String(svg.data)).toContain("<svg");
    expect(String(svg.data)).toContain('data-instance-id="producer_0"');
    expect([...png.data as Uint8Array].slice(0, 8)).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  });

  it("expires and reacquires whole-document leases", async () => {
    let current = new Date("2026-01-01T00:00:00.000Z");
    const backend = new EphemeralCircuitSessionBackend({
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
