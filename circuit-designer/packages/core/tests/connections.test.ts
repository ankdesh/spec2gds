import { describe, expect, it } from "vitest";
import { CircuitDraft, ConnectionChoiceRequired, planConnection, sameConnectionEndpoint, simpleDocumentFixture, type NetEndpoint } from "../src/index";

const pin = (instance_id: string): NetEndpoint => ({ kind: "instance", instance_id, terminal_id: "data" });
const options = { operationId: "connect", netId: "new_net", label: "new net" };
function fanoutFixture() {
  const document = simpleDocumentFixture();
  document.design.instances.push({ ...document.design.instances[1], id: "consumer_1", label: "Second sink" });
  return document;
}

describe("manual connection planning", () => {
  it("extends the same net and records one undoable action", () => {
    const document = fanoutFixture();
    const draft = new CircuitDraft(document, "1");
    const operation = planConnection(document, [pin("producer_0"), pin("consumer_1")], options)!;
    expect(operation.type).toBe("connect_endpoint");
    expect(draft.apply(operation).filter(item => item.severity === "error")).toEqual([]);
    expect(draft.document.design.nets).toHaveLength(1);
    expect(draft.document.design.nets[0]).toMatchObject({ id: "data", label: "data" });
    expect(draft.document.design.nets[0].endpoints).toHaveLength(3);
    expect(draft.undo()).toEqual(document);
    expect(draft.redo().design.nets[0].endpoints).toHaveLength(3);
    expect(document.design.nets[0].endpoints).toHaveLength(2);
  });

  it("adds a selected dialog endpoint and treats duplicates as no-ops", () => {
    const document = fanoutFixture();
    expect(planConnection(document, [pin("consumer_1")], { ...options, existingNetId: "data" }))
      .toMatchObject({ type: "connect_endpoint", net_id: "data", endpoint: pin("consumer_1") });
    expect(planConnection(document, [pin("producer_0"), pin("consumer_0")], options)).toBeUndefined();
  });

  it("rejects a second driver and mismatched widths without changing source", () => {
    const document = fanoutFixture();
    document.design.instances.push({ ...document.design.instances[0], id: "producer_1" });
    const before = structuredClone(document);
    expect(() => planConnection(document, [pin("producer_1")], { ...options, existingNetId: "data" })).toThrow(/source/i);
    document.components[1].terminals[0].width = 8;
    expect(() => planConnection(document, [pin("consumer_1")], { ...options, existingNetId: "data" })).toThrow(/width/i);
    document.components[1].terminals[0].width = 1;
    expect(document).toEqual(before);
  });

  it("requires explicit bus-net choice and preserves numeric slices", () => {
    const document = fanoutFixture();
    document.components[0].terminals[0].width = 8;
    document.design.nets[0].endpoints[0].slice = { lsb: 4, width: 1 };
    expect(() => planConnection(document, [pin("producer_0"), pin("consumer_1")], options)).toThrow(ConnectionChoiceRequired);
    expect(planConnection(document, [pin("consumer_1")], { ...options, existingNetId: "data" }))
      .toMatchObject({ type: "connect_endpoint", net_id: "data" });
  });

  it("reproduces scalar-to-bit and independent-offset connections successfully", () => {
    const document = fanoutFixture();
    document.design.nets = [];
    document.components[1].terminals[0].width = 65;
    const endpoints = [pin("producer_0"), { ...pin("consumer_0"), slice: { lsb: 64, width: 1 } }];
    const operation = planConnection(document, endpoints, options)!;
    expect(operation).toMatchObject({ type: "create_net", net: { endpoints } });
    expect(sameConnectionEndpoint(document, pin("producer_0"), { ...pin("producer_0"), slice: { lsb: 0, width: 1 } })).toBe(true);
    expect(() => planConnection(document, [pin("producer_0"), { ...pin("consumer_0"), slice: { lsb: 65, width: 1 } }], options)).toThrow(/exceeds/i);
  });

  it("does not remove locked route geometry when extending a net", () => {
    const document = fanoutFixture();
    const route = { vertices: [{ id: "p", kind: "endpoint" as const, point: { x: 0, y: 0 }, locked: true }], segments: [] };
    expect(() => planConnection(document, [pin("consumer_1")], { ...options, existingNetId: "data", route })).toThrow(/Unlock/);
    expect(document.design.nets[0].endpoints).toHaveLength(2);
  });

  it("does not merge separate nets or reuse an already driven sink", () => {
    const document = fanoutFixture();
    document.design.instances.push({ ...document.design.instances[0], id: "producer_1" });
    document.design.nets.push({ id: "other", label: "other", endpoints: [pin("producer_1"), pin("consumer_1")] });
    expect(() => planConnection(document, [pin("producer_0"), pin("consumer_1")], options)).toThrow(/different nets/);
    expect(() => planConnection(document, [pin("consumer_1")], { ...options, existingNetId: "data" })).toThrow(/more than one net/);
  });
});
