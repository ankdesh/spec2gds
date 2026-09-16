import assert from "node:assert/strict";
import test from "node:test";
import { normalizeCircuitOperations, normalizeSpecOperations } from "../src/normalize.js";

test("normalizes Spec maps, clear fields, and server-owned identities", () => {
  const [operation] = normalizeSpecOperations([{
    type: "upsert_narrative_block",
    block: { id: "intro", options: [{ key: "tone", value: "brief" }], children: [] },
  }]);
  assert.match(String(operation?.operation_id), /^operation_1_/);
  assert.deepEqual((operation?.block as Record<string, unknown>).options, { tone: "brief" });

  const [created] = normalizeSpecOperations([{ type: "create_entity", kind: "component", name: "alu core", entity_id: "model_owned", instances: [] }]);
  assert.match(String(created?.entity_id), /^component_alu_core_/);
  assert.notEqual(created?.entity_id, "model_owned");

  const [metadata] = normalizeSpecOperations([{ type: "set_entity_metadata", clear_fields: ["description"] }]);
  assert.equal(metadata?.description, null);
  assert.equal("clear_fields" in metadata!, false);
});

test("normalizes Circuit list-form maps and rejects duplicate keys", () => {
  const [operation] = normalizeCircuitOperations([{
    type: "add_instance",
    instance: { id: "u1", parameter_values: [{ name: "WIDTH", value: 32 }] },
  }]);
  assert.deepEqual((operation?.instance as Record<string, unknown>).parameter_values, { WIDTH: 32 });
  assert.throws(() => normalizeCircuitOperations([{
    type: "add_instance",
    instance: { parameter_values: [{ name: "WIDTH", value: 8 }, { name: "WIDTH", value: 16 }] },
  }]), /Duplicate map entry/);
});
