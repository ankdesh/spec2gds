/** Real Loader, native agents/goals, trusted product catalogs, and HTTP owner integration. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { Context } from '@deepseek-ai/cordis';
import Loader from '@deepseek-ai/cordis-plugin-loader';
import Include from '@deepseek-ai/cordis-plugin-include';
import { LlmAdapter, createUserMessage, ToolCallId } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { ProductState } from '../lib/state.js';
import * as Product from '../lib/index.js';

const productRoot=fileURLToPath(new URL('..',import.meta.url));
const limits={maxRounds:8,maxRequests:48,maxTokens:500000,maxActiveMillis:60000,maxMembers:3,maxConcurrency:2,maxPending:100,maxEvents:100,maxPayloadBytes:8192,maxDepth:8};
async function waitFor(check) {
  const deadline=Date.now()+15000;
  while(Date.now()<deadline) {if(check())return;await new Promise(resolve=>setTimeout(resolve,20));}
  assert.ok(check(),'Timed out waiting for native execution');
}
class Adapter extends LlmAdapter {
  requests=[];
  async *stream(options) {
    this.requests.push(options);
    const last=options.messages.at(-1);
    let event;
    if(last?.source.kind==='plugin') {
      const text=last.content.find(block=>block.type==='text')?.text;
      if(text?.startsWith('{')) event=JSON.parse(text).event;
    }
    let call;
    if(event?.type==='user.requested'||event?.type==='analysis.ready') {
      call={name:'publish_event',arguments:{type:event.type==='user.requested'?'analysis.ready':'review.ready',payload_json:JSON.stringify(event.type==='user.requested'?{findings:'Add a timer; original request reviewed.'}:{result:'Timer change reviewed.'}),dedupe_key:event.id}};
    } else if(last?.source.kind==='user'||event?.type==='review.ready') {
      call={name:'get_bound_context',arguments:{}};
    } else if(last?.source.kind==='tool' && options.messages.at(-2)?.content.some(block=>block.type==='tool-call'&&block.name==='get_bound_context')) {
      // The initial orchestrated primary may only acknowledge before the reviewer returns.
      if(options.system?.includes('event driven') && !options.messages.some(message=>message.content.some(block=>block.type==='text'&&block.text.includes('"type":"review.ready"')))) call=undefined;
      else call={name:'prepare_spec_proposal',arguments:{supported:true,base_source_revision_hash:'sha256:test',unsupported_reason:null,title:'Add timer',summary:'Add a timer component.',rationale:'Requested and reviewed.',assumptions:[],operations:[{operation_id:'timer',type:'create_entity',kind:'component',name:'timer',instances:[]}]}};
    }
    if(call) {
      yield {type:'block-start',index:0,blockType:'tool-call'};
      yield {type:'block-end',index:0,block:{type:'tool-call',id:ToolCallId(randomUUID()),name:call.name,arguments:JSON.stringify(call.arguments)}};
      yield {type:'usage',usage:{inputTokens:100,outputTokens:20}};
      yield {type:'finish',reason:{kind:'tool-calls'}};
    } else {
      yield {type:'block-start',index:0,blockType:'text'};
      yield {type:'block-end',index:0,block:{type:'text',text:'Acknowledged; inspect the proposal review.'}};
      yield {type:'usage',usage:{inputTokens:100,outputTokens:10}};
      yield {type:'finish',reason:{kind:'stop'}};
    }
  }
}
async function boot(directory,ownerUrl) {
  const names=['agent-default-model','llm','session','session-projection','system-prompt','tools','agent','session-persistence-jsonl','token-meter','storage','storage-sqlite','storage-domain','event-system','event-system-yaml','prompt-catalog','prompt-catalog-yaml','goal','goal-round-driver','agent-loop'];
  const modules=new Map();
  for(const name of names) modules.set(`@deepseek-ai/dsh-${name}`,await import(`@deepseek-ai/dsh-${name}`));
  modules.set('@spec2gds/harness-assistant',Product);
  const configFor=name=>name==='agent-default-model'?{provider:'mock',model:'mock'}:name==='session-persistence-jsonl'?{root:join(directory,'sessions'),compression:'none'}:name==='storage-sqlite'?{path:join(directory,'events.sqlite3')}:name==='storage-domain'?{backend:'sqlite'}:name==='event-system-yaml'?{roots:[join(productRoot,'profile/catalog/event-systems')],maxFileBytes:262144,maxPromptBytes:32768}:name==='prompt-catalog-yaml'?{roots:[join(productRoot,'profile/catalog/prompts')]}:name==='goal'?{defaultMaxGoalRounds:8}:name==='agent-loop'?{agents:[]}:undefined;
  const rows=names.map(name=>({name:`@deepseek-ai/dsh-${name}`,...configFor(name)?{config:configFor(name)}:{}}));
  rows.push({name:'@spec2gds/harness-assistant',config:{provider:'mock',model:'mock',stateRoot:directory,scratchRoot:join(directory,'workspaces'),specDocumentRoot:join(directory,'documents'),specAllowlist:ownerUrl,circuitAllowlist:'http://127.0.0.1:9/api/circuit-designer/v1',requestTimeoutMs:3000,maxStepsPerTurn:3,maxOutputTokens:1200,interactiveForms:false,execution:{goal:{...limits,maxRequests:32,maxTokens:300000,maxMembers:1,maxConcurrency:1},orchestrated:limits}}});
  await writeFile(join(directory,'cordis.yml'),JSON.stringify(rows));
  const ctx=new Context();ctx.baseUrl=pathToFileURL(directory).href+'/';
  await ctx.plugin(Loader);ctx.loader.builtins.include=Include;
  ctx.loader.internal={version:'v2',async import(name){if(!modules.has(name))throw new Error(`Unexpected module ${name}`);return modules.get(name);}};
  await ctx.loader.create({name:'cordis:include',config:{path:pathToFileURL(join(directory,'cordis.yml')).href}});
  await ctx.loader.await();for(const entry of ctx.loader.entries())await entry.fiber?.await();
  await ctx.eventSystems.ready;
  const adapter=new Adapter();ctx.llm.registerAdapter(['mock'],adapter);
  return {ctx,adapter};
}
for(const preset of ['goal','orchestrated']) test(`${preset} composes native execution with the owner proposal boundary`,{timeout:30000},async()=>{
  const directory=await mkdtemp(join(tmpdir(),'spec2gds-events-integration-'));
  const contract=JSON.parse(await readFile(new URL('./fixtures/spec-document-operation-contract.json',import.meta.url),'utf8'));
  let previews=0,mutations=0;
  const owner=createServer((request,response)=>{
    const path=new URL(request.url,'http://localhost').pathname;
    const send=value=>{response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(value));};
    if(path==='/health')return send({status:'ok'});
    if(path==='/assistant/operation-schema')return send(contract);
    if(path==='/assistant/context/document')return send({schema_version:'spec2gds.assistant-context.v1',scope:'document',document_id:'doc-test',source_revision_hash:'sha256:test',target:null,writable:{document_operations:['create_entity']},read_only:{existing_entities:true},rendered_context:{document_id:'doc-test',source_revision_hash:'sha256:test',target:null,text:'Specification with one ALU.'},available_references:{components:[],designs:[]},diagnostics:[]});
    if(request.method==='POST'&&path==='/assistant/proposals/preview'){previews++;return send({status:'valid',diagnostics:[],diff:[]});}
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
      assert.equal(execution.status,'paused');
      assert.equal(execution.reason,'Owner review pending');
      assert.equal(ctx.goals.get(primary.agent).phase,'paused');
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
    try {assert.equal(state.listReviews(primary.agent.id)[0].state,'ready');}finally{state.close();}
  } finally {
    if(previousBinding===undefined)delete process.env.SPEC2GDS_BINDING_JSON;else process.env.SPEC2GDS_BINDING_JSON=previousBinding;
    if(ctx)await ctx.fiber.dispose();
    await new Promise(resolve=>owner.close(resolve));await rm(directory,{recursive:true,force:true});
  }
});
