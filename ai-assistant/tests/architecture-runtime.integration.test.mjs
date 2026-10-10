/** Architecture phases use a single typed result and a correlated flow wait. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ToolCallId } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { ProductState } from '../lib/state.js';
import { boot } from './support/event-runtime.mjs';
const counter = {
  title: '16-bit counter', components: [{ name: 'counter', purpose: 'Synchronous counter' }], designs: [],
  interfaces: [{ component: 'counter', ports: [{ name: 'clk', direction: 'in', width: 1 }, { name: 'count', direction: 'out', width: 16 }] }],
  clocks_resets: ['Rising-edge clk'], decomposition_rationale: 'One leaf.', assumptions: ['Wrap modulo 65536.'],
  open_questions: [], concrete_configuration: { width: 16 },
};
for (const valid of [false, true]) test(`flow architecture ${valid ? 'waits for a decision' : 'fails invalid content without a correction request'}`, { timeout: 30000 }, async () => {
  const directory=await mkdtemp(join(tmpdir(),'architecture-flow-')); let runtime;
  try {
    runtime=await boot(directory,'http://127.0.0.1:9',{},true);
    const source=(await runtime.ctx.agents.create({sessionId:SessionId('source'),agentOptions:{provider:'mock',model:'mock'},meta:{agentPreset:'focused'}})).agent;
    runtime.adapter.stream=async function* (options) {
      this.requests.push(options); assert.deepEqual(options.tools.map(tool=>tool.name),['structured_output']);
      const value=valid ? counter : {...counter,components:[{component:'counter'}]};
      yield {type:'block-start',index:0,blockType:'tool-call'};
      yield {type:'block-end',index:0,block:{type:'tool-call',id:ToolCallId('architecture-result'),name:'structured_output',arguments:JSON.stringify(value)}};
      yield {type:'usage',usage:{inputTokens:100,outputTokens:20}}; yield {type:'finish',reason:{kind:'tool-calls'}};
    };
    const accepted=await runtime.api('/flow-runs/start',{sessionId:'source',toolName:'flow_create_spec_with_component',inputs:{title:'Counter Spec',request:'Create a counter Component in a new Spec.'},requestId:'counter'});
    assert.equal(accepted.status,202,JSON.stringify(accepted));
    const execution=await runtime.ctx.flows.settled(accepted.value.flow.id);
    assert.equal(execution.status,valid?'waiting':'failed',execution.error); assert.equal(runtime.adapter.requests.length,1);
    assert.equal(execution.usage.requests,1); assert.equal(source.ctx.tools.get('prepare_architecture_review'),undefined);
    const state=new ProductState(join(directory,'assistant.sqlite3'));
    try {
      assert.equal(state.database.prepare('SELECT count(*) AS count FROM source_creation_requests').get().count,0);
      assert.equal(state.listArchitectureReviews().length,valid?1:0);
      if(valid) {
        assert.equal(execution.pending.request.kind,'architecture');
        assert.equal((await runtime.api('/architecture-reviews/'+execution.pending.request.review_id+'/continue',{sessionId:'source'})).status,404);
        assert.equal((await runtime.api('/architecture-reviews/'+execution.pending.request.review_id+'/cancel',{sessionId:'source',flowRevision:execution.revision})).status,200);
      }
    } finally {state.close();}
  } finally {if(runtime)await runtime.ctx.fiber.dispose(); await rm(directory,{recursive:true,force:true});}
});
