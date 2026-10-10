import assert from "node:assert/strict";
import test from "node:test";
import { rtlSizingFeedback } from "../src/rtl-authoring-feedback.js";

for (const width of [5, 9, 14]) test(`compiler sizing feedback uses the actual ${width}-bit target`, () => {
  const artifact = { operations: [{ type: "create_entity", ports: [{ name: "a", direction: "in" }, { name: "cin", direction: "in" }, { name: "cout", direction: "out" }] }] };
  const before = structuredClone(artifact);
  const feedback = rtlSizingFeedback([`Operator ADD expects ${width} bits on the RHS, but RHS's VARREF 'cin' generates 1 bits.`], artifact);
  assert.ok(feedback.includes(`${width}'(cin)`));
  assert.ok(!feedback.includes(`${width}'(cout)`));
  assert.deepEqual(artifact, before);
  assert.equal(rtlSizingFeedback(["syntax error"], artifact), "");
});
