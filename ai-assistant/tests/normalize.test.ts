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

test("lossless formatting rejects structures or directives that cannot be normalized safely",()=>{
  assert.throws(()=>normalizeSpecOperations([{type:"create_entity",kind:"component",name:"x",instances:[{name:"child",component_vlnv:"v:l:c:1"}]}]),/internal design/);
  for(const body of ["module x; assign y=0; endmodule",'`include "external.sv"', '`line 1 "external.sv" 0', 'assign q=a; `include "external.sv"', 'assign q=a; `line 1 "external.sv" 0']) {
    assert.throws(()=>normalizeSpecOperations([{type:"create_entity",kind:"component",name:"x",systemverilog:body}]),/module-body|directive/);
  }
  const [created]=normalizeSpecOperations([{type:"create_entity",kind:"component",name:"x",ports:[{name:"a",direction:"in",range:"[ 7 : 0 ]"}],systemverilog:"```sv\n// module is a comment\nassign q=a;\n```"}],"proposal");
  assert.equal((created!.ports as any[])[0].family,"wire");
  assert.equal((created!.ports as any[])[0].range,"7:0");
  assert.equal(created!.systemverilog,"// module is a comment\nassign q=a;");
  const literalBody='// `include "ignored.sv"\ninitial $display("`line 1 is text");';
  assert.equal(normalizeSpecOperations([{type:"create_entity",kind:"component",name:"x",systemverilog:literalBody}])[0]!.systemverilog,literalBody);
});

test("creation aliases remap dependent and narrative references and retain independent proposal identities",()=>{
  const ref={document_id:"doc",entity_id:"local",entity_kind:"component"};
  const operations=[{type:"create_entity",kind:"component",name:"leaf",entity_id:"local"},
    {type:"set_entity_metadata",entity:ref,description:"Purpose"},
    {type:"upsert_narrative_block",block:{block_id:"r",entity_refs:[ref],children:[{entity_refs:[ref]}]}}];
  const a=normalizeSpecOperations(operations,"first"), retry=normalizeSpecOperations(operations,"first"),b=normalizeSpecOperations(operations,"second");
  assert.deepEqual(a,retry); assert.notEqual(a[0]!.entity_id,b[0]!.entity_id);
  assert.equal((a[1]!.entity as any).entity_id,a[0]!.entity_id);
  assert.equal((a[2]!.block as any).children[0].entity_refs[0].entity_id,a[0]!.entity_id);
  assert.equal(ref.entity_id,"local");
  assert.throws(()=>normalizeSpecOperations([...operations,{type:"create_entity",kind:"component",name:"other",entity_id:"local"}],"first"),/Duplicate creation alias/);
});

test("creation operation IDs resolve partial bound references without rewriting another document", () => {
  const operations = [
    { type: "create_entity", kind: "component", operation_id: "create_counter", name: "up_down_counter", entry_design: false },
    { type: "set_entity_metadata", operation_id: "describe_counter",
      entity: { entity_id: "create_counter", entity_kind: "component" }, description: "Synchronous counter." },
    { type: "set_entity_metadata", operation_id: "foreign",
      entity: { document_id: "other", entity_id: "create_counter", entity_kind: "component" }, description: "Another document." },
  ];
  const original = structuredClone(operations);
  const first = normalizeSpecOperations(operations, "proposal", "bound");
  assert.deepEqual(first, normalizeSpecOperations(operations, "proposal", "bound"));
  assert.equal((first[1]!.entity as any).entity_id, first[0]!.entity_id);
  assert.equal((first[1]!.entity as any).document_id, "bound");
  assert.deepEqual(first[2]!.entity, operations[2]!.entity);
  assert.equal(first[0]!.entry_design, undefined);
  assert.deepEqual(operations, original);
  assert.throws(() => normalizeSpecOperations([...operations,
    { type: "create_entity", kind: "component", name: "other", entity_id: "create_counter" }], "proposal", "bound"), /Duplicate creation alias/);
  assert.throws(() => normalizeSpecOperations([operations[0],
    { ...operations[1], entity: { entity_id: "create_counter", entity_kind: "design" } }], "proposal", "bound"), /different entity kind/);
});


test("authoring failures identify the failing operation and distinguish Design composition from Component behavior", () => {
  assert.throws(() => normalizeSpecOperations([
    { type: "create_entity", kind: "component", name: "adder", systemverilog: "assign sum = a;" },
    { type: "create_entity", kind: "design", name: "wrapper", systemverilog: "module wrapper; endmodule" },
  ]), /Spec operation 2.*design wrapper.*Remove systemverilog/);
  assert.throws(() => normalizeSpecOperations([
    { type: "create_entity", kind: "component", name: "adder", systemverilog: "module adder; endmodule" },
  ]), /Spec operation 1.*component adder.*module-body/);
});


test("initial empty RTL is rejected while explicit interface-only Components remain supported", () => {
  assert.throws(() => normalizeSpecOperations([{ type: "create_entity", kind: "component", name: "adder", systemverilog: "  " }]), /systemverilog is empty/);
  assert.doesNotThrow(() => normalizeSpecOperations([{ type: "create_entity", kind: "component", name: "interface_only" }]));
  assert.doesNotThrow(() => normalizeSpecOperations([{ type: "create_entity", kind: "component", name: "interface_only", systemverilog: null }]));
});


test("conflicting metadata and bus set/clear values cannot silently erase authored values", () => {
  assert.throws(() => normalizeSpecOperations([{ type: "set_entity_metadata", description: "Requested description", clear_fields: ["description"] }]), /Cannot set and clear metadata field description/);
  assert.throws(() => normalizeSpecOperations([{ type: "update_bus_definition", properties: { description: "Requested description", clear_fields: ["description"] } }]), /Cannot set and clear bus field description/);
  const [clear] = normalizeSpecOperations([{ type: "set_entity_metadata", description: null, clear_fields: ["description"] }]);
  assert.equal(clear!.description, null);
});
