import assert from "node:assert/strict";
import test from "node:test";
import { approvedComponentInterface, componentFlowOperations } from "../src/spec-flows.js";

const ports = [{ name: "a", direction: "in", width: 8 }, { name: "sum", direction: "out", width: 9 }];
const plan = { components: [{ name: "ApprovedAdder" }], designs: [], interfaces: [{ component: "ApprovedAdder", ports }] };
const draft = { name: "ApprovedAdder", ports, description: "Retains the carry.", systemverilog: "assign sum = {1'b0, a};" };

test("authoring receives the exact approved Component interface without mutable aliases", () => {
  const contract = approvedComponentInterface(plan);
  assert.deepEqual(contract, { name: "ApprovedAdder", ports });
  contract.ports[0].width = 1;
  assert.equal(ports[0].width, 8);
  assert.throws(() => approvedComponentInterface({ ...plan, interfaces: [] }), /concrete interface/);
  assert.throws(() => approvedComponentInterface({ ...plan, interfaces: [...plan.interfaces, ...plan.interfaces] }), /concrete interface/);
});

test("a draft cannot rename the approved Component or change approved port widths", () => {
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, name: "OtherAdder" }, "request"), /exactly.*ApprovedAdder/);
  assert.throws(() => componentFlowOperations("doc", plan, { ...draft, ports: [{ ...ports[0], width: 1 }, ports[1]] }, "request"), /approved concrete configuration/);
  const operations = componentFlowOperations("doc", plan, draft, "request");
  assert.equal(operations[0].name, "ApprovedAdder");
  assert.equal(operations[0].systemverilog, draft.systemverilog);
});
