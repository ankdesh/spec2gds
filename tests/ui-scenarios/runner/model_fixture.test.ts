import assert from "node:assert/strict";
import test from "node:test";
import { modelFixture, parseToolOutputs } from "./model_fixture.js";

const a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
async function request(fixture: Awaited<ReturnType<typeof modelFixture>>, messages: any[], tools: any[] = []) {
  const response = await fetch(fixture.url + "/chat/completions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages, tools, stream: true }) });
  assert.equal(response.status, 200);
  const text = await response.text();
  const chunks = text.split("\n").filter(line => line.startsWith("data: {")).map(line => JSON.parse(line.slice(6)));
  const fn = chunks.flatMap(chunk => chunk.choices[0].delta.tool_calls || [])[0]?.function;
  return { text, name: fn?.name, args: fn ? JSON.parse(fn.arguments) : null };
}

test("approval uses the selected older review and preserves distinct ID and title", async () => {
  const fixture = await modelFixture("scenario_123", { title: "Architecture lifecycle" });
  try {
    const value = await request(fixture, [
      { role: "tool", content: JSON.stringify({ architecture_review: { reviewId: a } }) },
      { role: "tool", content: JSON.stringify({ architecture_review: { reviewId: b } }) },
      { role: "user", content: JSON.stringify({ kind: "architecture_decision", architecture_review_id: a, decision: "approved", feedback: "" }) },
    ]);
    assert.equal(value.name, "prepare_spec_document_creation");
    assert.equal(value.args.architecture_review_id, a);
    assert.equal(value.args.document_id, "scenario_123");
    assert.equal(value.args.title, "Architecture lifecycle");
  } finally { await fixture.close(); }
});

test("malformed output is recorded and ends without retry or proposal submission", async () => {
  const fixture = await modelFixture("scenario_123");
  try {
    const messages = [
      { role: "user", content: "Request" },
      { role: "assistant", tool_calls: [{ id: "call", function: { name: "prepare_spec_proposal" } }] },
      { role: "tool", tool_call_id: "call", content: '{"success":true (Omitted bytes)' },
    ];
    const value = await request(fixture, messages);
    assert.equal(value.name, undefined);
    assert.match(value.text, /Malformed structured output from prepare_spec_proposal/);
    assert.equal(fixture.failures.length, 1);
    assert.equal(fixture.requests.length, 1);
  } finally { await fixture.close(); }
});

test("a generic success flag is not a proposal completion receipt", () => {
  const call = { role: "assistant", tool_calls: [{ id: "p", function: { name: "prepare_spec_proposal" } }] };
  assert.throws(() => parseToolOutputs([call, { role: "tool", tool_call_id: "p", content: '{"success":true}' }]), /Missing proposal outcome/);
  assert.equal(parseToolOutputs([call, { role: "tool", tool_call_id: "p", content: '{"success":true,"proposal_id":"saved","state":"ready"}' }])[0].proposal_id, "saved");
});

test("a bounded pending receipt stops generation without claiming that it was saved", async () => {
  const fixture = await modelFixture("scenario_123");
  try {
    const value = await request(fixture, [
      { role: "user", content: JSON.stringify({ kind: "architecture_decision", architecture_review_id: a, decision: "approved", feedback: "" }) },
      { role: "assistant", tool_calls: [{ id: "context", function: { name: "get_bound_context" } }, { id: "proposal", function: { name: "prepare_spec_proposal" } }] },
      { role: "tool", tool_call_id: "context", content: JSON.stringify({ authoritative_context: { document_id: "scenario_123", source_revision_hash: "r", records: [], incomplete: false } }) },
      { role: "tool", tool_call_id: "proposal", content: JSON.stringify({ success: true, proposal_id: "p", state: "ready" }) },
    ], [{ function: { name: "get_bound_context" } }]);
    assert.equal(value.name, undefined);
    assert.match(value.text, /ready for review/);
    assert.ok(!value.text.includes("Saved refinement"));
    assert.deepEqual(fixture.failures, []);
  } finally { await fixture.close(); }
});
