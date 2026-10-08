/** Unbound browser architecture preparation through the real prompt/tool/model loop. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createUserMessage, ToolCallId } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { ProductState } from '../lib/state.js';
import { boot, waitFor } from './support/event-runtime.mjs';

const counter = {
  title: '16-bit up/down counter', components: [{ name: 'up_down_counter', purpose: 'Synchronous counter' }],
  designs: [], interfaces: [{ component: 'up_down_counter', ports: [
    { name: 'clk', direction: 'in', width: 1 }, { name: 'reset', direction: 'in', width: 1 },
    { name: 'up_down', direction: 'in', width: 1 }, { name: 'count', direction: 'out', width: 16 },
  ] }], clocks_resets: ['clk: rising edge', 'reset: synchronous active-high'],
  decomposition_rationale: 'Keep cohesive counting state unified.', assumptions: ['Wrap at 16 bits.'],
  open_questions: [], concrete_configuration: { width: 16, reset: 'synchronous active-high', overflow: 'wrap' },
};

for (const recover of [true, false]) test(`unbound architecture ${recover ? 'recovers from malformed arguments' : 'retains errors at the retry limit'}`, { timeout: 30000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'spec2gds-architecture-runtime-'));
  let ctx;
  try {
    // Preparation must work even while no Spec Editor is reachable.
    const runtime = await boot(directory, 'http://127.0.0.1:9', {}, true);
    ctx = runtime.ctx;
    const events = [];
    ctx.on('session/event', (session, event) => { if (String(session.id) === 'counter') events.push(event); });
    runtime.adapter.stream = async function* (options) {
      this.requests.push(options);
      const step = this.requests.length;
      if (recover && step === 3) {
        yield { type: 'block-start', index: 0, blockType: 'text' };
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'The architecture is ready for approval. No specification has been created.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
        return;
      }
      const args = recover && step === 2 ? counter : { ...counter, components: [{ component: 'up_down_counter' }] };
      yield { type: 'block-start', index: 0, blockType: 'tool-call' };
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: ToolCallId(`architecture-${step}`),
        name: 'prepare_architecture_review', arguments: JSON.stringify(args) } };
      yield { type: 'finish', reason: { kind: 'tool-calls' } };
    };
    const primary = await ctx.agents.create({ sessionId: SessionId('counter'),
      agentOptions: { provider: 'mock', model: 'mock' }, meta: { agentPreset: 'focused' } });
    primary.agent.followup(createUserMessage({ source: { kind: 'user' }, content: [{ type: 'text', text: 'Create a new specification for a 16-bit up/down counter.' }] }));
    await waitFor(() => events.some(event => event.type === 'turn/end'));
    await primary.agent.whenIdle();
    assert.equal(runtime.adapter.requests.length, 3);
    const request = runtime.adapter.requests[0];
    const system = request.messages.filter(message => message.role === 'system')
      .flatMap(message => message.content.filter(block => block.type === 'text').map(block => block.text)).join('\n');
    assert.match(system, /ARCHITECTURE AND IMPLEMENTATION AUTHORITY/);
    assert.match(system, /NEW SPECS/);
    assert.match(system, /components=\[\{name,purpose\}\]/);
    const schema = request.tools.find(tool => tool.name === 'prepare_architecture_review').parameters;
    assert.deepEqual(schema.properties.components.items.required, ['name']);
    assert.deepEqual(schema.properties.designs.items.required, ['name']);
    assert.deepEqual(schema.properties.interfaces.items.oneOf[0].properties.ports.items.properties.direction.enum, ['in', 'out', 'inout']);
    const results = events.filter(event => event.type === 'tool/result');
    assert.equal(results[0].data.message.content[0].isError, true);
    assert.match(JSON.stringify(results[0]), /components\[0\]\.name/);
    assert.equal(events.find(event => event.type === 'turn/end').data.reason.kind, recover ? 'completed' : 'blocked');
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      const review = state.architectureForCall('counter', 'architecture-2');
      assert.equal(Boolean(review), recover);
      if (recover) {
        assert.equal(review.status, 'pending');
        assert.deepEqual(review.plan.interfaces, counter.interfaces);
        assert.equal(results[1].data.message.content[0].isError, false);
      }
      assert.equal(state.getBinding('counter'), null);
      assert.equal(state.sourceCreationForCall('counter', 'architecture-2'), null);
    } finally { state.close(); }
  } finally {
    if (ctx) await ctx.fiber.dispose();
    await rm(directory, { recursive: true, force: true });
  }
});

test('structured decisions retain older review intent and recover a lost delivery acknowledgement', { timeout: 30000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'architecture-continuation-'));
  let ctx;
  try {
    const runtime = await boot(directory, 'http://127.0.0.1:9', {}, true); ctx = runtime.ctx;
    runtime.adapter.stream = async function* (options) {
      this.requests.push(options);
      if (options.messages.at(-1)?.source.kind === 'tool') {
        yield { type: 'block-start', index: 0, blockType: 'text' };
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Architecture is ready.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
      } else {
        yield { type: 'block-start', index: 0, blockType: 'tool-call' };
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: ToolCallId(`review-${this.requests.length}`), name: 'prepare_architecture_review', arguments: JSON.stringify(counter) } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
      }
    };
    const primary = await ctx.agents.create({ sessionId: SessionId('decisions'), agentOptions: { provider: 'mock', model: 'mock' }, meta: { agentPreset: 'focused' } });
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    try {
      for (const request of ['Original designer intent', 'Independent second request']) {
        primary.agent.followup(createUserMessage({ source: { kind: 'user' }, content: [{ type: 'text', text: request }] }));
        await primary.agent.whenIdle();
      }
      const [older, newer] = state.listArchitectureReviews();
      assert.notEqual(older.originalRequest, newer.originalRequest);
      assert.equal((await runtime.api(`/architecture-reviews/${older.reviewId}/revise`, { feedback: 'Use active-low reset' })).status, 200);
      assert.equal((await runtime.api(`/architecture-reviews/${older.reviewId}/continue`, { sessionId: 'decisions' })).status, 200);
      await primary.agent.whenIdle();
      const revised = state.listArchitectureReviews().at(-1);
      assert.equal(revised.originalRequest, 'Original designer intent');
      assert.equal(state.listArchitectureReviews().length, 3);
      const delivered = state.architectureReview(older.reviewId);
      // Simulate losing the product acknowledgement after the native log committed.
      state.storeArchitecture({ ...delivered, continuationSent: false });
      assert.equal((await runtime.api(`/architecture-reviews/${older.reviewId}/continue`, { sessionId: 'decisions' })).status, 200);
      await primary.agent.whenIdle();
      assert.equal(state.listArchitectureReviews().length, 3);
      assert.equal((await runtime.api(`/architecture-reviews/${revised.reviewId}/revise`, { feedback: 'Keep the approved interface' })).status, 200);
      assert.equal((await runtime.api(`/architecture-reviews/${revised.reviewId}/continue`, { sessionId: 'decisions' })).status, 200);
      await primary.agent.whenIdle();
      assert.equal(state.listArchitectureReviews().at(-1).originalRequest, 'Original designer intent');
      await ctx.sessions.flush(primary.agent.session);
      const handle = await ctx.sessionPersistence.open(SessionId('decisions'), 'read');
      try {
        const events = (await handle.read()).events;
        const messages = events.filter(event => event.type === 'user/message' && event.data.source.plugin === 'spec2gds.architecture');
        assert.equal(messages.length, 2);
        assert.equal(messages[0].data.source.form, 'notice');
        assert.equal(JSON.parse(messages[0].data.content[0].text).architecture_review_id, older.reviewId);
      } finally { await handle.close(); }
    } finally { state.close(); }
  } finally { if (ctx) await ctx.fiber.dispose(); await rm(directory, { recursive: true, force: true }); }
});
