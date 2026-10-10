import assert from "node:assert/strict";
import test from "node:test";
import { generatedSpecReceipt, selectedEvaluationCases } from "./generalization_state.js";

const created = { destination: "/tmp/adder.spec", architectureReviewId: "approved-adder", status: "bound",
  serviceDocumentKey: "saved-adder-key", documentId: "saved-adder" };

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
