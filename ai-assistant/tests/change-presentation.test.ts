import assert from 'node:assert/strict';
import test from 'node:test';
import { presentationFor, hasSavedReceipt, readableDiagnostic } from '../src/change-presentation.js';
import { flowPresentation, relatedFlowViews } from '../src/flow-presentation.js';
import { publicReview } from '../src/proposal-presentation.js';
import type { ProposalReview } from '../src/types.js';

const review = (overrides: Partial<ProposalReview> = {}): ProposalReview => ({
  proposalId: 'proposal', sessionId: 'conversation', callId: 'operation', domain: 'spec', state: 'ready', baseRevision: 'base',
  artifact: { title: 'Update Adder', summary: 'Widen the input.', rationale: 'Match the output.', assumptions: ['Unsigned inputs.'] },
  artifactDigest: 'private', preview: null, diagnostics: [], error: null, serviceResult: null, version: 1, createdAt: '', updatedAt: '', ...overrides,
});

test('Spec fields use Section labels and suppress provenance and duplicate display values', () => {
  const result = presentationFor(review({ preview: { diff: [
    { path: '$[adder].tables[ports].rows[a].cells.width.value', label: 'Adder › Ports › a › Value', change: 'changed', before: '[3:0]', after: '[7:0]' },
    { path: '$[adder].tables[ports].rows[a].cells.width.display_text', label: 'Adder › Ports › a › Display text', change: 'changed', before: '[3:0]', after: '[7:0]' },
    { path: '$[adder].tables[ports].rows[a].cells.width.schema_path', change: 'changed', before: 'private.old', after: 'private.new' },
  ] } }));
  assert.equal(result.groups.length, 1);
  assert.equal(result.groups[0]?.label, 'Adder › Ports');
  assert.deepEqual(result.groups[0]?.changes.map(change => [change.label, change.before, change.after]), [['Adder › Ports › a › Width', '[3:0]', '[7:0]']]);
  assert.equal(result.summary, 'Widen the input.');assert.equal(result.rationale, 'Match the output.');
});

test('text, code, added content, removed content, and unknown fields retain their exact values', () => {
  const source = 'assign sum = a + b;\n' + '// context\n'.repeat(7000);
  const result = presentationFor(review({ preview: { diff: [
    { path: '$.sv.content', label: 'Adder › SystemVerilog › Content', change: 'added', before: null, after: source },
    { path: '$.description', label: 'Adder › Description', change: 'changed', before: 'Old prose', after: 'New prose' },
    { path: '$.ports[a]', label: 'Adder › Port a', change: 'removed', before: { name: 'a', direction: 'in', width: 4, row_id: 'opaque' }, after: null },
    { path: '$.custom', label: 'Adder › Custom field', change: 'changed', before: { enabled: false, depth: 0 }, after: { enabled: true, depth: 2 } },
  ] } }));
  const changes = result.groups.flatMap(group => group.changes);
  assert.equal(changes[0]?.kind, 'code');assert.equal(changes[0]?.after, source);assert.equal(changes[0]?.before, null);
  assert.equal(changes[1]?.kind, 'text');assert.equal(changes[1]?.before, 'Old prose');
  assert.deepEqual(changes[2]?.before, { Name: 'a', Direction: 'in', Width: 4 });assert.equal(changes[2]?.change, 'removed');
  assert.deepEqual(changes[3]?.before, { Enabled: false, Depth: 0 });assert.deepEqual(changes[3]?.after, { Enabled: true, Depth: 2 });
});

