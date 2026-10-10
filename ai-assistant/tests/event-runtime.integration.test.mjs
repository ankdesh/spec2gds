import { serveIntegrationMetadata } from './support/integration-metadata.mjs';
/** Spec event compositions retain analysis and monitoring without a mutation path. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { boot, waitFor } from './support/event-runtime.mjs';
for (const preset of ['goal','orchestrated']) test(`${preset} keeps Spec analysis inside its declared capability boundary`,{timeout:30000},async()=>{
  const directory=await mkdtemp(join(tmpdir(),'spec2gds-analysis-'));
  const contract=JSON.parse(await readFile(new URL('./fixtures/spec-document-operation-contract.json',import.meta.url),'utf8'));
  let mutations=0,revision='sha256:test';
  const owner=createServer((request,response)=>{
    if(serveIntegrationMetadata(request,response))return;
    const path=new URL(request.url,'http://localhost').pathname;
    const send=value=>{response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(value));};
    if(path==='/health')return send({status:'ok'});
    if(path==='/assistant/operation-schema')return send(contract);
    if(path==='/assistant/context/document')return send({schema_version:'spec2gds.assistant-context.v1',scope:'document',document_id:'doc-test',source_revision_hash:revision,target:null,writable:{document_operations:['create_entity']},read_only:{existing_entities:true},rendered_context:{document_id:'doc-test',source_revision_hash:revision,target:null,text:'Specification with one ALU.'},available_references:{components:[],designs:[]},diagnostics:[]});
    if(request.method==='POST')mutations++; response.writeHead(404);response.end('{}');
  });
  owner.listen(0,'127.0.0.1');await once(owner,'listening'); const serviceUrl=`http://127.0.0.1:${owner.address().port}`;
  let runtime; const oldBinding=process.env.SPEC2GDS_BINDING_JSON;
  try {
    runtime=await boot(directory,serviceUrl);
    process.env.SPEC2GDS_BINDING_JSON=JSON.stringify({domain:'spec',serviceBaseUrl:serviceUrl,documentId:'doc-test',scope:'document',preset});
    const primary=(await runtime.ctx.agents.create({sessionId:SessionId('source'),agentOptions:{provider:'mock',model:'mock'},meta:{agentPreset:preset}})).agent;
    primary.followup(createUserMessage({source:{kind:'user'},content:[{type:'text',text:'Inspect the bound specification.'}]})); await primary.whenIdle();
    if(preset==='orchestrated')await waitFor(()=>runtime.ctx.eventSystems.get(primary.id).events.some(event=>event.type==='review.ready'));
    await waitFor(()=>runtime.ctx.eventSystems.get(primary.id).deliveries.every(item=>item.state==='completed'));
    const execution=runtime.ctx.eventSystems.get(primary.id); assert.equal(execution.mode,preset);assert.ok(execution.requests.length>0);assert.equal(mutations,0);
    for(const member of execution.members){
      const agent=runtime.ctx.agents.get(member.sessionId);
      for(const name of ['prepare_spec_proposal','prepare_architecture_review','prepare_spec_document_creation'])assert.equal(agent.ctx.tools.get(name),undefined);
      if(preset==='orchestrated')for(const name of ['flow_edit_spec','flow_add_component','flow_create_empty_spec','flow_create_spec_with_component'])assert.equal(agent.ctx.tools.get(name),undefined);
    }
    assert.equal(runtime.ctx.goals.get(primary),undefined,'Read analysis does not create a Goal');
    if(preset==='orchestrated') {
      assert.equal(execution.members.length,3);
      const rejected=await runtime.api('/flow-runs/start',{sessionId:'source',toolName:'flow_edit_spec',inputs:{title:'Bypass',request:'Edit'},requestId:'bypass'});assert.equal(rejected.status,409);
      const foreign=await runtime.api('/bindings/source/execution/sources',{action:'add',definition:{url:'http://127.0.0.1:9/foreign',eventType:'source.changed',pointer:'/source_revision_hash',condition:'changed',intervalMillis:20,debounceMillis:0,emitInitial:false}});assert.equal(foreign.status,409);
      const added=await runtime.api('/bindings/source/execution/sources',{action:'add',definition:{url:serviceUrl+'/assistant/context/document',eventType:'source.changed',pointer:'/source_revision_hash',condition:'changed',intervalMillis:20,debounceMillis:0,emitInitial:false}});assert.equal(added.status,200,JSON.stringify(added));
      await waitFor(()=>runtime.ctx.eventHttpSources.list(primary.id)[0].observed);
      revision='sha256:changed';runtime.adapter.revision=revision;
      await waitFor(()=>runtime.ctx.eventSystems.get(primary.id).events.some(event=>event.type==='source.changed'));
      await waitFor(()=>runtime.ctx.eventSystems.get(primary.id).deliveries.every(item=>item.state==='completed'));assert.equal(mutations,0);
      const monitor=runtime.ctx.eventHttpSources.list(primary.id)[0];assert.equal((await runtime.api('/bindings/source/execution/sources',{action:'disable',sourceId:monitor.id,revision:monitor.revision})).status,200);
    }
  } finally {if(oldBinding===undefined)delete process.env.SPEC2GDS_BINDING_JSON;else process.env.SPEC2GDS_BINDING_JSON=oldBinding;
    if(runtime)await runtime.ctx.fiber.dispose();await new Promise(done=>owner.close(done));await rm(directory,{recursive:true,force:true});}
});
