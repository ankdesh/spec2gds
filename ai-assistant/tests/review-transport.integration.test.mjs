/** Native dispatch, spilling, persistence, and scoped review recovery. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Service } from '@deepseek-ai/cordis';
import { createUserMessage, ToolCallId } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import * as SpillPolicy from '@deepseek-ai/dsh-spill-policy';
import { nativeTool } from '../lib/tool-registry.js';
import { defaultInstructions } from '../lib/instructions.js';
import { ProductState } from '../lib/state.js';
import { boot, waitFor } from './support/event-runtime.mjs';

test('spilled native text retains durable review metadata and the complete scoped review', { timeout: 30000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'review-native-'));
  let ctx;
  try {
    const runtime = await boot(directory, 'http://127.0.0.1:9'); ctx = runtime.ctx;
    class SpillStore extends Service {
      constructor(context) { super(context, 'spillStore'); }
      async saveText(input) {
        const locator = join(directory, 'spilled.txt'); await writeFile(locator, input.content);
        return { locator, retrievalHint: 'Read complete result' };
      }
    }
    await ctx.plugin(SpillStore); await ctx.plugin(SpillPolicy, { maxInlineBytes: 512 });
    const events = [];
    ctx.on('session/event', (session, event) => { if (String(session.id) === 'review') events.push(event); });
    const primary = await ctx.agents.create({ sessionId: SessionId('review'), agentOptions: { provider: 'mock', model: 'mock' }, meta: { agentPreset: 'focused' } });
    const state = new ProductState(join(directory, 'assistant.sqlite3'));
    let review;
    try {
      state.createBinding('review', { domain: 'circuit', serviceBaseUrl: 'http://127.0.0.1:9', serviceUrl: 'http://127.0.0.1:9', documentId: 'doc', scope: 'document',
        workspaceKey: 'w', workspaceTitle: 'Test', workspacePath: directory, workspaceDomain: 'circuit', workspaceServiceUrl: 'http://127.0.0.1:9', workspaceDocumentId: 'doc' });
      review = state.createReview({ proposalId: 'proposal', sessionId: 'review', callId: 'call', domain: 'circuit', state: 'ready', baseRevision: 'r',
        artifact: { operations: [] }, preview: { status: 'valid', content: '界'.repeat(60000) }, diagnostics: [], error: null, serviceResult: null });
    } finally { state.close(); }
    primary.agent.ctx.tools.register({ ...nativeTool('prepare_circuit_proposal', defaultInstructions, undefined, true),
      execute: async () => ({ success: true, proposal_id: 'proposal', state: 'ready', review, diagnostics: [], instruction: 'Details. '.repeat(400) }) });
    runtime.adapter.stream = async function* () {
      if (!events.some(event => event.type === 'tool/result')) {
        yield { type: 'block-start', index: 0, blockType: 'tool-call' };
        yield { type: 'block-end', index: 0, block: { type: 'tool-call', id: ToolCallId('call'), name: 'prepare_circuit_proposal', arguments: '{}' } };
        yield { type: 'finish', reason: { kind: 'tool-calls' } };
      } else {
        yield { type: 'block-start', index: 0, blockType: 'text' };
        yield { type: 'block-end', index: 0, block: { type: 'text', text: 'Review is ready.' } };
        yield { type: 'finish', reason: { kind: 'stop' } };
      }
    };
    primary.agent.followup(createUserMessage({ source: { kind: 'user' }, content: [{ type: 'text', text: 'Prepare review' }] }));
    await waitFor(() => events.some(event => event.type === 'turn/end')); await primary.agent.whenIdle();
    const result = events.find(event => event.type === 'tool/result');
    assert.throws(() => JSON.parse(result.data.message.content[0].content[0].text));
    assert.equal(result.data.meta.proposalId, 'proposal');
    await ctx.sessions.flush(primary.agent.session);
    const handle = await ctx.sessionPersistence.open(SessionId('review'), 'read');
    try {
      const persisted = (await handle.read()).events.find(event => event.type === 'tool/result');
      assert.deepEqual(persisted.data.meta, result.data.meta);
    } finally { await handle.close(); }
    const scoped = await runtime.api('/bindings/review/reviews/proposal');
    assert.equal(scoped.status, 200); assert.equal(scoped.value.review.preview.content.length, 60000);
    assert.equal((await runtime.api('/bindings/foreign/reviews/proposal')).status, 404);
    assert.ok((await readFile(join(directory, 'spilled.txt'), 'utf8')).includes('proposal'));
  } finally { if (ctx) await ctx.fiber.dispose(); await rm(directory, { recursive: true, force: true }); }
});