test('Circuit changes resolve names, connection endpoints, placement, and terminal values', () => {
  const base = { components: [{ id: 'c1', label: 'Adder', terminals: [{ id: 'p1', label: 'Sum' }] }], design: {
    instances: [{ id: 'i1', label: 'Main adder' }, { id: 'i2', label: 'Spare adder' }],
    boundary_terminals: [{ id: 'b1', label: 'Result', width: 4 }], nets: [{ id: 'n1', label: 'Sum bus', endpoints: [{ kind: 'instance', instance_id: 'i1', terminal_id: 'p1' }] }],
  }, layout: { instances: { i1: { x: 20, y: 30 } } } };
  const candidate = structuredClone(base);candidate.design.boundary_terminals[0]!.width = 8;
  candidate.design.nets[0]!.endpoints[0]!.instance_id = 'i2';candidate.layout.instances.i1.x = 90;
  const result = presentationFor(review({ domain: 'circuit', preview: { base_document: base, candidate, diff: {
    added: [], removed: [], changed: [{ kind: 'boundary_terminal', id: 'b1' }, { kind: 'layout', id: 'design' }], connections_changed: ['n1'],
  } } }));
  const changes = result.groups.flatMap(group => group.changes);
  assert.equal(changes[0]?.label, 'Boundary terminal · Result › Width');assert.equal(changes[0]?.before, 4);assert.equal(changes[0]?.after, 8);
  assert.deepEqual(changes[1]?.after, { 'Main adder': { X: 90, Y: 30 } });
  assert.deepEqual(changes[2]?.before, ['Main adder › Sum']);assert.deepEqual(changes[2]?.after, ['Spare adder › Sum']);
});

test('unavailable previews differ from valid no-change previews, and missing sides are explicit', () => {
  assert.equal(presentationFor(review()).previewAvailable, false);
  const empty = presentationFor(review({ preview: { diff: [] } }));assert.equal(empty.previewAvailable, true);assert.deepEqual(empty.groups, []);
  const partial = presentationFor(review({ preview: { diff: [{ label: 'Description', after: 'New' }] } }));
  assert.equal(partial.groups[0]?.changes[0]?.beforeAvailable, false);assert.equal(partial.groups[0]?.changes[0]?.afterAvailable, true);
});

test('new Component code is shown separately and duplicate placement labels retain both values', () => {
  const result = presentationFor(review({ preview: { diff: [{ label: 'Adder', change: 'added', before: null,
    after: { title: 'Adder', content_sections: [{ section_id: 'sv', section_type: 'sv', title: 'SystemVerilog', payload: { content: 'assign sum = a + b;' } }] } }] } }));
  const changes = result.groups.flatMap(group => group.changes);
  assert.equal(changes[1]?.kind, 'code');assert.equal(changes[1]?.after, 'assign sum = a + b;');assert.equal(changes[1]?.before, null);
  const document = { components: [], design: { instances: [{ id: 'a', label: 'Adder' }, { id: 'b', label: 'Adder' }, { id: 'c', label: 'Adder (2)' }] }, layout: { instances: { a: { x: 1 }, b: { x: 2 }, c: { x: 3 } } } };
  const after = structuredClone(document);after.layout.instances.b.x = 9;
  const circuit = presentationFor(review({ domain: 'circuit', preview: { base_document: document, candidate: after, diff: { changed: [{ kind: 'layout', id: 'layout' }] } } }));
  assert.deepEqual(circuit.groups[0]?.changes[0]?.after, { Adder: { X: 1 }, 'Adder (2)': { X: 9 }, 'Adder (2) (2)': { X: 3 } });
});

test('whole keyed Sections and ports use content names instead of storage path suffixes', () => {
  const result = presentationFor(review({ preview: { diff: [
    { path: '$[component-component_timer_core_abcdef1234]', label: 'Timer › Component component timer core abcdef', change: 'added', before: null,
      after: { section_id: 'component-component_timer_core_abcdef1234', title: 'Timer', level: 2, entity_ref: { entity_kind: 'component' } } },
    { path: '$[component].tables[ports].rows[wire-port-uuid]', label: 'Timer › Ports › irq › Rows wire port uuid', change: 'added', before: null,
      after: { row_id: 'wire-port-uuid', cells: { name: { value: 'irq', display_text: 'irq' }, width: { value: '[7:0]', display_text: '[7:0]' } } } },
  ] } }));
  assert.deepEqual(result.groups.flatMap(group => group.changes.map(change => change.label)), ['Component · Timer', 'Timer › Ports › irq']);
  assert.ok(!JSON.stringify(result).includes('abcdef'));assert.ok(!JSON.stringify(result).includes('uuid'));
});

