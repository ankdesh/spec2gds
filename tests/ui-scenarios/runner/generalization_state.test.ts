import assert from "node:assert/strict";
import test from "node:test";
import { generatedSpecReceipt, selectedEvaluationCases, assertEvaluationCreationFlow, assertEvaluationInterface } from "./generalization_state.js";

const created = { destination: "/tmp/adder.spec", architectureReviewId: "approved-adder", status: "bound",
  serviceDocumentKey: "saved-adder-key", documentId: "saved-adder" };

test("an empty creation or failed hardware flow stops evaluation without waiting for approval", () => {
  assertEvaluationCreationFlow(null, null, null);
  assertEvaluationCreationFlow("spec2gds.create_spec_with_component", "waiting", "");
  assert.throws(() => assertEvaluationCreationFlow("spec2gds.create_empty_spec", "succeeded", ""), /wrong flow/);
  assert.throws(() => assertEvaluationCreationFlow("spec2gds.create_spec_with_component", "failed", "bad widths"), /bad widths/);
});

test("testbench contracts reject reset aliases while accepting approved port order changes", () => {
  const ports = [{ name: "clk", direction: "in", width: 1 }, { name: "reset", direction: "in", width: 1 }];
  const interfaces = ports.map(({ width, ...port }) => ({ ...port, range: null, description: "Control signal" }));
  const plan = { components: [{ name: "pipeline" }], designs: [], interfaces: [{ component: "pipeline", ports: [...interfaces].reverse(), parameters: [], constant_context: "" }] };
  assertEvaluationInterface(plan, ports);
  assert.throws(() => assertEvaluationInterface({ ...plan, interfaces: [{ component: "pipeline", ports: [interfaces[0], { ...interfaces[1], name: "rst" }], parameters: [], constant_context: "" }] }, ports), /testbench contract/);
});

test("evaluation uses the created Spec receipt when another Spec is active", () => {
  const other = { ...created, destination: "/tmp/other.spec", serviceDocumentKey: "active-other-key" };
  assert.equal(generatedSpecReceipt([other, created], "/tmp/adder.spec", "approved-adder"), created);
  assert.equal(generatedSpecReceipt([created], "/tmp/adder.spec", "foreign-review"), null);
  assert.equal(generatedSpecReceipt([{ ...created, status: "pending" }], created.destination, "approved-adder"), null);
});

test("ambiguous receipts and missing Spec identity cannot establish a generated result", () => {
  assert.throws(() => generatedSpecReceipt([created, { ...created }], created.destination, "approved-adder"), /one creation receipt/);
  assert.throws(() => generatedSpecReceipt([{ ...created, serviceDocumentKey: null }], created.destination, "approved-adder"), /exact Spec/);
});


test("selected live cases keep requested order and reject silent partial selection", () => {
  const cases = [{ id: "adder_8" }, { id: "adder_4" }, { id: "adder_13" }];
  assert.deepEqual(selectedEvaluationCases(cases, "adder_4,adder_8,adder_13").map(item => item.id), ["adder_4", "adder_8", "adder_13"]);
  assert.throws(() => selectedEvaluationCases(cases, "adder_8,unknown"), /Unknown/);
  assert.throws(() => selectedEvaluationCases(cases, "adder_8,adder_8"), /Duplicate/);
  assert.throws(() => selectedEvaluationCases(cases, "adder_8,"), /nonempty/);
});

test("evaluation uses checked bounds for constant expressions without requiring literal source ranges", () => {
  const plan = { components: [{ name: "adder" }], designs: [], interfaces: [{ component: "adder", ports: [{ name: "a", direction: "in", range: "WIDTH-1:0" }] }] };
  const elaborations = [{ component: "adder", status: "resolved", ports: [{ name: "a", left: 12, right: 0, width: 13 }] }];
  assertEvaluationInterface(plan, [{ name: "a", direction: "in", width: 13 }], elaborations);
  assert.throws(() => assertEvaluationInterface(plan, [{ name: "a", direction: "in", width: 8 }], elaborations), /testbench contract/);
});
