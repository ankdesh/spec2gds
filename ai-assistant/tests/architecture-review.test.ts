import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { registerArchitectureTool, validateArchitectureOperations } from "../src/architecture-review.js";
import { ProductState } from "../src/state.js";
import { architecturePlan } from "./support/architecture.js";

test("counter review rejects the failed model payload and accepts a concrete interface usable by creation", async () => {
  const root = mkdtempSync(join(tmpdir(), "architecture-counter-"));
  const state = new ProductState(join(root, "state.sqlite3"));
  try {
    let tool: any;
    registerArchitectureTool({ id: "counter", ctx: { tools: { register: value => { tool = value; return () => {}; } } } },
      state, {} as any, () => "Create a 16-bit up/down counter");
    const ports = [{ name: "clk", direction: "in", width: 1 }, { name: "reset", direction: "in", width: 1 },
      { name: "up_down", direction: "in", width: 1 }, { name: "count", direction: "out", width: 16 }];
    const plan = { ...architecturePlan, components: [{ name: "up_down_counter", purpose: "16-bit counter" }],
      designs: [{ name: "counter_design", purpose: "Entry composition" }],
      interfaces: [{ component: "up_down_counter", ports }], concrete_configuration: { width: 16, reset: "synchronous active-high", overflow: "wrap" } };
    await assert.rejects(tool.execute({ ...plan, components: [{ component: "up_down_counter", ports }] }, { callId: "invalid" }), /components\[0\]\.name/);
    await assert.rejects(tool.execute({ ...plan, designs: [{ design: "counter_design" }] }, { callId: "invalid-design" }), /designs\[0\]\.name/);
    await assert.rejects(tool.execute({ ...plan, interfaces: [{ component: "up_down_counter", ports: [{ name: "clk", direction: "input", width: 1 }] }] }, { callId: "invalid-direction" }), /interfaces\[0\]/);
    assert.match((await tool.execute({ ...plan, interfaces: [] }, { callId: "empty-interfaces" })).creation_error, /interfaces must contain/);
    assert.match((await tool.execute({ ...plan, concrete_configuration: {} }, { callId: "empty-config" })).creation_error, /concrete_configuration must contain/);
    assert.match((await tool.execute({ ...plan, interfaces: [{ component: "unknown", ports }] }, { callId: "unknown" })).creation_error, /per named component/);
    assert.match((await tool.execute({ ...plan, interfaces: [{ component: "up_down_counter", ports: [{ name: "count", direction: "out", width: 0 }] }] }, { callId: "zero-width" })).creation_error, /positive integer widths/);
    const result = await tool.execute(plan, { callId: "corrected" });
    assert.equal(result.architecture_review.status, "pending");
    assert.equal(state.architectureReview(result.architecture_review.reviewId)?.originalRequest, "Create a 16-bit up/down counter");
    validateArchitectureOperations(plan, [{ type: "create_entity", kind: "component", name: "up_down_counter",
      ports: ports.map(({ width, ...port }) => ({ ...port, ...(width > 1 ? { range: `${width - 1}:0` } : {}) })) }]);
  } finally { state.close(); rmSync(root, { recursive: true, force: true }); }
});

test("approved creation names and concrete interfaces constrain content", () => {
  const creation = { type: "create_entity", kind: "component", name: "leaf", ports: [{ name: "clk", direction: "in" }] };
  validateArchitectureOperations(architecturePlan, [creation]);
  assert.throws(() => validateArchitectureOperations(architecturePlan, [{ ...creation, name: "unreviewed" }]), /not included/);
  assert.throws(() => validateArchitectureOperations(architecturePlan, [{ ...creation, ports: [{ name: "clk", direction: "in", range: "7:0" }] }]), /width differs/);
});

