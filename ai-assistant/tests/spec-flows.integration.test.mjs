/** Real Harness Loader and Spec service; only model responses are scripted. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { once } from 'node:events';
import { createServer } from 'node:net';
import { spawn, spawnSync } from 'node:child_process';
import { createUserMessage, ToolCallId } from '@ankdesh/dsh-llm';
import { SessionId } from '@ankdesh/dsh-session';
import { ProductState } from '../lib/state.js';
import { ServiceClients, ServiceError } from '../lib/service-clients.js';
import { boot, waitFor } from './support/event-runtime.mjs';
const root = resolve(import.meta.dirname, '../..');
const ports = [{ name: 'a', direction: 'in', range: "7:0", description: "Port purpose" }, { name: 'b', direction: 'in', range: "7:0", description: "Port purpose" }, { name: 'sum', direction: 'out', range: "8:0", description: "Port purpose" }];
const rtl = "assign sum = {1'b0, a} + {1'b0, b};";
function plan(name) { return { title: 'Unsigned adder', components: [{ name, purpose: 'Add two unsigned bytes.' }], designs: [],
  interfaces: [{ component: name, ports, parameters: [], constant_context: "" }], clocks_resets: [], decomposition_rationale: 'One combinational leaf.', assumptions: [], open_questions: [], concrete_configuration: { width: 8, sum_width: 9 } }; }
function saved(path) {
  const result = spawnSync(join(root, '.venv/bin/python'), ['-c',
    "import sys,json,zipfile; from spec2gds.spec.spec_format.ir import SpecRevision; r=SpecRevision.load(sys.argv[1]); z=zipfile.ZipFile(sys.argv[1]); print(json.dumps({'revision':r.source_revision_hash,'components':[{'id':c.ref.entity_id,'name':c.display_name,'ports':[(p.name,p.direction,p.width) for p in c.ports]} for c in r.components],'source':'\\n'.join(z.read(p).decode() for p in z.namelist() if p.endswith(('.xml','.json')))}))", path], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr); return JSON.parse(result.stdout);
}
async function service(directory, policy) {
  const server = createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening'); const port = server.address().port; await new Promise(done => server.close(done));
  const config = JSON.parse(await readFile(join(root, 'config/services.json'), 'utf8'));
  config.public_host = '127.0.0.1'; config.logging.enabled = false; config.logging.file = join(directory, 'events.jsonl');
  config.activities.scratch_root = join(directory, 'generated'); config.circuit_designer.preferences_file = join(directory, 'preferences.json');
  const configPath = join(directory, 'services.json'); await writeFile(configPath, JSON.stringify(config));
  const child = spawn(join(root, '.venv/bin/spec2gds-spec-service'), ['--host', '127.0.0.1', '--port', String(port), ...(policy === 'review' ? ['--require-designer-approval'] : [])],
    { cwd: root, env: { ...process.env, SPEC2GDS_SERVICE_CONFIG: configPath, SPEC_EDITOR_STATE_ROOT: join(directory, 'spec-state') }, stdio: ['ignore', 'pipe', 'pipe'] });
  let log = ''; child.stdout.on('data', data => { log += data; }); child.stderr.on('data', data => { log += data; });
  const url = `http://127.0.0.1:${port}`, deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, log);
    try { if ((await fetch(url + '/health')).ok) return { url, async close() { if (child.exitCode !== null || child.signalCode !== null) return; const exited = once(child, 'exit'); child.kill('SIGTERM'); await exited; } }; } catch {}
    await new Promise(done => setTimeout(done, 50));
  }
  child.kill('SIGKILL'); throw new Error('Spec service did not become ready: ' + log);
}
function script(runtime, toolName, title, component, invalidDraft = false, interfaceOptions = {}) {
  const scriptPorts = interfaceOptions.ports ?? ports;
  const parameters = interfaceOptions.parameters ?? [];
  const constant_context = interfaceOptions.constant_context ?? "";
  const body = interfaceOptions.body ?? rtl;
  runtime.adapter.stream = async function* (options) {
    this.requests.push(options);
    const last = options.messages.at(-1); let name, args;
    if (last?.source.kind === 'plugin' && last.source.plugin === 'flow-model-native') {
      assert.deepEqual(options.tools.map(tool => tool.name), ['structured_output']);
      const system = options.messages.filter(message => message.role === 'system').flatMap(message => message.content).filter(block => block.type === 'text').map(block => block.text).join('\n');
      assert.match(system, /one content phase of a host-controlled flow/);
      assert.doesNotMatch(system, /MUST call get_bound_context before answering|The Spec service currently allows automatic/);
      const data = JSON.parse(last.content.find(block => block.type === 'text').text);
      name = 'structured_output';
      if (!data.phase.startsWith('architecture/')) {
        assert.deepEqual(data.inputs.authoring_context.approved_component.ports, scriptPorts);
        assert.equal(data.inputs.authoring_context.operation_schema, undefined);
        assert.equal(data.inputs.authoring_context.pages, undefined);
      }
      args = data.phase.startsWith('architecture/') ? { ...plan(component), interfaces: [{ component, ports: scriptPorts, parameters, constant_context }] } : { name: component, ports: scriptPorts, parameters, description: invalidDraft ? '' : 'Adds two unsigned 8-bit inputs and retains the carry bit.', narrative: 'The sum includes the carry bit.', systemverilog: body };
    } else if (last?.source.kind === 'user') { assert.equal(options.tools.some(tool => ['prepare_spec_document_creation', 'prepare_architecture_review', 'prepare_spec_proposal'].includes(tool.name)), false, 'Spec has no legacy mutation tools'); assert.match(options.messages.filter(message => message.role === 'system').flatMap(message => message.content).filter(block => block.type === 'text').map(block => block.text).join('\n'), /flow_create_empty_spec|flow_add_component/, 'Native complete prompts must expose the available flow guidance'); name = toolName; args = { title, request: 'Create ' + component + ' with ports, description, narrative and functional SystemVerilog.' }; }
    if (name) {
      yield { type: 'block-start', index: 0, blockType: 'tool-call' };
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: ToolCallId('flow-call-' + this.requests.length), name, arguments: JSON.stringify(args) } };
      yield { type: 'usage', usage: { inputTokens: 100, outputTokens: 20 } }; yield { type: 'finish', reason: { kind: 'tool-calls' } };
    } else {
      yield { type: 'block-start', index: 0, blockType: 'text' }; yield { type: 'block-end', index: 0, block: { type: 'text', text: 'The remaining Goal needs designer input.' } };
      yield { type: 'finish', reason: { kind: 'stop' } };
    }
  };
}
async function start(runtime, agent) {
  const before = new Set(runtime.ctx.flows.list({ kind: 'host', sessionId: agent.id }).map(flow => flow.id));
  agent.followup(createUserMessage({ source: { kind: 'user' }, content: [{ type: 'text', text: 'Run the requested flow.' }] })); await agent.whenIdle();
  await waitFor(() => runtime.ctx.flows.list({ kind: 'host', sessionId: agent.id }).some(flow => !before.has(flow.id)));
  const flow = runtime.ctx.flows.list({ kind: 'host', sessionId: agent.id }).findLast(flow => !before.has(flow.id));
  return runtime.ctx.flows.settled(flow.id);
}
async function approve(runtime, flow, policy) {
  assert.equal(flow.status, 'waiting', flow.error); assert.equal(flow.pending.request.kind, 'architecture');
  const result = await runtime.api('/architecture-reviews/' + flow.pending.request.review_id + '/approve', { sessionId: String(flow.sourceSessionId), flowRevision: flow.revision }); assert.equal(result.status, 200, JSON.stringify(result));
  await waitFor(() => { const current = runtime.ctx.flows.get(flow.id, { kind: 'host', sessionId: flow.sourceSessionId }); return ['succeeded', 'failed', 'needs-reconcile'].includes(current.status) || current.pending?.request.kind === 'spec-receipt'; });
  let current = runtime.ctx.flows.get(flow.id, { kind: 'host', sessionId: flow.sourceSessionId });
  if (policy === 'review') {
    assert.equal(current.status, 'waiting', current.error); assert.equal(current.pending.request.kind, 'spec-receipt');
    const state = new ProductState(join(runtime.directory, 'assistant.sqlite3')); let binding;
    try { binding = state.getBinding(current.pending.request.session_id); } finally { state.close(); }
    const response = await fetch(binding.serviceUrl + '/assistant/proposals/' + current.pending.request.proposal_id + '/approve?owner_document_key=' + encodeURIComponent(binding.serviceDocumentKey), { method: 'POST' });
    assert.equal(response.ok, true, JSON.stringify(await response.json()));
  }
  await waitFor(() => ['succeeded', 'failed', 'needs-reconcile'].includes(runtime.ctx.flows.get(flow.id, { kind: 'host', sessionId: flow.sourceSessionId }).status));
  current = runtime.ctx.flows.get(flow.id, { kind: 'host', sessionId: flow.sourceSessionId }); assert.equal(current.status, 'succeeded', current.error); return current;
}
for (const policy of ['automatic', 'review']) for (const preset of ['focused', 'goal']) test(`${preset} flows save complete Components with ${policy} content policy`, { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-')); let owner, ctx, runtime;
  try {
    owner = await service(directory, policy); runtime = await boot(directory, owner.url); runtime.directory = directory; ctx = runtime.ctx;
    const handle = await ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: preset }, agentOptions: { provider: 'mock', model: 'mock' } });
    script(runtime, 'flow_create_empty_spec', 'Empty flow Spec', 'empty'); const empty = await start(runtime, handle.agent);
    assert.equal(empty.status, 'succeeded', empty.error); assert.equal(empty.usage.requests, 0); assert.equal(saved(empty.result.path).components.length, 0);
    const source = preset === 'goal' ? ctx.agents.get(SessionId(empty.result.session_id)) : handle.agent;
    script(runtime, 'flow_create_spec_with_component', 'Flow Adder', 'flow_adder'); const pending = await start(runtime, source);
    const complete = await approve(runtime, pending, policy); assert.equal(complete.usage.requests, 2); assert.equal(complete.result.state, 'applied');
    const state = new ProductState(join(directory, 'assistant.sqlite3')); let creation;
    try { creation = state.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(request => request.flowExecutionId === complete.id); } finally { state.close(); }
    const first = saved(creation.destination); assert.equal(first.components.length, 1); assert.equal(first.revision, complete.result.source_revision_hash);
    assert.deepEqual(first.components[0].ports, [['a','in','[7:0]'],['b','in','[7:0]'],['sum','out','[8:0]']]); assert.ok(first.source.includes(rtl)); assert.match(first.source, /Adds two unsigned/);
    const destination = ctx.agents.get(SessionId(creation.destinationSessionId)); assert.ok(destination); assert.equal(creation.status, 'bound');
    script(runtime, 'flow_add_component', 'Second adder', 'flow_adder_two'); const added = await approve(runtime, await start(runtime, destination), policy);
    const second = saved(creation.destination); assert.equal(second.components.length, 2); assert.equal(second.revision, added.result.source_revision_hash);
    if (preset === 'goal') {
      assert.equal(ctx.eventSystems.get(source.id).requests.length, 3, 'Start and both phases use the source budget');
      assert.equal(ctx.eventSystems.get(destination.id).requests.length, 3, 'Existing Spec start and its two phases use its budget');
    }
  } catch (error) {
    if (ctx) {
      const state = new ProductState(join(directory, 'assistant.sqlite3'));
      try {
        const sessions = ['source', ...state.listBindings(true).map(binding => binding.sessionId)];
        const flows = sessions.flatMap(id => ctx.flows.list({ kind: 'host', sessionId: SessionId(id) }));
        await writeFile(`/tmp/spec-flow-diag-${preset}-${policy}.json`, JSON.stringify({ flows, decisions: state.database.prepare('SELECT * FROM flow_decision_outbox').all(), requests: runtime.adapter.requests.map(request => ({ tools: request.tools?.map(tool => tool.name), last: request.messages.at(-1) })) }, null, 2));
      } finally { state.close(); }
    }
    throw error;
  } finally { if (ctx) await ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('explicit architecture revision reuses a confirmed Spec after authoring failed', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-revise-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_spec_with_component', 'Revised adder', 'revision_adder', true);
    const pending = await start(runtime, source);
    const approval = await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/approve', { sessionId: 'source', flowRevision: pending.revision });
    assert.equal(approval.status, 200);
    await waitFor(() => runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id }).status === 'failed');
    const failed = runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id });
    assert.match(failed.error, /description/); assert.equal(failed.usage.requests, 2);
    let state = new ProductState(join(directory, 'assistant.sqlite3')), creation;
    try { creation = state.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(row => row.flowExecutionId === failed.id); } finally { state.close(); }
    assert.equal(saved(creation.destination).components.length, 0);
    const listed = await runtime.api('/flows/source');
    const failureView = listed.value.flows.find(row => row.id === failed.id);
    assert.equal(failureView.architecture_review_id, pending.pending.request.review_id);
    assert.equal(failureView.creation_confirmation.path, creation.destination);
    assert.equal(failureView.creation_confirmation.binding_confirmed, true);
    assert.equal(failureView.creation_confirmation.content_required, true);
    script(runtime, 'flow_create_spec_with_component', 'Revised adder', 'revision_adder');
    const body = { sessionId: 'source', flowRevision: failed.revision, feedback: 'Supply a complete description and retain these ports.' };
    const revised = await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/revise', body);
    assert.equal(revised.status, 200, JSON.stringify(revised));
    const replacement = await runtime.ctx.flows.settled(revised.value.flow.id);
    assert.equal(replacement.parentExecutionId, failed.id);
    assert.notEqual(replacement.pending.request.review_id, pending.pending.request.review_id);
    const complete = await approve(runtime, replacement, 'automatic');
    const duplicate = await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/revise', body);
    assert.equal(duplicate.status, 200); assert.equal(duplicate.value.flow.id, complete.id);
    assert.equal(saved(creation.destination).components.length, 1);
    state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      assert.equal(state.database.prepare('SELECT COUNT(*) AS count FROM source_creation_requests').get().count, 1);
      assert.equal(state.architectureReview(pending.pending.request.review_id).status, 'approved');
      assert.equal(state.architectureReview(replacement.pending.request.review_id).destinationSessionId, creation.destinationSessionId);
    } finally { state.close(); }
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('an active Goal cannot complete during a flow and receives a durable release on success', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-goal-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'goal' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_empty_spec', 'Goal Spec', 'empty'); const empty = await start(runtime, source);
    const destination = runtime.ctx.agents.get(SessionId(empty.result.session_id));
    script(runtime, 'flow_add_component', 'Goal adder', 'goal_adder');
    const goal = runtime.ctx.goals.create(destination, { objective: 'Save an adder, then discuss verification.', maxGoalRounds: 1 });
    const pending = await start(runtime, destination), paused = runtime.ctx.goals.get(destination);
    assert.equal(paused.phase, 'paused'); assert.equal(paused.id, goal.id);
    assert.throws(() => runtime.ctx.goals.complete(destination, paused), /flow/i);
    assert.throws(() => runtime.ctx.goals.resume(destination, paused), /flow/i);
    const complete = await approve(runtime, pending, 'automatic');
    await waitFor(() => {
      const state = new ProductState(join(directory, 'assistant.sqlite3'));
      try { return state.database.prepare('SELECT delivered FROM flow_goal_releases WHERE execution_id=?').get(complete.id)?.delivered === 1; } finally { state.close(); }
    });
    const remaining = runtime.ctx.goals.get(destination);
    assert.equal(remaining.id, goal.id); assert.notEqual(remaining.phase, 'complete');
    assert.equal(runtime.ctx.flows.active(destination.id), false);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('browser reload and closure preserve the host flow and Spec Editor approval', { timeout: 90000 }, async () => {
  process.env.PLAYWRIGHT_BROWSERS_PATH ??= join(root, 'circuit-designer/.playwright-browsers');
  const { createRequire } = await import('node:module');
  const dependencies = createRequire(resolve(process.env.AI_ASSISTANT_UI_TEST_DEPS || join(root, 'tests/ui-scenarios'), 'package.json'));
  const nativeDependencies = createRequire(resolve(process.env.HARNESS_SOURCE || join(root, '../deepseek-harness'), 'packages/client/ui-conversation/package.json'));
  const { chromium, expect } = dependencies('@playwright/test');
  const { createServer: createHttpServer } = await import('node:http');
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-browser-')); let owner, runtime, app, browser;
  try {
    owner = await service(directory, 'review'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_spec_with_component', 'Browser adder', 'browser_adder'); const waiting = await start(runtime, source);
    const assets = new Map([
      ['/product.js', await readFile(join(root, 'ai-assistant/bundles/web/lib/client.js'), 'utf8')],
      ['/react.js', await readFile(resolve(nativeDependencies.resolve('react/package.json'), '../umd/react.development.js'), 'utf8')],
      ['/react-dom.js', await readFile(resolve(nativeDependencies.resolve('react-dom/package.json'), '../umd/react-dom.development.js'), 'utf8')],
    ]);
    const shell = `<!doctype html><html><head><script src="/react.js"></script><script src="/react-dom.js"></script></head><body><div id="dock"></div><div id="review"></div><script>
      const slots={};window.__ModuleLoader__={load(definition){const plugin=definition.factory(()=>React);plugin.apply({
        uiSession:{registerNewSessionHandler(){}},uiConversation:{events:{register(){}}},
        slots:{inject(name,register){if(name==='conversation.input.dock'||name==='conversation.chat.turnTail')register();},register(options,component){slots[options.id||options.name]=component;return ()=>{};}},
        sessions:{list:{getSnapshot:()=>({byId:{}})},open(){}},workspaces:{list:{getSnapshot:()=>({items:[]})}}
      });ReactDOM.createRoot(document.querySelector('#dock')).render(React.createElement(slots['flow-approvals'],{sessionId:'source'}));
      ReactDOM.createRoot(document.querySelector('#review')).render(React.createElement(slots['conversation.chat.turnTail'],{sessionId:'source',matched:{flowExecutionId:${JSON.stringify(waiting.id)}}}));}};
      </script><script src="/product.js"></script></body></html>`;
    app = createHttpServer(async (request, response) => {
      try {
        if (request.url.startsWith('/spec2gds-api')) return runtime.routes.find(route => route.kind === 'prefix').handler(request, response);
        if (assets.has(request.url)) { response.writeHead(200, { 'Content-Type': 'text/javascript' }); return response.end(assets.get(request.url)); }
        response.writeHead(200, { 'Content-Type': 'text/html' }); response.end(shell);
      } catch (error) { response.writeHead(500); response.end(String(error)); }
    });
    app.listen(0, '127.0.0.1'); await once(app, 'listening');
    const browserOptions = { headless: true, ...(process.env.ASSISTANT_UI_BROWSER_PATH ? { executablePath: process.env.ASSISTANT_UI_BROWSER_PATH } : {}) };
    browser = await chromium.launch(browserOptions); const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${app.address().port}`);
    await expect(page.getByRole('button', { name: 'Approve architecture', exact: true })).toBeVisible();
    await expect(page.locator('#review pre')).toHaveCount(0);
    await expect(page.locator('#review')).toContainText('Unsigned adder');
    await page.reload();
    await page.getByRole('button', { name: 'Approve architecture', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Review in Spec Editor' })).toBeVisible({ timeout: 30000 });
    await expect.poll(() => page.locator('#review .s2g-comparison').count()).toBeGreaterThan(0);
    const editorUrl = await page.getByRole('link', { name: 'Review in Spec Editor' }).getAttribute('href');
    await browser.close(); browser = undefined;
    const pending = runtime.ctx.flows.get(waiting.id, { kind: 'host', sessionId: source.id });
    assert.equal(pending.status, 'waiting'); assert.equal(pending.pending.request.kind, 'spec-receipt');
    browser = await chromium.launch(browserOptions); const editor = await browser.newPage();
    await editor.goto(editorUrl);
    await expect(editor.getByRole('button', { name: 'Approve', exact: true })).toBeVisible({ timeout: 30000 });
    await editor.getByRole('button', { name: 'Approve', exact: true }).click();
    await waitFor(() => runtime.ctx.flows.get(waiting.id, { kind: 'host', sessionId: source.id }).status === 'succeeded');
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      const creation = state.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(row => row.flowExecutionId === waiting.id);
      assert.equal(saved(creation.destination).components[0].name, 'browser_adder');
    } finally { state.close(); }
  } finally {
    if (browser) await browser.close(); if (app) await new Promise(done => app.close(done));
    if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true });
  }
});


test('a naming collision does not overwrite an existing Spec or start model phases', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-collision-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_empty_spec', 'Same title', 'empty'); const first = await start(runtime, source);
    const before = await readFile(first.result.path);
    const collision = await start(runtime, source);
    assert.equal(collision.status, 'failed'); assert.match(collision.error, /exists|name/i);
    assert.equal(collision.usage.requests, 0); assert.deepEqual(await readFile(first.result.path), before);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('an unavailable selected service stops before creating a Spec', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-outage-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    await owner.close();
    script(runtime, 'flow_create_empty_spec', 'Unavailable', 'empty'); const stopped = await start(runtime, source);
    assert.equal(stopped.status, 'failed'); assert.match(stopped.error, /unavailable/i); assert.equal(stopped.usage.requests, 0);
    assert.equal(stopped.nodes.some(node => node.id === 'create'), false);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('architecture Cancel stops the flow without creating a file and leaves the Goal paused', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-architecture-cancel-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'goal' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_empty_spec', 'Cancel source', 'empty'); const empty = await start(runtime, source);
    const destination = runtime.ctx.agents.get(SessionId(empty.result.session_id));
    const goal = runtime.ctx.goals.create(destination, { objective: 'Create the requested Spec and inspect it.', maxGoalRounds: 1 });
    script(runtime, 'flow_create_spec_with_component', 'Cancelled hardware', 'cancelled_adder'); const pending = await start(runtime, destination);
    assert.throws(() => runtime.ctx.goals.create(destination, { objective: 'Competing work' }), /flow/i);
    const decision = await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/cancel', { sessionId: String(destination.id), flowRevision: pending.revision });
    assert.equal(decision.status, 200, JSON.stringify(decision));
    await waitFor(() => runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: destination.id }).status === 'cancelled');
    const cancelled = runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: destination.id });
    assert.equal(cancelled.usage.requests, 1); assert.equal(cancelled.nodes.some(node => node.id === 'create'), false);
    assert.equal(runtime.ctx.goals.get(destination).id, goal.id); assert.equal(runtime.ctx.goals.get(destination).phase, 'paused');
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    try { assert.equal(state.database.prepare('SELECT COUNT(*) AS count FROM source_creation_requests').get().count, 1); } finally { state.close(); }
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

for (const boundary of ['before', 'after']) test(`Resume reconciles a lost ${boundary}-dispatch submission without repeating model phases`, { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-submit-loss-')); let owner, runtime;
  const original = ServiceClients.prototype.submitSpec; let injected = false, dispatches = 0;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_spec_with_component', 'Receipt recovered adder', 'receipt_adder');
    const pending = await start(runtime, source);
    ServiceClients.prototype.submitSpec = async function (...args) {
      if (!injected && boundary === 'before') { injected = true; throw new ServiceError(503, 'Submission connection lost before dispatch.', true); }
      dispatches++; const result = await original.apply(this, args);
      if (!injected) { injected = true; throw new ServiceError(503, 'Submission response lost after dispatch.', true); }
      return result;
    };
    const approval = await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/approve', { sessionId: 'source', flowRevision: pending.revision });
    assert.equal(approval.status, 200);
    await waitFor(() => ['needs-reconcile', 'failed'].includes(runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id }).status));
    assert.equal(runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id }).status, 'needs-reconcile', JSON.stringify(runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id }))); 
    const uncertain = runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id });
    assert.equal(uncertain.usage.requests, 2); const modelCalls = runtime.adapter.requests.length;
    const submission = uncertain.nodes.find(node => node.id.endsWith('/submit')); assert.ok(submission);
    await runtime.ctx.flows.control(uncertain.id, uncertain.revision, 'resume', { kind: 'human', sessionId: source.id });
    await waitFor(() => runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id }).status === 'succeeded');
    const complete = runtime.ctx.flows.get(pending.id, { kind: 'host', sessionId: source.id });
    assert.equal(runtime.adapter.requests.length, modelCalls); assert.equal(complete.usage.requests, 2); assert.equal(dispatches, 1);
    assert.equal(complete.nodes.filter(node => node.id.endsWith('/submit')).length, 1);
    assert.equal(complete.nodes.find(node => node.id.endsWith('/submit')).operationId, submission.operationId);
    const state = new ProductState(join(directory, 'assistant.sqlite3')); let creation;
    try { creation = state.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(row => row.flowExecutionId === complete.id); } finally { state.close(); }
    const archive = saved(creation.destination); assert.equal(archive.components.length, 1); assert.equal(archive.components[0].name, 'receipt_adder');
    assert.equal(archive.revision, complete.result.source_revision_hash); assert.match(archive.source, /Adds two unsigned/);
  } finally { ServiceClients.prototype.submitSpec = original; if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('a closed source conversation retains Goal accounting and its pending release', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-closed-goal-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const seed = (await runtime.ctx.agents.create({ sessionId: SessionId('seed'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    script(runtime, 'flow_create_empty_spec', 'Goal source Spec', 'empty'); const empty = await start(runtime, seed);
    const binding = (await runtime.api('/bindings/' + empty.result.session_id)).value.session;
    const reservation = await runtime.api('/bindings/reserve', { sessionId: 'source', domain: 'spec', serviceBaseUrl: binding.serviceUrl, serviceDocumentKey: binding.serviceDocumentKey, documentId: binding.documentId, scope: 'document', preset: 'goal' });
    assert.equal(reservation.status, 201, JSON.stringify(reservation));
    const handle = await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'goal' }, agentOptions: { provider: 'mock', model: 'mock' } });
    assert.equal((await runtime.api('/bindings/source/activate', {})).status, 200);
    const source = handle.agent;
    script(runtime, 'flow_create_spec_with_component', 'Closed source adder', 'closed_adder');
    const goal = runtime.ctx.goals.create(source, { objective: 'Save an adder, then discuss verification.', maxGoalRounds: 8 });
    const pending = await start(runtime, source);
    assert.equal(runtime.ctx.goals.get(source).phase, 'paused'); assert.equal(pending.callerContext.agentPreset, 'goal');
    assert.equal(await runtime.ctx.sessions.flush(source.session), true);
    await handle.dispose(); assert.equal(runtime.ctx.agents.get(source.id), undefined);
    const complete = await approve(runtime, pending, 'automatic'); assert.equal(complete.usage.requests, 2);
    let state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      const release = state.database.prepare('SELECT delivered FROM flow_goal_releases WHERE execution_id=?').get(complete.id);
      assert.equal(release.delivered, 0); assert.equal(state.database.prepare('SELECT COUNT(*) AS count FROM flow_goal_claims').get().count, 0);
    } finally { state.close(); }
    assert.equal(runtime.ctx.eventSystems.get(source.id).requests.length, 3, 'Closed source keeps the initiating request and both phase charges');
    const restored = await runtime.ctx.agents.resume({ resumeSessionId: source.id, agentOptions: { provider: 'mock', model: 'mock' } });
    await waitFor(() => {
      state = new ProductState(join(directory, 'assistant.sqlite3'));
      try { return state.database.prepare('SELECT delivered FROM flow_goal_releases WHERE execution_id=?').get(complete.id)?.delivered === 1; } finally { state.close(); }
    });
    const remaining = runtime.ctx.goals.get(restored.agent); assert.equal(remaining.id, goal.id); assert.notEqual(remaining.phase, 'complete');
    assert.equal(runtime.ctx.flows.active(restored.agent.id), false);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

async function edited(runtime, destination, { componentId, documentId, structural = false, stale = false }) {
  runtime.adapter.stream = async function* (options) {
    this.requests.push(options);
    assert.deepEqual(options.tools.map(tool => tool.name), ['structured_output']);
    const phase = JSON.parse(options.messages.at(-1).content.find(block => block.type === 'text').text);
    const entity = { document_id: documentId, entity_kind: 'component', entity_id: componentId };
    const args = phase.phase.startsWith('architecture/') ? plan('editable_adder') : {
      supported: true, unsupported_reason: null, base_source_revision_hash: stale ? 'sha256:stale' : phase.inputs.context.source_revision_hash,
      title: 'Refine the saved Component', summary: 'Refine its description.', rationale: 'Requested edit.', assumptions: [],
      operations: [{ operation_id: 'describe', type: 'set_entity_metadata', entity, description: 'Revised by the explicit edit flow.' },
        ...(structural ? [{ operation_id: 'extra', type: 'upsert_component_port', component: entity, port: { name: 'enable', family: 'wire', direction: 'in' } }] : [])],
    };
    yield { type: 'block-start', index: 0, blockType: 'tool-call' };
    yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: ToolCallId('edit-' + this.requests.length), name: 'structured_output', arguments: JSON.stringify(args) } };
    yield { type: 'usage', usage: { inputTokens: 100, outputTokens: 20 } };
    yield { type: 'finish', reason: { kind: 'tool-calls' } };
  };
  const accepted = await runtime.api('/flow-runs/start', { sessionId: String(destination.id), toolName: 'flow_edit_spec', inputs: { title: 'Refine saved Component', request: 'Update the description' }, requestId: 'edit-' + runtime.adapter.requests.length });
  assert.equal(accepted.status, 202, JSON.stringify(accepted));
  return runtime.ctx.flows.settled(accepted.value.flow.id);
}
for (const policy of ['automatic', 'review']) test(`flow-only Spec edits and removed routes under ${policy} policy`, { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-edit-')); let owner, runtime;
  try {
    owner = await service(directory, policy); runtime = await boot(directory, owner.url); runtime.directory = directory;
    const source = (await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } })).agent;
    const noLegacy = agent => { for (const name of ['prepare_spec_proposal', 'prepare_spec_document_creation', 'prepare_architecture_review']) assert.equal(agent.ctx.tools.get(name), undefined); };
    noLegacy(source);
    assert.equal((await runtime.api('/sources/create', { domain: 'spec', serviceBaseUrl: owner.url, title: 'Bypass' })).status, 410);
    assert.equal((await runtime.api('/source-requests/old/create', {})).status, 404);
    assert.equal((await runtime.api('/architecture-reviews/old/continue', {})).status, 404);
    assert.equal((await runtime.api('/flow-runs/start', { sessionId: 'source', toolName: 'flow_create_empty_spec', inputs: { title: 'No stable ID', request: 'Create' } })).status, 400);
    script(runtime, 'flow_create_spec_with_component', 'Editable Spec', 'editable_adder');
    const pending = await start(runtime, source);
    assert.equal((await runtime.api('/architecture-reviews/' + pending.pending.request.review_id + '/approve', { sessionId: 'source', flowRevision: pending.revision - 1 })).status, 409);
    const created = await approve(runtime, pending, policy);
    const state = new ProductState(join(directory, 'assistant.sqlite3')); let creation;
    try {
      creation = state.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(row => row.flowExecutionId === created.id);
      state.storeArchitecture({ reviewId: 'old-review', sessionId: 'source', callId: 'old', status: 'pending', plan: plan('old') });
      assert.equal((await runtime.api('/architecture-reviews/old-review/approve', { sessionId: 'source', flowRevision: created.revision })).status, 410);
      for (const sessionId of [creation.destinationSessionId]) {
        const inputId = state.createProposalInput(sessionId, [{ name: 'description' }]);
        assert.equal((await runtime.api('/proposal-inputs/' + inputId + '/confirm', { values: { description: 'Legacy input' } })).status, 410);
        assert.equal(state.confirmedProposalInput(sessionId, inputId), null);
      }
    } finally { state.close(); }
    const destination = runtime.ctx.agents.get(SessionId(creation.destinationSessionId)); noLegacy(destination);
    assert.equal((await runtime.api('/reviews/' + created.result.proposal_id + '/actions', { action: 'discard' })).status, 410);
    const initial = saved(creation.destination), before = await readFile(creation.destination);
    const info = { componentId: initial.components[0].id, documentId: creation.documentId };
    const stale = await edited(runtime, destination, { ...info, stale: true });
    assert.equal(stale.status, 'failed'); assert.match(stale.error, /authored source revision/); assert.deepEqual(await readFile(creation.destination), before);
    let edit = await edited(runtime, destination, info);
    if (policy === 'review') {
      assert.equal(edit.status, 'waiting', edit.error); assert.equal(edit.pending.request.kind, 'spec-receipt');
      assert.deepEqual(await readFile(creation.destination), before);
      assert.equal((await fetch(owner.url + '/assistant/proposals/' + edit.pending.request.proposal_id + '/approve?owner_document_key=' + encodeURIComponent(creation.serviceDocumentKey), { method: 'POST' })).ok, true);
      await waitFor(() => runtime.ctx.flows.get(edit.id, { kind: 'host', sessionId: destination.id }).status === 'succeeded');
      edit = runtime.ctx.flows.get(edit.id, { kind: 'host', sessionId: destination.id });
    }
    if (edit.status === 'waiting') { await waitFor(() => runtime.ctx.flows.get(edit.id, { kind: 'host', sessionId: destination.id }).status === 'succeeded'); edit = runtime.ctx.flows.get(edit.id, { kind: 'host', sessionId: destination.id }); }
    assert.equal(edit.status, 'succeeded', edit.error); assert.equal(edit.usage.requests, 1);
    assert.match(saved(creation.destination).source, /Revised by the explicit edit flow/);
    assert.equal(saved(creation.destination).components[0].ports.length, 3);
    const structural = await edited(runtime, destination, { ...info, structural: true });
    assert.equal(structural.status, 'waiting', structural.error); assert.equal(structural.pending.request.kind, 'architecture');
    const review = await runtime.api('/architecture-reviews/' + structural.pending.request.review_id);
    assert.equal(typeof review.value.architecture_review.approved_operations_digest, 'string');
    const complete = await approve(runtime, structural, policy);
    assert.equal(complete.usage.requests, 2); assert.equal(saved(creation.destination).components[0].ports.length, 4);
    noLegacy(destination);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('manual empty-Spec start is idempotent and does not call a model', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec-flow-manual-')); let owner, runtime;
  try {
    owner = await service(directory, 'automatic'); runtime = await boot(directory, owner.url);
    await runtime.ctx.agents.create({ sessionId: SessionId('source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } });
    const command = { sessionId: 'source', toolName: 'flow_create_empty_spec', inputs: { title: 'Manual empty Spec', request: 'Create an empty Spec', service_url: owner.url }, requestId: 'manual-create' };
    const first = await runtime.api('/flow-runs/start', command); assert.equal(first.status, 202, JSON.stringify(first));
    const complete = await runtime.ctx.flows.settled(first.value.flow.id); assert.equal(complete.status, 'succeeded', complete.error);
    const progress = await runtime.api('/flows/source');
    assert.equal(progress.status, 200);
    const summary = progress.value.flows.find(flow => flow.id === complete.id);
    assert.equal(summary.definition_id, 'spec2gds.create_empty_spec');
    assert.equal(summary.definition, undefined);
    assert.equal(summary.nodes, undefined);
    assert.equal(summary.inputs, undefined);
    const duplicate = await runtime.api('/flow-runs/start', command); assert.equal(duplicate.status, 202); assert.equal(duplicate.value.flow.id, complete.id);
    assert.equal(runtime.adapter.requests.length, 0); assert.equal(saved(complete.result.path).components.length, 0);
    assert.equal((await runtime.api('/flow-runs/start', { ...command, inputs: { ...command.inputs, title: 'Changed' } })).status, 409);
  } finally { if (runtime) await runtime.ctx.fiber.dispose(); if (owner) await owner.close(); await rm(directory, { recursive: true, force: true }); }
});

test('parameterized Component creation checks defaults and saves source expressions through the real service', { timeout: 60000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'flow-parameters-'));
  const owner = await service(directory, 'automatic');
  const runtime = await boot(directory, owner.url);
  runtime.directory = directory;
  try {
    const handle = await runtime.ctx.agents.create({ sessionId: SessionId('parameter-source'), meta: { agentPreset: 'focused' }, agentOptions: { provider: 'mock', model: 'mock' } });
    const ports = [
      { name: 'a', direction: 'in', range: 'LAST:BASE', description: 'First unsigned operand' },
      { name: 'b', direction: 'in', range: 'LAST:BASE', description: 'Second unsigned operand' },
      { name: 'sum', direction: 'out', range: 'WIDTH+1:1', description: 'Sum including carry' },
    ];
    script(runtime, 'flow_create_spec_with_component', 'Parameterized adder', 'parameter_adder', false, {
      ports, parameters: [{ name: 'WIDTH', rtl_type: 'int unsigned', value: '4', description: 'Operand width' }],
      constant_context: 'localparam int BASE=1, LAST=WIDTH;', body: "assign sum = {1'b0,a}+{1'b0,b};",
    });
    const pending = await start(runtime, handle.agent);
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      const review = state.architectureReview(pending.pending.request.review_id);
      assert.equal(review.elaborations[0].status, 'resolved');
      assert.deepEqual(review.elaborations[0].ports.map(port => port.width), [4,4,5]);
      assert.equal(review.elaborations[0].parameter_values.WIDTH, 4);
    } finally { state.close(); }
    const complete = await approve(runtime, pending, 'automatic');
    assert.equal(complete.result.state, 'applied');
    const records = new ProductState(join(directory, 'assistant.sqlite3'));
    let creation;
    try { creation = records.database.prepare('SELECT request_json FROM source_creation_requests').all().map(row => JSON.parse(row.request_json)).find(request => request.flowExecutionId === complete.id); }
    finally { records.close(); }
    assert.deepEqual(saved(creation.destination).components[0].ports, [['a','in','[LAST:BASE]'],['b','in','[LAST:BASE]'],['sum','out','[WIDTH+1:1]']]);
  } finally { await runtime.ctx.fiber.dispose(); await owner.close(); await rm(directory, { recursive: true, force: true }); }
});