test('public reviews add display data without changing stored artifacts or exposing the digest', () => {
  const saved = review({ state: 'applied', serviceResult: { source_revision_hash: 'saved', proposal_id: 'proposal' } });
  assert.equal(hasSavedReceipt(saved), true);
  assert.equal(hasSavedReceipt({ ...saved, serviceResult: { source_revision_hash: 'saved', proposal_id: 'different' } }), false);
  assert.equal(hasSavedReceipt({ ...saved, serviceResult: {} }), false);
  const copy = structuredClone(saved), result = publicReview(saved);
  assert.equal(result.presentation.saved, true);assert.equal('artifactDigest' in result, false);assert.deepEqual(saved, copy);
  assert.equal(readableDiagnostic('{"message":"Port a has a width mismatch."}'), 'Port a has a width mismatch.');
  assert.equal(readableDiagnostic({ private_payload: 'hidden' }), 'The changes need attention.');
});

test('progress uses exact operation correlations and needs a saved service receipt', () => {
  const flow = { definition: { id: 'spec2gds.edit_spec' }, nodes: [
    { id: 'context', kind: 'call', operationId: 'read', attempt: 1, state: 'succeeded' },
    { id: 'validated', kind: 'call', operationId: 'validate', attempt: 1, state: 'succeeded' },
    { id: 'submit_content', kind: 'call', operationId: 'operation', attempt: 1, state: 'succeeded', output: { proposal_id: 'proposal' } },
  ] } as any;
  const prepared = review({ preview: { diff: [{ label: 'Adder › Port a width', before: 4, after: 8, change: 'changed' }] } });
  const unrelated = review({ proposalId: 'unrelated', callId: 'other' });
  const progress = flowPresentation(flow, [prepared, unrelated], 'Adder');
  assert.equal(progress.items[0]?.label, 'Reading Adder');assert.deepEqual(progress.proposalIds, ['proposal']);
  assert.deepEqual(progress.reviewReferences, [{ proposalId: 'proposal', sessionId: 'conversation', version: 1 }]);
  assert.equal(progress.items.at(-1)?.state, 'checked');assert.ok(!progress.items.some(item => item.state === 'saved'));
  const applied = { ...prepared, state: 'applied' as const, serviceResult: { source_revision_hash: 'saved' } };
  assert.equal(flowPresentation(flow, [applied]).items.at(-1)?.label, 'Changes saved');
  assert.ok(!flowPresentation(flow, [{ ...applied, serviceResult: {} }]).items.some(item => item.state === 'saved'));
  assert.equal(flowPresentation(flow, [{ ...prepared, state: 'stale' }]).items.at(-1)?.state, 'failed');
  const waiting = { ...flow, nodes: [{ id: 'saved', kind: 'wait', attempt: 1, operationId: 'wait', state: 'waiting' }] };
  assert.equal(flowPresentation({ ...waiting, status: 'paused' }, []).items[0]?.state, 'paused');
  assert.equal(flowPresentation({ ...waiting, status: 'cancelled' }, []).items[0]?.state, 'cancelled');
});

test('flow review replay follows revision descendants and excludes newer unrelated flows', () => {
  const root = { id: 'root', createdAt: 1 } as any;
  const child = { id: 'child', parentExecutionId: 'root', createdAt: 2 } as any;
  const grandchild = { id: 'grandchild', parentExecutionId: 'child', createdAt: 3 } as any;
  const other = { id: 'unrelated', createdAt: 4 } as any;
  const list = [other, grandchild, root, child];
  assert.deepEqual(relatedFlowViews(root, list).map(flow => flow.id), ['root', 'child', 'grandchild']);
  assert.deepEqual(list.map(flow => flow.id), ['unrelated', 'grandchild', 'root', 'child']);
});
