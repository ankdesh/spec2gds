/** Real Loader, native agents/goals, trusted product catalogs, and HTTP owner integration. */
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { Readable } from 'node:stream';
import { Context, Service } from '@ankdesh/cordis';
import Loader from '@ankdesh/cordis-plugin-loader';
import Include from '@ankdesh/cordis-plugin-include';
import { LlmAdapter, ToolCallId } from '@ankdesh/dsh-llm';
import * as Product from '../../lib/index.js';

const productRoot=fileURLToPath(new URL('../..',import.meta.url));
const limits={maxRounds:8,maxRequests:48,maxTokens:500000,maxActiveMillis:60000,maxMembers:3,maxConcurrency:2,maxPending:100,maxEvents:100,maxPayloadBytes:8192,maxDepth:8};
export async function waitFor(check) {
  const deadline=Date.now()+15000;
  while(Date.now()<deadline) {if(check())return;await new Promise(resolve=>setTimeout(resolve,20));}
  assert.ok(check(),'Timed out waiting for native execution');
}
class Adapter extends LlmAdapter {
  completeOnReview=false; requests=[]; revision='sha256:test'; architectureReviewId='approved-timer';
  async *stream(options) {
    this.requests.push(options);
    const last=options.messages.at(-1);
    let event;
    if(last?.source.kind==='plugin') {
      const text=last.content.find(block=>block.type==='text')?.text;
      if(text?.startsWith('{')) event=JSON.parse(text).event;
    }
    let call;
    if(event?.type==='user.requested'||event?.type==='source.changed'||event?.type==='analysis.ready') {
      call={name:'publish_event',arguments:{type:event.type!=='analysis.ready'?'analysis.ready':'review.ready',payload_json:JSON.stringify(event.type!=='analysis.ready'?{findings:'Add a timer; original request reviewed.'}:{result:'Timer change reviewed.'}),dedupe_key:event.id}};
    } else if(last?.source.kind==='user'||event?.type==='review.ready') {
      call={name:'get_bound_context',arguments:{}};
    } else if(last?.source.kind==='tool' && options.messages.at(-2)?.content.some(block=>block.type==='tool-call'&&block.name==='get_bound_context')) {
      // The initial orchestrated primary may only acknowledge before the reviewer returns.
      if(options.system?.includes('event driven') && !options.messages.some(message=>message.content.some(block=>block.type==='text'&&block.text.includes('"type":"review.ready"')))) call=undefined;
      else call=undefined; // Spec mutations are selected as flows, never proposal tools.
    }
    if(this.completeOnReview && last?.source.kind==='goal') call={name:'get_goal',arguments:{}};
    if(this.completeOnReview && last?.source.kind==='tool' && options.messages.at(-2)?.content.some(block=>block.type==='tool-call'&&block.name==='get_goal')) {
      const value=JSON.parse(last.content.flatMap(block=>block.type==='tool-result'?block.content:[block]).find(block=>block.type==='text').text);
      if(value.goal?.phase==='active')call={name:'update_goal',arguments:{goal_id:value.goal.id,revision:value.goal.revision,action:'complete'}};
    }
    if(call) {
      yield {type:'block-start',index:0,blockType:'tool-call'};
      yield {type:'block-end',index:0,block:{type:'tool-call',id:ToolCallId(randomUUID()),name:call.name,arguments:JSON.stringify(call.arguments)}};
      yield {type:'usage',usage:{inputTokens:100,outputTokens:20}};
      yield {type:'finish',reason:{kind:'tool-calls'}};
    } else {
      yield {type:'block-start',index:0,blockType:'text'};
      yield {type:'block-end',index:0,block:{type:'text',text:'Acknowledged; the read-only analysis is complete.'}};
      yield {type:'usage',usage:{inputTokens:100,outputTokens:10}};
      yield {type:'finish',reason:{kind:'stop'}};
    }
  }
}
export async function boot(directory,serviceUrl,orchestratedLimits={},interactiveForms=false) {
  const routes=[];
  class Transport extends Service {
    constructor(ctx) { super(ctx,'webServer'); }
    register(route) { routes.push(route); return ()=>{}; }
  }
  class Connection extends Service {
    constructor(ctx) { super(ctx,'connection'); }
    authenticatedUrl(url) { return url+'/?token=test'; }
  }

  const names=['agent-default-model','llm','session','session-projection','system-prompt','tools','agent','session-persistence-jsonl','token-meter','storage','storage-sqlite','storage-domain','event-system','event-system-yaml','event-system-http','prompt-catalog','prompt-catalog-yaml','goal','goal-round-driver','invariants','flow-runtime','flow-yaml','flow-model-native','flow-model-native/invariant','agent-loop'];
  const custom = new Set(['event-system','event-system-yaml','event-system-http','prompt-catalog','prompt-catalog-yaml','flow-runtime','flow-yaml','flow-model-native','flow-model-native/invariant']);
  const packageName = name => `@ankdesh/${custom.has(name) ? 'ankdesh' : 'dsh'}-${name}`;
  const modules=new Map();
  for(const name of names) modules.set(packageName(name),await import(packageName(name)));
  modules.set('@spec2gds/harness-assistant',Product);
  modules.set('test:transport',Transport); modules.set('test:connection',Connection);
  const configFor=name=>name==='agent-default-model'?{provider:'mock',model:'mock'}:name==='session-persistence-jsonl'?{root:join(directory,'sessions'),compression:'none'}:name==='storage-sqlite'?{path:join(directory,'events.sqlite3')}:name==='storage-domain'?{backend:'sqlite'}:name==='event-system-yaml'?{roots:[join(productRoot,'profile/catalog/event-systems')],maxFileBytes:262144,maxPromptBytes:32768}:name==='prompt-catalog-yaml'?{roots:[join(productRoot,'profile/catalog/prompts')]}:name==='event-system-http'?{allowedOrigins:[serviceUrl],tickMillis:10,minIntervalMillis:10,maxIntervalMillis:10000,timeoutMillis:1000,maxResponseBytes:4096,maxSourcesPerConversation:2,maxTotalSources:4,maxConcurrentChecks:2,maxFailures:3}:name==='flow-runtime'?{maxRequests:4,maxTokens:500000,maxActiveMillis:300000,maxOutputTokens:16384,maxRetainedBytes:1048576,maxExpandedNodes:128}:name==='flow-yaml'?{roots:[join(productRoot,'profile/catalog/flows')],maxFileBytes:262144,maxInstructionBytes:32768}:name==='goal'?{defaultMaxGoalRounds:8}:name==='agent-loop'?{agents:[]}:undefined;
  const rows=names.map(name=>({name:packageName(name),...configFor(name)?{config:configFor(name)}:{}}));
  rows.push({name:'test:transport'},{name:'test:connection'});
  rows.push({name:'@spec2gds/harness-assistant',config:{provider:'mock',model:'mock',stateRoot:directory,scratchRoot:join(directory,'workspaces'),specDocumentRoot:join(directory,'documents'),specAllowlist:serviceUrl,circuitAllowlist:'http://127.0.0.1:9/api/circuit-designer/v1',requestTimeoutMs:3000,maxStepsPerTurn:3,maxOutputTokens:1200,interactiveForms,flowReceiptPollMillis:100,execution:{goal:{...limits,maxRequests:32,maxTokens:300000,maxMembers:1,maxConcurrency:1},orchestrated:{...limits,...orchestratedLimits}}}});
  await writeFile(join(directory,'cordis.yml'),JSON.stringify(rows));
  const ctx=new Context();ctx.baseUrl=pathToFileURL(directory).href+'/';
  await ctx.plugin(Loader);ctx.loader.builtins.include=Include;
  ctx.loader.internal={version:'v2',async import(name){if(!modules.has(name))throw new Error(`Unexpected module ${name}`);return modules.get(name);}};
  await ctx.loader.create({name:'cordis:include',config:{path:pathToFileURL(join(directory,'cordis.yml')).href}});
  await ctx.loader.await();for(const entry of ctx.loader.entries())await entry.fiber?.await();
  await ctx.eventSystems.ready;
  const adapter=new Adapter();ctx.llm.registerAdapter(['mock'],adapter);
  const api=async(path,body)=>{
    const route=routes.find(item=>item.kind==='prefix'); assert.ok(route);
    const request=Readable.from(body===undefined?[]:[Buffer.from(JSON.stringify(body))]);
    request.url='/spec2gds-api'+path;request.method=body===undefined?'GET':'POST';request.headers={host:'local','content-type':'application/json'};
    let status,value;
    await route.handler(request,{writeHead(code){status=code;},end(text){value=JSON.parse(text);}});
    return {status,value};
  };
  return {ctx,adapter,api,routes};
}
