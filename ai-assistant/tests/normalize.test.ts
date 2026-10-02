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

test("fills empty create-entity instances and compacts comparator wire ranges", () => {
  const [component] = normalizeSpecOperations([{ type: "create_entity", kind: "component", name: "comparator_3bit",
    ports: [
      { name: "A", family: "wire", direction: "in", range: "[2:0]" },
      { name: "B", family: "wire", direction: "in", range: "2:0" },
      { name: "A_equal", family: "wire", direction: "out", range: "[0:0]" },
    ] }]);
  assert.deepEqual(component?.instances, []);
  assert.deepEqual((component?.ports as Array<Record<string, unknown>>).map(port => port.range), ["2:0", "2:0", "0:0"]);
  const [design] = normalizeSpecOperations([{ type: "create_entity", kind: "design", name: "top" }]);
  assert.deepEqual(design?.instances, []);
  const [populated] = normalizeSpecOperations([{ type: "create_entity", kind: "design", name: "system",
    instances: [{ name: "u1", component_vlnv: "spec2gds.local:work:comparator_3bit:1.0" }] }]);
  assert.equal((populated?.instances as unknown[]).length, 1);
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

test("cleans SystemVerilog code blocks and unwraps module declarations", () => {
  const [withFences] = normalizeSpecOperations([{
    type: "create_entity",
    kind: "component",
    name: "adder",
    systemverilog: "```verilog\nassign {cout, sum} = a + b + cin;\n```",
  }]);
  assert.equal(withFences?.systemverilog, "assign {cout, sum} = a + b + cin;");

  const [wrapped] = normalizeSpecOperations([{
    type: "create_entity",
    kind: "component",
    name: "adder",
    systemverilog: "module adder_8bit(input [7:0] a, b, input cin, output [7:0] sum, output cout);\n  assign {cout, sum} = a + b + cin;\nendmodule",
  }]);
  assert.equal(wrapped?.systemverilog, "assign {cout, sum} = a + b + cin;");

  const [sectionOp] = normalizeSpecOperations([{
    type: "upsert_entity_section",
    owner: { document_id: "doc", entity_id: "c1", entity_kind: "component" },
    section_type: "sv",
    payload: { content: "```systemverilog\n`include \"unused.vh\"\nalways_comb sum = a + b;\n```" },
  }]);
  assert.equal((sectionOp?.payload as Record<string, unknown>).content, "always_comb sum = a + b;");
});