test("approved review reuse requires the same owner document and fresh revision", () => {
  const root = mkdtempSync(join(tmpdir(), "architecture-binding-"));
  const state = new ProductState(join(root, "state.sqlite3"));
  try {
    const binding = { domain: "spec" as const, serviceBaseUrl: "http://owner", ownerUrl: "http://owner", documentId: "shared-id",
      scope: "document" as const, workspaceKey: "key", workspaceTitle: "Workspace", workspacePath: root,
      workspaceDomain: "spec" as const, workspaceOwnerUrl: "http://owner", workspaceDocumentId: "shared-id" };
    state.createBinding("same", { ...binding, ownerDocumentKey: "package-A" });
    state.createBinding("copy", { ...binding, ownerDocumentKey: "package-B" });
    state.storeArchitecture({ reviewId: "approved", sessionId: "original", callId: "review", status: "pending", plan: architecturePlan,
      ownerDocumentKey: "package-A", documentId: "shared-id", scope: "document", entityId: null, sourceRevision: "sha256:A" });
    state.decideArchitecture("approved", "approved", "");
    assert.equal(state.requireArchitecture("same", "approved", "sha256:A").reviewId, "approved");
    assert.throws(() => state.requireArchitecture("copy", "approved", "sha256:A"), /approval/);
    assert.throws(() => state.requireArchitecture("same", "approved", "sha256:B"), /stale/);
  } finally { state.close(); rmSync(root, { recursive: true, force: true }); }
});

for(const decision of ["approved","revised","cancelled"] as const) test(`architecture ${decision} survives reload and controls content authorization`,async()=>{
  const root=mkdtempSync(join(tmpdir(),"architecture-"));
  let state=new ProductState(join(root,"state.sqlite3"));
  try {
    const tools=new Map<string,any>();
    const agent={id:"source",ctx:{tools:{register:(tool:any)=>{tools.set(tool.name,tool);return()=>{};}}}};
    registerArchitectureTool(agent,state,{} as any,()=>"Create a reusable architecture");
    const first=await tools.get("prepare_architecture_review").execute(architecturePlan,{callId:"call"});
    const id=first.architecture_review.reviewId;
    assert.equal((await tools.get("prepare_architecture_review").execute(architecturePlan,{callId:"call"})).architecture_review.reviewId,id);
    assert.throws(()=>state.requireArchitecture("source",id),/approval/);
    state.decideArchitecture(id,decision,"Feedback");
    state.close(); state=new ProductState(join(root,"state.sqlite3"));
    assert.equal(state.architectureReview(id)?.status,decision);
    assert.throws(()=>state.requireArchitecture("other",id),/approval/);
    if(decision==="approved") {
      assert.equal(state.requireArchitecture("source",id).originalRequest,"Create a reusable architecture");
      const review=state.architectureReview(id)!;
      state.storeArchitecture({...review,destinationSessionId:"destination",destinationSourceRevision:"sha256:new"});
      assert.equal(state.requireArchitecture("destination",id,"sha256:new").reviewId,id);
      assert.throws(()=>state.requireArchitecture("destination",id,"sha256:changed"),/stale/);
    } else assert.throws(()=>state.requireArchitecture("source",id),/approval/);
    assert.throws(()=>state.decideArchitecture(id,decision==="approved"?"cancelled":"approved",""),/already/);
  }finally{state.close();rmSync(root,{recursive:true,force:true});}
});

test("essential questions block approval and revised reviews retain original intent",async()=>{
  const root=mkdtempSync(join(tmpdir(),"architecture-question-"));
  const state=new ProductState(join(root,"state.sqlite3"));
  try {
    const tools=new Map<string,any>(); let request="Create the original specification";
    registerArchitectureTool({id:"source",ctx:{tools:{register:(tool:any)=>{tools.set(tool.name,tool);return()=>{};}}}},state,{} as any,()=>request);
    const first=await tools.get("prepare_architecture_review").execute({...architecturePlan,open_questions:["Which reset polarity?"]},{callId:"first"});
    assert.throws(()=>state.decideArchitecture(first.architecture_review.reviewId,"approved",""),/essential open questions/);
    state.decideArchitecture(first.architecture_review.reviewId,"revised","Use active-low reset");
    request=JSON.stringify({kind:"architecture_decision",architecture_review_id:first.architecture_review.reviewId,decision:"revised",feedback:"Use active-low reset"});
    const second=await tools.get("prepare_architecture_review").execute(architecturePlan,{callId:"second"});
    assert.equal(second.architecture_review.originalRequest,"Create the original specification");
    assert.notEqual(second.architecture_review.reviewId,first.architecture_review.reviewId);
  }finally{state.close();rmSync(root,{recursive:true,force:true});}
});
