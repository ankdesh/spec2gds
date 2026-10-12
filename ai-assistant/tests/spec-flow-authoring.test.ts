import assert from "node:assert/strict";
import test from "node:test";
import { approvedComponentInterface, componentFlowOperations } from "../src/spec-flows.js";

const ports = [{ name: "a", direction: "in", range: "7:0", description: "Port purpose" }, { name: "sum", direction: "out", range: "8:0", description: "Port purpose" }];
const plan = { components: [{ name: "ApprovedAdder" }], designs: [], interfaces: [{ component: "ApprovedAdder", ports, parameters: [], constant_context: "" }] };
const draft = { name: "ApprovedAdder", ports, parameters: [], description: "Retains the carry.", systemverilog: "assign sum = {1'b0, a};" };

test("authoring receives the exact approved Component interface without mutable aliases", () => {
  const contract = approvedComponentInterface(plan);
  assert.deepEqual(contract, { name: "ApprovedAdder", ports, parameters: [], constant_context: "" });
  contract.ports[0].range = null;
  assert.equal(ports[0].range, "7:0");
  assert.throws(() => approvedComponentInterface({ ...plan, interfaces: [] }), /exact interface/);
  assert.throws(() => approvedComponentInterface({ ...plan, interfaces: [...plan.interfaces, ...plan.interfaces] }), /exact interface/);
});

test("a draft cannot rename the approved Component or change approved port widths", () => {
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, name: "OtherAdder" }, "request"), /exactly.*ApprovedAdder/);
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, ports: [{ ...ports[0], range: "0:7" }, ports[1]] }, "request"), /approved exact interface/);
  const operations = componentFlowOperations("doc", plan, draft, "request");
  assert.equal(operations[0].name, "ApprovedAdder");
  assert.equal(operations[0].systemverilog, draft.systemverilog);
});

test("equal-width ranges cannot replace the approved bounds or direction", () => {
  const ports = [{ name: "A", direction: "in", range: "4:1", description: "First operand" }];
  const plan = { components: [{ name: "offset" }], designs: [], interfaces: [{ component: "offset", ports, parameters: [], constant_context: "" }] };
  const draft = { name: "offset", ports, parameters: [], description: "Offset interface", systemverilog: "wire unused_A = &A;" };
  const operations = componentFlowOperations("doc", plan, draft, "offset");
  assert.deepEqual((operations[0].ports as any[])[0], { ...ports[0], family: "wire" });
  for (const range of ["3:0", "1:4"]) assert.throws(() => componentFlowOperations("doc", plan, { ...draft, ports: [{ ...ports[0], range }] }, "offset"), /approved exact interface/);
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, ports: [{ ...ports[0], name: "a" }] }, "offset"), /approved exact interface/);
});

test("stored parameters and constant dependencies are copied into one atomic batch", () => {
  const ports = [{ name: "A", direction: "in", range: "LAST:BASE", description: "Operand" }];
  const parameters = [{ name: "WIDTH", rtl_type: "int unsigned", value: "4", description: "Operand width" }];
  const constant_context = "localparam int BASE=1, LAST=WIDTH;";
  const plan = { components: [{ name: "parameterized" }], designs: [], interfaces: [{ component: "parameterized", ports, parameters, constant_context }] };
  const draft = { name: "parameterized", ports, parameters, description: "Parameterized", systemverilog: "wire unused_A = &A;" };
  const operations = componentFlowOperations("doc", plan, draft, "p");
  assert.equal(operations[0].systemverilog, constant_context + "\n" + draft.systemverilog);
  assert.deepEqual(operations.find(operation => operation.type === "upsert_parameter")?.parameter, parameters[0]);
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, parameters: [{ ...parameters[0], value: "8" }] }, "p"), /approved exact interface/);
});

test("published flow definitions pass the real Harness schema and instruction loader", async () => {
  const { readFileSync, readdirSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const { join } = await import("node:path");
  const { parseFlowYaml } = await import("@deepseek-ai/dsh-flow-yaml");
  const root = fileURLToPath(new URL("../profile/catalog/flows", import.meta.url));
  for (const file of readdirSync(root).filter(file => file.endsWith(".yaml"))) {
    const definition = parseFlowYaml(readFileSync(join(root, file), "utf8"), file, 1_000_000,
      instruction => readFileSync(join(root, instruction), "utf8"));
    assert.equal(definition.version, "3.0.0");
  }
});

test("the published wire-edit prompt example satisfies the current service schema", async () => {
  const { readFileSync } = await import("node:fs");
  const { parseServiceOperationContract, validateServiceOperations } = await import("../src/service-operation-schema.js");
  const text = readFileSync(new URL("../profile/catalog/flows/prompts/edit.md", import.meta.url), "utf8");
  const port = JSON.parse(text.match(/port object has this shape: (\{[^\n]+\})\./)![1]);
  const contract = parseServiceOperationContract(JSON.parse(readFileSync(new URL("./fixtures/spec-document-operation-contract.json", import.meta.url), "utf8")));
  assert.doesNotThrow(() => validateServiceOperations(contract, [{ operation_id: "range", type: "upsert_component_port", component: { document_id: "doc", entity_kind: "component", entity_id: "component" }, port }]));
});

test("cosmetic range brackets cannot cause an approved creation to fail", () => {
  const ports = [{ name: "A", direction: "in", range: "[4:1]", description: "Operand" }];
  const plan = { components: [{ name: "offset" }], designs: [], interfaces: [{ component: "offset", ports, parameters: [], constant_context: "" }] };
  const draft = { name: "offset", ports: [{ ...ports[0], range: "4:1" }], parameters: [], description: "Offset", systemverilog: "wire unused_A = &A;" };
  const operations = componentFlowOperations("doc", plan, draft, "offset");
  assert.equal((operations[0].ports as any[])[0].range, "[4:1]");
});

test("the content prompt keeps interface constants in host context rather than a new draft field", async () => {
  const { readFileSync } = await import("node:fs");
  const prompt = readFileSync(new URL("../profile/catalog/flows/prompts/component.md", import.meta.url), "utf8");
  assert.match(prompt, /Do not return a constant_context field/);
  assert.ok(!prompt.includes("in constant_context."));
});
