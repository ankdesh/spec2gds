import { serveIntegrationMetadata } from "./support/integration-metadata.mjs";
/** Browser clicks use the shipped product plugin and real Loader/goals/event services.
 * Only the model and external owner are deterministic; the tiny shell implements
 * Harness's session/workspace/slot adapters rather than mocking product requests. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, readFile, rm, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { SessionId } from '@deepseek-ai/dsh-session';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { boot, waitFor } from './support/event-runtime.mjs';
import { approveTimer } from './support/approved-timer.mjs';

const dependencies = createRequire(resolve(process.env.ASSISTANT_UI_TEST_DEPS || new URL('..',import.meta.url).pathname,'package.json'));
const { chromium, expect } = dependencies('@playwright/test');
const root = new URL('..',import.meta.url);
const shell = `<!doctype html><html><head><meta charset="utf-8"><script src="/react.js"></script><script src="/react-dom.js"></script></head><body>
<button id="new">New conversation</button><label>Request<input id="request" value="Propose a timer component."></label><button id="send">Send request</button><div id="dock"></div><div id="reviews"></div>
<script>
const slots={},workspaceItems=[];let current;
const dock=ReactDOM.createRoot(document.querySelector('#dock')),reviews=ReactDOM.createRoot(document.querySelector('#reviews'));
const post=async(path,body)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw Error(value.error);return value;};
window.__ModuleLoader__={load(definition){const plugin=definition.factory(()=>React);plugin.apply({
uiSession:{registerNewSessionHandler(handler){document.querySelector('#new').onclick=()=>handler.handle();}},uiConversation:{events:{register(){}}},
slots:{inject(name,register){if(name==='conversation.input.dock'||name==='conversation.chat.turnTail')register();},register(options,component){slots[options.id||options.name]=component;return ()=>{};}},
sessions:{list:{getSnapshot:()=>({byId:{}})},create:async options=>{await post('/test/create-session',options);return options.sessionId;},open(id){current=id;window.currentSession=id;dock.render(React.createElement(slots.execution,{key:id,sessionId:id}));}},
workspaces:{list:{getSnapshot:()=>({items:workspaceItems})},create:async options=>{const value={workspaceId:'ws-'+workspaceItems.length,...options};workspaceItems.push(value);return value;},rename:async(id,title)=>{const value=workspaceItems.find(item=>item.workspaceId===id);value.title=title;return value;}}
});}};
document.querySelector('#send').onclick=()=>post('/test/send',{sessionId:current,text:document.querySelector('#request').value});
setInterval(async()=>{if(!current)return;const value=await (await fetch('/spec2gds-api/bindings/'+encodeURIComponent(current)+'/reviews')).json();reviews.render(React.createElement(React.Fragment,null,...(value.reviews||[]).map(review=>React.createElement(slots['conversation.chat.turnTail'],{key:review.proposalId,matched:{review}}))));},100);
</script><script src="/product.js"></script></body></html>`;

async function fixture() {
  const directory=await mkdtemp(join(tmpdir(),'spec2gds-event-ui-'));
  const contract=JSON.parse(await readFile(new URL('./fixtures/spec-document-operation-contract.json',import.meta.url),'utf8'));
  let revision='sha256:test', mutations=0, previews=0;
  const owner=createServer((request,response)=>{
    if (serveIntegrationMetadata(request, response)) return;
    const path=new URL(request.url,'http://localhost').pathname;
    const send=value=>{response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify(value));};
    if(path==='/health')return send({status:'ok'});
    if(path==='/assistant/capabilities')return send({approval_policy:'review'});
    if(path==='/documents/snapshot')return send({document_id:'doc-test',narrative:{title:'UI test specification'},components:[]});
    if(path==='/assistant/operation-schema')return send(contract);
    if(path==='/assistant/context/document')return send({schema_version:'spec2gds.assistant-context.v1',scope:'document',document_id:'doc-test',source_revision_hash:revision,target:null,writable:{document_operations:['create_entity']},read_only:{existing_entities:true},rendered_context:{document_id:'doc-test',source_revision_hash:revision,target:null,text:'Specification with one ALU.'},available_references:{components:[],designs:[]},diagnostics:[]});
    if(request.method==='POST'&&path==='/assistant/proposals/preview'){previews++;return send({status:'valid',diagnostics:[],diff:[]});}
    if(request.method==='POST'&&path.endsWith('/decision'))return send({state:'discarded'});
    if(request.method==='POST'&&path==='/assistant/submissions')return send({state:'pending',proposal_id:'owner-pending'});
    if(request.method==='POST')mutations++;
    response.writeHead(404);response.end('{}');
  });
  owner.listen(0,'127.0.0.1');await once(owner,'listening');
  const runtime=await boot(directory,`http://127.0.0.1:${owner.address().port}`,{maxMembers:7});
  runtime.adapter.completeOnReview=true;
  const plugin=await readFile(new URL('client/index.js',root),'utf8');
  const assets=new Map([['/product.js',plugin],['/react.js',await readFile(resolve(dependencies.resolve('react/package.json'),'../umd/react.development.js'),'utf8')],['/react-dom.js',await readFile(resolve(dependencies.resolve('react-dom/package.json'),'../umd/react-dom.development.js'),'utf8')]]);
  const app=createServer(async(request,response)=>{
    if (serveIntegrationMetadata(request, response)) return;
    try {
      if(request.url.startsWith('/spec2gds-api'))return runtime.routes.find(route=>route.kind==='prefix').handler(request,response);
      if(assets.has(request.url)){response.writeHead(200,{'Content-Type':'text/javascript; charset=utf-8'});return response.end(assets.get(request.url));}
      if(request.url.startsWith('/test/')) {
        let data='';for await(const chunk of request)data+=chunk;const body=JSON.parse(data);
        if(request.url==='/test/create-session') {
          await runtime.ctx.agents.create({sessionId:SessionId(body.sessionId),agentOptions:{provider:'mock',model:'mock'},meta:{agentPreset:body.agentPreset},setup:async(ctx)=>{if(body.agentPreset==='goal')await ctx.plugin(await import('@deepseek-ai/dsh-tool-goal'));}});
          approveTimer(directory, body.sessionId);
        }
        else if(request.url==='/test/send') {
          const agent=runtime.ctx.agents.get(SessionId(body.sessionId));
          if(agent.session.header.agentPreset==='goal'&&!runtime.ctx.goals.get(agent))runtime.ctx.goals.create(agent,{objective:body.text,maxGoalRounds:8});
          agent.followup(createUserMessage({content:[{type:'text',text:body.text}],source:{kind:'user'}}));
        }
        response.writeHead(200,{'Content-Type':'application/json'});return response.end('{}');
      }
      response.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});response.end(shell);
    }catch(error){response.writeHead(500,{'Content-Type':'application/json'});response.end(JSON.stringify({error:error.message}));}
  });
  app.listen(0,'127.0.0.1');await once(app,'listening');
  const browser=await chromium.launch({headless:true,...(process.env.ASSISTANT_UI_BROWSER_PATH ? {executablePath:process.env.ASSISTANT_UI_BROWSER_PATH} : {})});const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${app.address().port}`);
  await page.waitForFunction(() => typeof document.querySelector('#new')?.onclick === 'function');
  return {page,runtime,directory,get mutations(){return mutations;},get previews(){return previews;},change(){revision='sha256:changed';runtime.adapter.revision=revision;},
    async close(){try{await screenshot(page,'last-state');assert.deepEqual(errors,[]);}finally{await browser.close();await new Promise(resolve=>app.close(resolve));await runtime.ctx.fiber.dispose();await new Promise(resolve=>owner.close(resolve));await rm(directory,{recursive:true,force:true});}}};
}
async function screenshot(page,name) {
  const directory=process.env.ASSISTANT_UI_SCREENSHOT_DIR;
  if(!directory)return;
  await mkdir(directory,{recursive:true});
  await page.screenshot({path:join(directory,`${name}.png`),fullPage:true});
}
async function chooser(page,preset) {
  await page.getByRole('button',{name:'New conversation',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Start a design conversation'});
  await expect(dialog.getByLabel('Target',{exact:true})).toBeVisible();
  await dialog.getByLabel('Assistant preset').selectOption(preset);return dialog;
}
async function customTemplate(page,dialog,preset) {
  await dialog.getByRole('button',{name:'Configure event template',exact:true}).click();
  const editor=page.getByRole('dialog',{name:`Event setup · ${preset}`});
  await expect(editor, await page.locator('body').innerText()).toBeVisible({timeout:3000});
  await editor.getByLabel('Template name',{exact:true}).fill(`${preset} browser template`);
  await editor.getByLabel('Prompt · primary',{exact:true}).fill((await editor.getByLabel('Prompt · primary',{exact:true}).inputValue())+'\nUse concise explanations for the browser tutorial.');
  await editor.getByRole('button',{name:'Validate and preview'}).click();
  await expect(editor.getByRole('region',{name:'Configuration review'})).toContainText('Validation passed');
  await editor.getByRole('button',{name:'Save reviewed template'}).click();
  await expect(editor).not.toBeVisible();
}
async function start(page,dialog) {const previous=await page.evaluate(()=>window.currentSession);await dialog.getByRole('button',{name:'Start conversation',exact:true}).click();await page.waitForFunction(old=>window.currentSession&&window.currentSession!==old,previous);await expect(page.locator('[data-s2g-execution]')).toBeVisible();return page.evaluate(()=>window.currentSession);}
async function inspect(page) {await page.locator('.s2g-inspector > summary').click();}

test('orchestrated UI saves text-backed reactions, runs analyst/reviewer, and explains causal deliveries', {timeout:45000},async()=>{
  const f=await fixture();try {
    const dialog=await chooser(f.page,'orchestrated');await customTemplate(f.page,dialog,'orchestrated');const id=await start(f.page,dialog);
    await f.page.getByRole('button',{name:'Send request',exact:true}).click();
    await waitFor(()=>f.runtime.ctx.eventSystems.get(SessionId(id)).events.some(event=>event.type==='review.prepared'));
    await inspect(f.page);const state=f.runtime.ctx.eventSystems.get(SessionId(id));
    assert.equal(state.members.length,3);assert.ok(state.definition.agents[0].prompt.includes('browser tutorial'));assert.equal(f.mutations,0);assert.equal(f.previews,1);
    const review=state.events.find(event=>event.type==='review.ready');
    await f.page.getByLabel('Inspect event',{exact:true}).selectOption(review.id);
    await expect(f.page.locator('[data-causal-event]')).toContainText('user.requested (human) → analysis.ready (analyst) → review.ready (reviewer)');
    await expect(f.page.locator('[data-causal-event]')).toContainText('Matched prepare: exact review.ready → primary');
    await expect(f.page.getByRole('table',{name:'Model request charges'})).toBeVisible();
    await f.page.getByRole('button',{name:'Discard',exact:true}).click();
    await waitFor(()=>f.runtime.ctx.eventSystems.get(SessionId(id)).deliveries.every(item=>item.state==='completed'));
    await f.page.waitForTimeout(2100); // Let the dock observe the committed review decision before its CAS action.
    await f.page.getByRole('button',{name:'Pause',exact:true}).click();await expect(f.page.locator('[data-s2g-execution]')).toHaveAttribute('data-s2g-execution','paused');
    await f.page.getByRole('button',{name:'Resume',exact:true}).click();await expect(f.page.locator('[data-s2g-execution]')).toHaveAttribute('data-s2g-execution','active');
    assert.deepEqual(f.runtime.ctx.eventSystems.get(SessionId(id)).definition,state.definition);
    await screenshot(f.page,"01-orchestrated-final");
  }finally{await f.close();}
});

test('goal UI retains one native primary, waits for owner review, and controls model-free HTTP checks', {timeout:45000},async()=>{
  const f=await fixture();try {
    const dialog=await chooser(f.page,'goal');await customTemplate(f.page,dialog,'goal');const id=await start(f.page,dialog);
    await f.page.getByRole('button',{name:'Send request',exact:true}).click();await waitFor(()=>f.runtime.ctx.goals.get(f.runtime.ctx.agents.get(SessionId(id)))?.phase==='blocked');
    await expect(f.page.locator('[data-s2g-execution]')).toContainText('waiting');assert.equal(f.runtime.ctx.eventSystems.get(SessionId(id)).members.length,1);assert.equal(f.mutations,0);
    await f.page.getByRole('button',{name:'Discard',exact:true}).click();await waitFor(()=>f.runtime.ctx.eventSystems.get(SessionId(id)).waits.some(wait=>wait.state==='resolved'));
    await waitFor(()=>f.runtime.ctx.goals.get(f.runtime.ctx.agents.get(SessionId(id)))?.phase==='complete');
    await expect(f.page.locator('[data-s2g-execution]')).toContainText('goal complete');
    await f.page.getByText('Monitor owner endpoint',{exact:true}).click();await f.page.getByLabel('Check interval in seconds').fill('5');
    await f.page.getByRole('button',{name:'Start monitoring',exact:true}).click();await expect(f.page.getByRole('button',{name:'Disable monitor',exact:true})).toBeVisible();
    await waitFor(()=>f.runtime.ctx.eventHttpSources.list(SessionId(id))[0]?.observed);
    await f.runtime.ctx.agents.get(SessionId(id)).whenIdle();const requests=f.runtime.adapter.requests.length;
    await f.page.waitForTimeout(2100);assert.equal(f.runtime.adapter.requests.length,requests);
    await f.page.getByRole('button',{name:'Disable monitor',exact:true}).click();await expect(f.page.getByRole('button',{name:'Enable monitor',exact:true})).toBeVisible();
    await inspect(f.page);await expect(f.page.getByText('Pinned event configuration',{exact:true})).toBeVisible();
    await f.page.getByRole('button',{name:'Stop',exact:true}).click();await expect(f.page.locator('[data-s2g-execution]')).toHaveAttribute('data-s2g-execution','stopped');
    await screenshot(f.page,"02-goal-final");
  }finally{await f.close();}
});

test('both preset UIs reject permission escalation and preserve pinned text when saved templates change', {timeout:60000},async()=>{
  const f=await fixture();try {
    for(const preset of ['goal','orchestrated']) {
      const dialog=await chooser(f.page,preset);await customTemplate(f.page,dialog,preset);const id=await start(f.page,dialog);await inspect(f.page);
      const original=f.runtime.ctx.eventSystems.get(SessionId(id));
      await f.page.getByRole('button',{name:'Configure event templates',exact:true}).click();const editor=f.page.getByRole('dialog',{name:`Event setup · ${preset}`});
      const catalog=(await f.runtime.api('/event-templates')).value.templates;const template=catalog.find(item=>item.name===`${preset} browser template`);
      await editor.getByLabel('Template',{exact:true}).selectOption(template.key);
      await f.page.keyboard.press('Shift+Tab');await expect(editor.getByRole('button',{name:'Validate and preview'})).toBeFocused();
      await f.page.keyboard.press('Tab');await expect(editor.getByLabel('Template',{exact:true})).toBeFocused();
      await editor.getByText('Text definition (JSON / YAML subset)',{exact:true}).click();
      const document=JSON.parse(template.text);document.definition.agents[0].tools.push('run_shell');
      await editor.getByLabel('Configuration text',{exact:true}).fill(JSON.stringify(document));await editor.getByRole('button',{name:'Validate and preview'}).click();
      await expect(editor.getByRole('alert')).toContainText('Unapproved');await expect(editor.getByRole('button',{name:'Save reviewed template'})).toBeDisabled();
      document.definition.agents[0].tools.pop();document.definition.agents[0].prompt+='\nA later template revision.';
      if(preset==='orchestrated') {
        document.definition.agents.push({id:'observer',prompt:'Observe review preparation without mutations.',tools:['get_bound_context','get_event_system'],publishes:[]});
        document.definition.subscriptions.push({id:'observe-prepared',event:'review.prepared',target:'observer'});
      }
      await editor.getByLabel('Configuration text',{exact:true}).fill(JSON.stringify(document));await editor.getByRole('button',{name:'Apply text to visual editor'}).click();
      await expect(editor.getByLabel('Prompt · primary',{exact:true})).toHaveValue(document.definition.agents[0].prompt);
      await editor.getByRole('button',{name:'Validate and preview'}).click();await editor.getByRole('button',{name:'Save reviewed template'}).click();
      assert.deepEqual(f.runtime.ctx.eventSystems.get(SessionId(id)).definition,original.definition);
      const reopened=await chooser(f.page,preset);await reopened.getByLabel('Event template',{exact:true}).selectOption(template.key);const next=await start(f.page,reopened);
      const configured=f.runtime.ctx.eventSystems.get(SessionId(next));
      assert.ok(configured.definition.agents[0].prompt.includes('later template revision'));
      if(preset==='orchestrated')assert.equal(configured.members.length,4);
      await inspect(f.page);
      await screenshot(f.page,`03-configuration-pinning-${preset}-final`);
      if(preset==='orchestrated'&&process.env.ASSISTANT_UI_SCREENSHOT_DIR){
        await f.page.getByRole('button',{name:'Configure event templates',exact:true}).click();
        const editor=f.page.getByRole('dialog',{name:`Event setup · ${preset}`});
        await editor.getByLabel('Template',{exact:true}).selectOption(template.key);
        await screenshot(f.page,'04-orchestrated-topology-editor');
        await editor.getByRole('button',{name:'Close',exact:true}).click();
      }
    }
  }finally{await f.close();}
});
