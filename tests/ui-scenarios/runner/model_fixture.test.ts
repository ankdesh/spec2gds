import assert from "node:assert/strict";
import test from "node:test";
import { modelFixture, parseToolOutputs } from "./model_fixture.js";

async function request(fixture: Awaited<ReturnType<typeof modelFixture>>, messages: any[], tools: any[] = []) {
  const response = await fetch(fixture.url + "/chat/completions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages, tools, stream: true }) });
  assert.equal(response.status, 200);
  const text = await response.text();
  const chunks = text.split("\n").filter(line => line.startsWith("data: {")).map(line => JSON.parse(line.slice(6)));
  const fn = chunks.flatMap(chunk => chunk.choices[0].delta.tool_calls || [])[0]?.function;
  return { text, name: fn?.name, args: fn ? JSON.parse(fn.arguments) : null };
}

test("a new Spec request selects its flow with complete inputs",async()=>{
 const fixture=await modelFixture("scenario_123",{title:"Architecture lifecycle"});
 try {const value=await request(fixture,[{role:"user",content:"Create a new timer Spec."}],[{function:{name:"flow_create_spec_with_component"}}]);
 assert.equal(value.name,"flow_create_spec_with_component");assert.equal(value.args.request,"Create a new timer Spec.");assert.equal(value.args.title,"Architecture lifecycle");assert.equal(value.args.architecture_review_id,undefined);
 }finally{await fixture.close();}
});

test("malformed output is recorded and ends without retry or proposal submission", async () => {
  const fixture = await modelFixture("scenario_123");
  try {
    const messages = [
      { role: "user", content: "Request" },
      { role: "assistant", tool_calls: [{ id: "call", function: { name: "prepare_circuit_proposal" } }] },
      { role: "tool", tool_call_id: "call", content: '{"success":true (Omitted bytes)' },
    ];
    const value = await request(fixture, messages);
    assert.equal(value.name, undefined);
    assert.match(value.text, /Malformed structured output from prepare_circuit_proposal/);
    assert.equal(fixture.failures.length, 1);
    assert.equal(fixture.requests.length, 1);
  } finally { await fixture.close(); }
});

test("a generic success flag is not a proposal completion receipt", () => {
  const call = { role: "assistant", tool_calls: [{ id: "p", function: { name: "prepare_circuit_proposal" } }] };
  assert.throws(() => parseToolOutputs([call, { role: "tool", tool_call_id: "p", content: '{"success":true}' }]), /Missing proposal outcome/);
  assert.equal(parseToolOutputs([call, { role: "tool", tool_call_id: "p", content: '{"success":true,"proposal_id":"saved","state":"ready"}' }])[0].proposal_id, "saved");
});

test("flow acceptance stops generation without claiming saved content",async()=>{
 const fixture=await modelFixture("scenario_123");
 try {const value=await request(fixture,[{role:"user",content:"Add timer"},{role:"assistant",tool_calls:[{id:"flow",function:{name:"flow_add_component"}}]},{role:"tool",tool_call_id:"flow",content:JSON.stringify({execution_id:"accepted",revision:1,state:"running"})}],[{function:{name:"flow_add_component"}}]);
 assert.equal(value.name,undefined);assert.match(value.text,/accepted/);assert.ok(!value.text.includes("Saved refinement"));assert.deepEqual(fixture.failures,[]);
 }finally{await fixture.close();}
});
