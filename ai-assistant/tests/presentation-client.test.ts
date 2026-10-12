import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

function plugin() {
  let definition: any, tracker: any;
  const slots = new Map<string, any>();
  const React = { Fragment: 'fragment', createElement: (type: any, props: any, ...children: any[]) => ({ type, props: props || {}, children: children.flat(Infinity) }),
    useState: (initial: any) => [typeof initial === 'function' ? initial() : initial, () => {}], useEffect() {} };
  vm.runInNewContext(readFileSync(new URL('../client/index.js', import.meta.url), 'utf8'), {
    window: { __ModuleLoader__: { load(value: any) { definition = value; } } },
    document: { createElement: () => ({ dataset: {} }), head: { appendChild() {} }, documentElement: { dataset: {} } },
    URL, URLSearchParams, location: { search: '', hash: '' }, queueMicrotask() {},
  });
  definition.factory(() => React).apply({ uiSession: { registerNewSessionHandler() {} }, uiConversation: { events: { register(value: any) { tracker = value; } } },
    slots: { inject: (_name: string, register: any) => register(), register: (options: any, component: any) => slots.set(`${options.name}:${options.key || options.id || ''}`, { options, component }) } });
  const render = (node: any): any => {
    if (!node || typeof node !== 'object') return node;
    if (typeof node.type === 'function') return render(node.type(node.props));
    return { ...node, children: node.children.map(render) };
  };
  return { slots, tracker, render };
}
const nodes = (tree: any, predicate: (node: any) => boolean): any[] => typeof tree !== 'object' || tree === null ? [] : [...(predicate(tree) ? [tree] : []), ...(tree.children || []).flatMap((child: any) => nodes(child, predicate))];
const content = (tree: any): string => tree === null || tree === undefined || typeof tree === 'boolean' ? '' : typeof tree !== 'object' ? String(tree) : tree.children.map(content).join('');

function reviewTree(fixture: ReturnType<typeof plugin>, change: any) {
  const tail = fixture.slots.get('conversation.chat.turnTail:');
  return fixture.render(tail.component({ matched: { review: { proposalId: 'proposal', state: 'ready', domain: 'spec', artifact: { title: 'Adder' },
    presentation: { previewAvailable: true, summary: 'Update the adder.', groups: [{ label: 'Adder', changes: [change] }] } } } }));
}

test('product slots suppress prompt/context rows and replace raw product tool payloads', () => {
  const f = plugin();
  for (const key of ['system-prompt', 'context']) {
    const entry = f.slots.get(`conversation.chat.node:${key}`);assert.equal(entry.options.priority, -100);assert.equal(entry.component({ node: { data: 'private prompt' } }), null);
  }
  const row = f.slots.get('tool.call.toolview:structured_output').component({ toolName: 'structured_output', block: { kind: 'tool-result', content: [{ type: 'text', text: '{"private":"payload"}' }] } });
  assert.equal(content(row), 'Content prepared');assert.ok(!content(row).includes('payload'));
});

test('paired text rows preserve every source line and align added/deleted lines', () => {
  const f = plugin();
  const tree = reviewTree(f, { id: 'code', label: 'SystemVerilog', kind: 'code', change: 'changed', beforeAvailable: true, afterAvailable: true,
    before: 'first\nsecond\nremoved\nlast', after: 'first\ninserted\nsecond\nlast' });
  const lines = nodes(tree, node => node.props.className?.includes('s2g-text-line'));
  const left = lines.filter((_, index) => index % 2 === 0), right = lines.filter((_, index) => index % 2 === 1);
  const source = (side: any[]) => side.filter(line => content(line.children[0])).map(line => content(line.children[1])).join('\n');
  assert.equal(source(left), 'first\nsecond\nremoved\nlast');assert.equal(source(right), 'first\ninserted\nsecond\nlast');
  assert.ok(lines.some(line => line.props.className.includes('s2g-line--after')));assert.ok(lines.some(line => line.props.className.includes('s2g-line--before')));
  assert.equal(nodes(tree, node => node.type === 'details').length, 0);assert.equal(nodes(tree, node => node.type === 'pre').length, 0);
});

test('nested unknown values, false, zero, and removals render readable before/after values', () => {
  const f = plugin();
  const tree = reviewTree(f, { id: 'field', label: 'Custom field', kind: 'value', change: 'removed', beforeAvailable: true, afterAvailable: true,
    before: { enabled: false, depth: 0, modes: ['A', 'B'] }, after: null });
  assert.match(content(tree), /FieldBeforeAfter/);assert.match(content(tree), /EnabledNoDepth0ModesAB/);assert.match(content(tree), /Not present/);
  assert.ok(!content(tree).includes('{'));assert.match(content(tree), /Removed/);
});

test('width comparisons show bit counts and preserve the exact source ranges', () => {
  const f = plugin();
  const tree = reviewTree(f, { id: 'width', label: 'Port a width', kind: 'value', change: 'changed', beforeAvailable: true, afterAvailable: true,
    before: '[3:0]', after: '[7:0]' });
  assert.match(content(tree), /4 bits \(\[3:0\]\)/);assert.match(content(tree), /8 bits \(\[7:0\]\)/);
});

test('recorded flow tool results attach progress to their exact conversation turn', () => {
  const f = plugin(), tracker = f.tracker;
  let state = tracker.start({}, { event: { type: 'turn/start', data: { turn: 7 } } });
  state = tracker.update({ state }, { event: { type: 'tool/call', data: { name: 'flow_edit_spec', callId: 'call' } } });
  state = tracker.update({ state }, { event: { type: 'tool/result', seq: 20, data: { message: { source: { callId: 'call' }, content: [{ content: [{ type: 'text', text: '{"execution_id":"exact-flow"}' }] }] } } } });
  const location = tracker.buildLocationData({ state }, 'turn', null);
  const tail = f.slots.get('conversation.chat.turnTail:');
  const matched = tail.options.select({ seq: 21, turn: { data: { get: () => location.value } } });
  assert.equal(matched.flowExecutionId, 'exact-flow');assert.equal(tail.component({ matched, sessionId: 'exact-conversation' }).props.sessionId, 'exact-conversation');
  assert.equal(tail.options.select({ seq: 19, turn: { data: { get: () => location.value } } }), null);
});

test('older inline reviews load the current read-only presentation from their stored identities', () => {
  const f = plugin(), tail = f.slots.get('conversation.chat.turnTail:');
  const element = tail.component({ sessionId: 'conversation', matched: { callId: 'call', review: { proposalId: 'older-proposal', domain: 'spec' } } });
  const node = element.type(element.props);
  assert.equal(node.type.name, 'StoredReviewCard');assert.equal(node.props.reference.proposalId, 'older-proposal');assert.equal(node.props.reference.sessionId, 'conversation');
  assert.ok(f.slots.has('tool.call.toolview:prepare_spec_proposal'));
});
