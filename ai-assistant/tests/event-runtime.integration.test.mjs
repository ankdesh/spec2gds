import { serveIntegrationMetadata } from "./support/integration-metadata.mjs";
/** Real Loader, native agents/goals, trusted product catalogs, and HTTP owner integration. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { ProductState } from '../lib/state.js';

import { boot, waitFor } from './support/event-runtime.mjs';
import { approveTimer } from './support/approved-timer.mjs';

for(const preset of ['goal','orchestrated']) test(`${preset} composes native execution with the owner proposal boundary`,{timeout:30000},async()=>{
  const directory=await mkdtemp(join(tmpdir(),'spec2gds-events-integration-'));
  const contract=JSON.parse(await readFile(new URL('./fixtures/spec-document-operation-contract.json',import.meta.url),'utf8'));
  let previews=0,mutations=0,revision='sha256:test';
  const owner=createServer((request,response)=>{
    if (serveIntegrationMetadata(request, response)) return;
    const path=new URL(request.url,'http://localhost').pathname;
    const send=value=>{response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(value));};
    if(path==='/health')return send({status:'ok'});
    if(path==='/assistant/operation-schema')return send(contract);
    if(path==='/assistant/context/document')return send({schema_version:'spec2gds.assistant-context.v1',scope:'document',document_id:'doc-test',source_revision_hash:revision,target:null,writable:{document_operations:['create_entity']},read_only:{existing_entities:true},rendered_context:{document_id:'doc-test',source_revision_hash:revision,target:null,text:'Specification with one ALU.'},available_references:{components:[],designs:[]},diagnostics:[]});
    if(request.method==='POST'&&path==='/assistant/proposals/preview'){previews++;return send({status:'valid',diagnostics:[],diff:[]});}
    if(request.method==='POST'&&path.startsWith('/assistant/submissions/')&&path.endsWith('/decision'))return send({state:'discarded'});
    if(request.method==='POST')mutations++;
    response.writeHead(404);response.end('{}');
  });
  owner.listen(0,'127.0.0.1');await once(owner,'listening');
  const ownerUrl=`http://127.0.0.1:${owner.address().port}`;
  let ctx;
  const previousBinding=process.env.SPEC2GDS_BINDING_JSON;
  try {
    const runtime=await boot(directory,ownerUrl);ctx=runtime.ctx;
    process.env.SPEC2GDS_BINDING_JSON=JSON.stringify({domain:'spec',serviceBaseUrl:ownerUrl,documentId:'doc-test',scope:'document',preset});
    const primary=await ctx.agents.create({sessionId:SessionId(`native-${preset}`),agentOptions:{provider:'mock',model:'mock'},meta:{agentPreset:preset},setup:async(agentCtx)=>{if(preset==='goal')await agentCtx.plugin(await import('@deepseek-ai/dsh-tool-goal'));}});
    approveTimer(directory, String(primary.agent.id));
    if(preset==='goal')ctx.goals.create(primary.agent,{objective:'Prepare a timer proposal.',maxGoalRounds:8});
    primary.agent.followup(createUserMessage({content:[{type:'text',text:'Propose a timer component.'}],source:{kind:'user'}}));
    await waitFor(()=>ctx.eventSystems.get(primary.agent.id)?.events.some(event=>event.type==='review.prepared'));
    await primary.agent.whenIdle();
    const execution=ctx.eventSystems.get(primary.agent.id);
    assert.equal(previews,1);assert.equal(mutations,0);
    assert.equal(execution.mode,preset);
    assert.ok(execution.requests.length>0);
    if(preset==='goal') {
      assert.equal(execution.members.length,1);
      assert.equal(execution.status,'active');
      assert.ok(execution.waits.some(wait=>wait.kind==='review'&&wait.state==='waiting'));
      assert.equal(ctx.goals.get(primary.agent).phase,'blocked');
    } else {
      await waitFor(()=>ctx.eventSystems.get(primary.agent.id).deliveries.every(item=>item.state==='completed'));
      assert.equal(execution.members.length,3);
      assert.ok(execution.events.some(event=>event.type==='analysis.ready'));
      assert.ok(execution.events.some(event=>event.type==='review.ready'));
      for(const member of execution.members.filter(item=>item.id!=='primary')) {
        const agent=ctx.agents.get(member.sessionId);
        assert.equal(agent.ctx.tools.get('prepare_spec_proposal'),undefined);
      }
    }
    const state=new ProductState(join(directory,'assistant.sqlite3'));
    try {
      const review=state.listReviews(primary.agent.id)[0];assert.equal(review.state,'ready');
      const view=await runtime.api(`/bindings/${primary.agent.id}/execution`);assert.equal(view.status,200);
      assert.equal(view.value.goal?.phase,preset==='goal'?'blocked':undefined);
      const discard=await runtime.api(`/reviews/${review.proposalId}/actions`,{action:'discard'});assert.equal(discard.status,200,JSON.stringify(discard));
      if(preset==='goal') {
        await waitFor(()=>ctx.eventSystems.get(primary.agent.id).waits[0].state==='resolved');
        assert.ok(ctx.goals.get(primary.agent).revision>execution.waits[0].goal.revision);
        let stopped;
        for(let attempt=0;attempt<5;attempt++) {
          const current=ctx.eventSystems.get(primary.agent.id);
          stopped=await runtime.api(`/bindings/${primary.agent.id}/execution/actions`,{action:'stop',revision:current.revision});
          if(stopped.status===200)break;
          assert.equal(stopped.status,409);await new Promise(resolve=>setTimeout(resolve,20));
        }
        assert.equal(stopped.status,200,JSON.stringify(stopped));
      } else {
        const before=runtime.adapter.requests.length;
        const foreign=await runtime.api(`/bindings/${primary.agent.id}/execution/sources`,{action:'add',definition:{url:'http://127.0.0.1:9/foreign',eventType:'source.changed',pointer:'/source_revision_hash',condition:'changed',intervalMillis:20,debounceMillis:0,emitInitial:false}});
        assert.equal(foreign.status,409);
        const added=await runtime.api(`/bindings/${primary.agent.id}/execution/sources`,{action:'add',definition:{url:ownerUrl+'/assistant/context/document',eventType:'source.changed',pointer:'/source_revision_hash',condition:'changed',intervalMillis:20,debounceMillis:0,emitInitial:false}});
        assert.equal(added.status,200,JSON.stringify(added));
        await waitFor(()=>ctx.eventHttpSources.list(primary.agent.id)[0].observed);
        await new Promise(resolve=>setTimeout(resolve,100));assert.equal(runtime.adapter.requests.length,before);
        approveTimer(directory, String(primary.agent.id), 'sha256:changed', 'approved-timer-changed');
        runtime.adapter.architectureReviewId='approved-timer-changed';
        revision='sha256:changed'; runtime.adapter.revision=revision;
        await waitFor(()=>ctx.eventSystems.get(primary.agent.id).events.some(item=>item.type==='source.changed'));
        await waitFor(()=>previews===2);assert.equal(mutations,0);
        assert.ok(runtime.adapter.requests.length>before);
        const source=ctx.eventHttpSources.list(primary.agent.id)[0];
        assert.equal((await runtime.api(`/bindings/${primary.agent.id}/execution/sources`,{action:'disable',sourceId:source.id,revision:source.revision})).status,200);
      }
    }finally{state.close();}
  } finally {
    if(previousBinding===undefined)delete process.env.SPEC2GDS_BINDING_JSON;else process.env.SPEC2GDS_BINDING_JSON=previousBinding;
    if(ctx)await ctx.fiber.dispose();
    await new Promise(resolve=>owner.close(resolve));await rm(directory,{recursive:true,force:true});
  }
});
