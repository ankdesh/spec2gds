/** Real-service teaching captures. No product API responses or model replies are mocked. */
import { chromium, expect, type Page, type Locator } from '@playwright/test';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { createWriteStream, readFileSync, writeFileSync, mkdirSync, existsSync, cpSync } from 'node:fs';
import { resolve, join, dirname, relative } from 'node:path';
import { createServer } from 'node:net';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
const root = resolve(import.meta.dirname, '../../..');
const args = process.argv.slice(2);
const option = (key: string, fallback = '') => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const output = resolve(option('--output'));
if (!relative(root, output).startsWith('temp/TEMP_'))
    throw new Error('Use a repository temp/TEMP_ output.');
const groups = option('--only', 'spec,systemc,catalog,circuit,planner,layouts').split(',');
if (groups.some(name => !['spec', 'systemc', 'catalog', 'circuit', 'planner', 'assistant', 'layouts'].includes(name)))
    throw new Error('Unknown capture group. Use spec, systemc, catalog, circuit, planner, assistant, or layouts.');
const attempt = `take-${Date.now()}`;
const raw = join(output, 'originals', attempt);
mkdirSync(raw, { recursive: true });
const manifestPath = join(output, 'captures.json');
const manifest: any = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : { schema_version: 1, captures: [], runs: [] };
const run: any = { attempt, started_at: new Date().toISOString(), groups, results: [], source_commit: spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim() };
const sourceInputs = spawnSync(join(root, '.venv/bin/python'), ['-c', 'import json; from scripts.capture_tutorials import source_digests; print(json.dumps(source_digests(),separators=(",",":")))'], { cwd: root, encoding: 'utf8' });
if (sourceInputs.status !== 0)
    throw new Error(sourceInputs.stderr);
run.source_digests = JSON.parse(sourceInputs.stdout);
run.source_tree_digest = createHash('sha256').update(JSON.stringify(run.source_digests)).digest('hex');
run.editor_bundle_sha256 = createHash('sha256').update(readFileSync(join(root, 'spec2gds/spec/spec_format/editor_dist/assets/index.js'))).digest('hex');
manifest.runs.push(run);
const save = () => writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
const children: ChildProcess[] = [];
async function port() { const server = createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening'); const value = (server.address() as any).port; await new Promise<void>(r => server.close(() => r())); return value; }
const ports = new Set<number>();
while (ports.size < 6)
    ports.add(await port());
const [sp, cs, cu, vp, ca, ap] = [...ports];
const spec = `http://127.0.0.1:${sp}`, circuit = `http://127.0.0.1:${cu}`, planner = `http://127.0.0.1:${vp}`, assistant = `http://127.0.0.1:${ap}`;
const config = JSON.parse(readFileSync(join(root, 'config/services.json'), 'utf8'));
for (const [name, a, b] of [['spec_editor', sp, sp], ['circuit_designer', cs, cu], ['verification_planner', vp, vp], ['spec_catalog', ca, ca], ['ai_assistant', ap, ap]] as const) {
    Object.assign(config[name].service, { host: '127.0.0.1', port: a });
    Object.assign(config[name].ui, { host: '127.0.0.1', port: b });
}
const originalStarts = resolve(option('--starts'));
if (!relative(root, originalStarts).startsWith('temp/TEMP_') || !existsSync(join(originalStarts, 'starts.json')))
    throw new Error('Provide a complete prepared --starts directory under repository temp/TEMP_.');
const state = join(output, 'environment', attempt);
mkdirSync(state, { recursive: true });
const documents = join(state, 'documents');
const starts = join(documents, 'starts');
if (!existsSync(starts))
    cpSync(originalStarts, starts, { recursive: true });
config.public_host = '127.0.0.1';
config.spec_editor.spec_root = documents;
config.logging = { ...config.logging, enabled: false, file: join(output, 'events.jsonl') };
config.activities.scratch_root = join(output, 'generated');
config.activities.extension_modules = [];
config.circuit_designer.preferences_file = join(output, 'preferences.json');
config.spec_catalog.catalog_root = join(root, 'spec_catalog_service/catalog');
config.spec_catalog.state_dir = join(output, 'catalog-state');
const registry = join(output, 'services.json');
writeFileSync(registry, JSON.stringify(config, null, 2));
mkdirSync(join(output, 'scratch'), { recursive: true });
const env = { ...process.env, SPEC_EDITOR_STATE_ROOT: join(state, 'spec-state'), SPEC_DOCUMENT_ROOT: output, ASSISTANT_STATE: join(state, 'assistant-state'), SPEC2GDS_SCRATCH_ROOT: join(output, 'scratch'), TMPDIR: join(output, 'scratch'), TMP: join(output, 'scratch'), TEMP: join(output, 'scratch'), ASSISTANT_MAX_STEPS_PER_TURN: '10' };
Object.assign(process.env, { TMPDIR: env.TMPDIR, TMP: env.TMP, TEMP: env.TEMP });
async function start(name: string, cmd: string, argv: string[], cwd: string, health: string) { const stream = createWriteStream(join(output, `${attempt}-${name}.log`)); const child = spawn(cmd, argv, { cwd, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] }); children.push(child); const secrets = Object.entries(env).filter(([key, value]) => /KEY|TOKEN|SECRET|PASSWORD/i.test(key) && typeof value === 'string' && value.length > 6).map(([, value]) => value as string);
    const redact = (line: string) => secrets.reduce((text, secret) => text.replaceAll(secret, '[REDACTED]'), line).replace(/([?&]token=)[^\s&#]+/g, '$1[REDACTED]');
    for (const source of [child.stdout, child.stderr]) {
        let pending = '';
        source?.setEncoding('utf8');
        source?.on('data', (chunk: string) => {
            pending += chunk;
            const lines = pending.split('\n');
            pending = lines.pop()!;
            for (const line of lines) stream.write(redact(line) + '\n');
        });
        source?.on('end', () => { if (pending) stream.write(redact(pending)); });
    } child.on('error', error => { run.results.push({ service: name, error: String(error) }); save(); }); await expect.poll(async () => { if (child.exitCode !== null)
    throw new Error(`${name} stopped: ${child.exitCode}`); try {
    return (await fetch(health)).ok;
}
catch {
    return false;
} }, { timeout: 60000 }).toBe(true); return child; }
let selected: any;
async function api(path: string, body?: any) { const url = new URL(path, spec); if (selected && !url.searchParams.has('owner_document_key'))
    url.searchParams.set('owner_document_key', selected.owner_document_key); const edit = selected?.edit_access; const res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(edit ? { 'X-Spec-Edit-Context': edit.context_id, 'X-Spec-Participant': edit.participant_id } : {}) }, ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) }) }); const value = await res.json(); if (!res.ok)
    throw new Error(`${path}: ${res.status} ${JSON.stringify(value)}`); if (value.owner_document_key && value.edit_access)
    selected = value; return value; }
async function snapshot() { return api('/documents/snapshot'); }
async function commit(operations: any[]) { const before = await snapshot(); return api('/transactions', { expected_source_revision_hash: before.source_revision_hash, operations }); }
async function capture(page: Page, name: string, area: string, target?: Locator) { await page.evaluate(() => document.fonts.ready); if (target)
    await target.scrollIntoViewIfNeeded(); const file = join(raw, `${name}.jpg`); await page.screenshot({ path: file, type: 'jpeg', quality: 90, fullPage: false, animations: 'disabled' }); const source = selected ? await snapshot() : null; const htmlTheme = await page.locator('html').getAttribute('data-theme'); const appTheme = !htmlTheme ? await page.evaluate(() => document.querySelector('[data-theme]')?.getAttribute('data-theme') || null) : null; const record = { name, file: relative(output, file), app: area, attempt, viewport: page.viewportSize(), theme: htmlTheme || appTheme || null, captured_at: new Date().toISOString(), source_commit: run.source_commit, source_tree_digest: run.source_tree_digest, editor_bundle_sha256: run.editor_bundle_sha256, document_id: source?.document_id, source_revision: source?.source_revision_hash, sha256: createHash('sha256').update(readFileSync(file)).digest('hex'), model_provenance: area === 'AI Assistant' ? 'live' : null }; manifest.captures = manifest.captures.filter((x: any) => x.name !== name); manifest.captures.push(record); save(); console.log(`Captured ${name}`); }
async function open(page: Page, key: string) { selected = await api('/documents/open', { path: join(starts, `${key}-start.spec`) }); await page.goto(`${spec}/editor?owner_document_key=${encodeURIComponent(selected.owner_document_key)}&edit_context_id=${encodeURIComponent(selected.edit_access.context_id)}`); await expect(page.locator('.spec-paper')).toBeVisible(); if (await page.locator('html').getAttribute('data-theme') !== 'obsidian')
    await page.getByRole('button', { name: /Switch theme/ }).click(); }
const component = (page: Page, id = 'add16') => page.locator(`#component-${id.replaceAll('_', '-')}`);
async function options(area: Locator, label: string) { await area.getByRole('button', { name: 'Options', exact: true }).click(); await area.getByRole('menuitem', { name: label, exact: true }).click(); }
async function cmenu(page: Page, menu: string, label: string) { await page.getByRole('menuitem', { name: menu, exact: true }).click(); await page.getByRole('menuitem', { name: label, exact: true }).click(); }
async function verify(page: Page, id = 'add16') { await options(component(page, id), 'Verify Component'); await expect(page.locator('.app-toast').last()).toContainText(/Lint (passed|failed)|Not verified/, { timeout: 60000 }); }
async function closePanel(page: Page) { const close = page.getByRole('button', { name: 'Close side panel', exact: true }); if (await close.isVisible())
    await close.click(); }
async function editSV(page: Page, text: string) { const section = component(page).locator('.spec-sv-section'); await section.getByRole('button', { name: 'Options for SystemVerilog', exact: true }).click(); await section.getByRole('menuitem', { name: 'Edit', exact: true }).click(); await section.locator('.cm-content').fill(text); await section.getByRole('button', { name: 'Save to Spec', exact: true }).click(); await expect(section.locator('.spec-sv-source')).toContainText(text); }
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, colorScheme: 'dark', acceptDownloads: true });
await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
const page = await context.newPage();
page.setDefaultTimeout(20000);
let errors = 0;
async function group(name: string, work: () => Promise<void>) { if (!groups.includes(name))
    return; try {
    await work();
    run.results.push({ group: name, status: 'passed' });
}
catch (error) {
    errors++;
    run.results.push({ group: name, status: 'failed', error: String(error), stack: (error as Error).stack });
    await page.screenshot({ path: join(raw, `failure-${name}.png`), fullPage: true }).catch(() => { });
    console.error(`${name}: ${error}`);
} save(); }
try {
    await start('spec', join(root, '.venv/bin/spec2gds-spec-service'), ['--service-config', registry], root, `${spec}/health`);
    await group('spec', async () => {
        await page.goto(spec);
        if (await page.locator('html').getAttribute('data-theme') !== 'obsidian')
            await page.getByRole('button', { name: /Switch theme/ }).click();
        await page.getByRole('menuitem', { name: 'File', exact: true }).click();
        await page.getByRole('menuitem', { name: /New Spec/ }).click();
        await page.getByLabel('Spec name', { exact: true }).fill('My registered adder');
        await page.getByText('More options', { exact: true }).click();
        await page.getByLabel('File path', { exact: true }).fill(join(documents, 'my-adder.spec'));
        await capture(page, 'spec-new', 'Spec Editor');
        const created = page.waitForResponse(r => r.url().includes('/documents/create') && r.request().method() === 'POST');
        await page.getByRole('button', { name: 'Create Spec', exact: true }).click();
        selected = await (await created).json();
        await expect(page.locator('.spec-paper')).toBeVisible();
        await capture(page, 'spec-cover', 'Spec Editor');
        await page.getByRole('menuitem', { name: 'File', exact: true }).click();
        await page.getByRole('menuitem', { name: /Open Spec/ }).click();
        await capture(page, 'spec-open', 'Spec Editor');
        await page.getByRole('button', { name: 'Cancel', exact: true }).click();
        await open(page, '02');
        await commit([{ type: 'create_entity', kind: 'component', name: '16-bit modulo adder', entity_id: 'add16' }]);
        await page.reload();
        const comp = component(page);
        await comp.getByRole('button', { name: 'Options for Ports', exact: true }).click();
        await comp.getByRole('menuitem', { name: 'Add port', exact: true }).click();
        const draft = comp.locator('.spec-port-editor');
        await draft.getByLabel('Port ID', { exact: true }).fill('a');
        await draft.getByLabel('Range', { exact: true }).fill('15-0');
        await draft.getByLabel('Description', { exact: true }).fill('First unsigned operand.');
        await capture(page, 'spec-port-draft', 'Spec Editor', draft);
        await draft.getByRole('button', { name: 'Save to Spec', exact: true }).click();
        await expect(draft.getByLabel('Range', { exact: true })).toBeFocused();
        await expect(draft.getByLabel('Range', { exact: true })).toHaveAttribute('aria-invalid', 'true');
        await capture(page, 'spec-range-error', 'Spec Editor', draft);
        await draft.getByLabel('Range', { exact: true }).fill('15:0');
        await draft.getByRole('button', { name: 'Save and add another', exact: true }).click();
        await expect(draft.getByLabel('Port ID', { exact: true })).toHaveValue('');
        for (const [id, direction, description] of [['b', 'in', 'Second unsigned operand.'], ['y', 'out', 'Unsigned sum, modulo 65536.']]) {
            await draft.getByLabel('Port ID', { exact: true }).fill(id);
            await draft.getByLabel('Direction', { exact: true }).selectOption(direction);
            await draft.getByLabel('Range', { exact: true }).fill('15:0');
            await draft.getByLabel('Description', { exact: true }).fill(description);
            await draft.getByRole('button', { name: id === 'b' ? 'Save and add another' : 'Save to Spec', exact: true }).click();
            if (id === 'b')
                await expect(draft.getByLabel('Port ID', { exact: true })).toHaveValue('');
            else
                await expect(draft).not.toBeVisible();
        }
        expect((await snapshot()).components[0].ports).toHaveLength(3);
        await capture(page, 'spec-ports', 'Spec Editor', comp);
        await open(page, '09');
        const editRow = component(page).locator('.spec-port-row').filter({ has: page.getByRole('rowheader', { name: 'a', exact: true }) });
        await editRow.getByRole('button', { name: 'Options for port a', exact: true }).click();
        await component(page).getByRole('menuitem', { name: 'Edit', exact: true }).click();
        const challenge = component(page).locator('.spec-port-editor');
        await challenge.getByLabel('Description', { exact: true }).fill('First unsigned 16-bit operand.');
        await challenge.getByLabel('Range', { exact: true }).fill('15-0');
        await challenge.getByRole('button', { name: 'Save to Spec', exact: true }).click();
        await expect(challenge.getByLabel('Range', { exact: true })).toBeFocused();
        await capture(page, 'spec-invalid', 'Spec Editor', challenge);
        await challenge.getByLabel('Range', { exact: true }).fill('15:0');
        await challenge.getByRole('button', { name: 'Save to Spec', exact: true }).click();
        await expect(challenge).not.toBeVisible();
        await capture(page, 'spec-port-description', 'Spec Editor', component(page));
        const challengeRevision = (await snapshot()).source_revision_hash;
        await open(page, '09');
        expect((await snapshot()).source_revision_hash).toBe(challengeRevision);
        expect((await snapshot()).designs[0].connections).toHaveLength(7);
        await open(page, 'diagnostics');
        await capture(page, 'spec-sv', 'Spec Editor', component(page).locator('.spec-sv-section'));
        await verify(page);
        await expect(page.locator('.utility-sidebar')).toHaveCount(0);
        await capture(page, 'spec-notification', 'Spec Editor', component(page));
        await page.locator('#editor-diagnostics-trigger').click();
        await expect(page.locator('.diagnostics-panel')).toContainText('Lint passed');
        await page.locator('.diagnostic-target summary').filter({ hasText: 'Technical details' }).click();
        await capture(page, 'spec-verified', 'Spec Editor');
        await closePanel(page);
        const preview = component(page).locator('.spec-topology-card');
        await expect(preview.locator('img')).toBeVisible();
        await capture(page, 'spec-preview', 'Spec Editor', preview);
        await preview.getByRole('button', { name: 'Options for circuit preview', exact: true }).click();
        await preview.getByRole('menuitem', { name: 'Expand', exact: true }).click();
        await capture(page, 'spec-preview-expanded', 'Spec Editor');
        await page.keyboard.press('Escape');
        await editSV(page, 'assign y = ;');
        await verify(page);
        await page.locator('#editor-diagnostics-trigger').click();
        await expect(page.locator('.diagnostics-panel')).toContainText('Lint failed');
        await capture(page, 'spec-failed', 'Spec Editor');
        await page.getByRole('button', { name: 'Go to source', exact: true }).first().click();
        await capture(page, 'spec-source', 'Spec Editor', component(page).locator('.spec-sv-section'));
        await closePanel(page);
        await editSV(page, 'assign y = a + b;');
        await page.locator('#editor-diagnostics-trigger').click();
        await expect(page.locator('.diagnostics-panel')).toContainText('Out of date');
        await capture(page, 'spec-stale', 'Spec Editor');
        await closePanel(page);
        await verify(page);
        await page.locator('#editor-diagnostics-trigger').click();
        await expect(page.locator('.diagnostics-panel')).toContainText('Lint passed');
        await open(page, '05');
        const containing = component(page, 'registered_adder');
        await options(containing, 'Create internal Design…');
        const creation = page.getByRole('dialog', { name: 'Create internal Design', exact: true });
        await creation.getByLabel('Design name', { exact: true }).fill('Registered adder implementation');
        await creation.getByRole('button', { name: 'Create internal Design', exact: true }).click();
        await expect(creation).toBeHidden();
        const authored = (await snapshot()).designs[0];
        const authoredDesign = page.locator(`#design-${authored.ref.entity_id.replaceAll('_', '-')}`);
        await expect.poll(async () => (await snapshot()).component_compositions.length).toBe(1);
        const definitions = (await snapshot()).components;
        for (const [name, id] of [['u_add', 'add16'], ['u_reg', 'reg16']]) {
            await options(authoredDesign, 'Add component instance…');
            await authoredDesign.getByLabel('Instance ID', { exact: true }).fill(name);
            await authoredDesign.getByLabel('Component', { exact: true }).selectOption(definitions.find((x: any) => x.ref.entity_id === id).vlnv);
            await authoredDesign.getByRole('button', { name: 'Add instance', exact: true }).click();
            await expect(authoredDesign.getByLabel('Instance ID', { exact: true })).toHaveCount(0);
        }
        expect((await snapshot()).designs[0].instances).toHaveLength(2);
        await capture(page, 'spec-composition', 'Spec Editor', containing);
        await capture(page, 'spec-instances', 'Spec Editor', authoredDesign);
        await open(page, 'complete');
        await capture(page, 'spec-register', 'Spec Editor', component(page, 'reg16'));
        const wrapper = component(page, 'registered_adder');
        const settings = wrapper.locator('.spec-hardware-controls > details').filter({ hasText: 'Hardware settings' });
        if (await settings.count())
            await settings.locator('summary').first().click();
        const design = page.locator('#design-registered-adder-impl');
        await expect(design).toBeVisible();
        await options(design, 'Verify Design');
        await expect(page.locator('.app-toast').last()).toContainText('Lint passed', { timeout: 60000 });
        await page.locator('#editor-diagnostics-trigger').click();
        await capture(page, 'spec-design-verified', 'Spec Editor');
        await closePanel(page);
        await options(design, 'Generate RTL');
        await expect.poll(async () => (await api('/executions')).executions.some((x: any) => x.activity_id === 'rtl.generate' && x.status === 'succeeded'), { timeout: 60000 }).toBe(true);
        const generated = (await api('/executions')).executions.find((x: any) => x.activity_id === 'rtl.generate' && x.status === 'succeeded');
        const project = resolve(generated.workspace_output_path);
        expect(relative(state, project).startsWith('..')).toBe(false);
        const projectManifest = JSON.parse(readFileSync(join(project, 'generation-manifest.json'), 'utf8'));
        expect(projectManifest.source_revision_hash).toBe((await snapshot()).source_revision_hash);
        const lint = spawnSync('make', ['lint'], { cwd: project, env, encoding: 'utf8', timeout: 90000 });
        writeFileSync(join(raw, 'generated-rtl-lint.log'), `${lint.stdout || ''}${lint.stderr || ''}`);
        expect(lint.status, 'Lint the actual published tutorial project').toBe(0);
        run.results.push({ check: 'published RTL lint', status: 'passed', project: relative(output, project), source_revision: projectManifest.source_revision_hash });
        await page.locator('#editor-activity-trigger').click();
        await capture(page, 'spec-activity', 'Spec Editor');
        await closePanel(page);
        await options(wrapper, 'Export target details (JSON)');
        await page.locator('#editor-activity-trigger').click();
        await expect(page.getByRole('link', { name: 'Download JSON' })).toBeVisible();
        await capture(page, 'spec-download', 'Spec Editor', page.getByRole('link', { name: 'Download JSON' }));
        const downloadEvent = page.waitForEvent('download');
        await page.getByRole('link', { name: 'Download JSON' }).click();
        const download = await downloadEvent;
        await download.saveAs(join(raw, 'target-details.json'));
        const exported = JSON.parse(readFileSync(join(raw, 'target-details.json'), 'utf8'));
        expect(exported.source_revision_hash).toBe((await snapshot()).source_revision_hash);
    });
    await group('systemc', async () => {
        await open(page, 'systemc-cycle');
        const design = page.locator('#design-registered-adder-impl');
        await design.getByRole('button', { name: 'Options', exact: true }).click();
        await capture(page, 'systemc-options', 'Spec Editor');
        await page.keyboard.press('Escape');
        await open(page, 'tlm');
        const tlm = page.locator('#design-tlm-practice');
        await capture(page, 'tlm-source', 'Spec Editor', tlm);
        await options(tlm, 'Generate SystemC AT skeleton');
        await expect.poll(async () => (await api('/executions')).executions.some((x: any) => x.status === 'succeeded'), { timeout: 60000 }).toBe(true);
        await page.locator('#editor-activity-trigger').click();
        await capture(page, 'tlm-activity', 'Spec Editor');
    });
    await group('catalog', async () => {
        await start('catalog', join(root, '.venv/bin/spec2gds-catalog-service'), ['--service-config', registry], root, `http://127.0.0.1:${ca}/api/spec-catalog/v1/health`);
        await open(page, 'catalog-reuse');
        const browse = async () => { await options(page.locator('#components'), 'Import from catalog…'); const d = page.getByRole('dialog', { name: 'Component library', exact: true }); await d.getByLabel('Search Components').fill('barrel_shift'); await d.getByRole('button', { name: /barrel_shift/ }).click(); return d; };
        let d = await browse();
        await capture(page, 'catalog-library', 'Spec Editor');
        await d.getByRole('button', { name: 'Review import', exact: true }).click();
        await d.getByRole('button', { name: 'Import into Spec', exact: true }).click();
        await expect(d).not.toBeVisible();
        d = await browse();
        await d.getByLabel('Import as a renamed copy').check();
        await d.getByRole('button', { name: 'Review import', exact: true }).click();
        await d.getByLabel(/Local name for/).first().fill('Local barrel shifter');
        await d.getByRole('button', { name: 'Review import', exact: true }).click();
        await expect(d.getByRole('button', { name: 'Import into Spec', exact: true })).toBeEnabled();
        await capture(page, 'catalog-review', 'Spec Editor');
        await d.getByRole('button', { name: 'Import into Spec', exact: true }).click();
        await expect(d).not.toBeVisible();
        await page.locator('#editor-diagnostics-trigger').click();
        await page.locator('.diagnostics-panel summary').filter({ hasText: 'Catalog evidence' }).click();
        await capture(page, 'catalog-origin', 'Spec Editor');
        expect((await snapshot()).components).toHaveLength(2);
    });
    await group('circuit', async () => {
        await start('circuit', 'npm', ['run', 'service', '--', '--service-config', registry], join(root, 'circuit-designer'), `http://127.0.0.1:${cs}/api/circuit-designer/v1/health`);
        await start('circuit-ui', 'npm', ['run', 'preview:standalone', '--', '--service-config', registry], join(root, 'circuit-designer'), `${circuit}/api/circuit-designer/v1/health`);
        await open(page, '06');
        const snap = await snapshot();
        const launched = await api('/circuit-designer/launch', { entity_kind: 'design', entity_id: snap.designs[0].ref.entity_id });
        const c = await context.newPage();
        await c.goto(launched.editor_url);
        await expect(c.getByTestId('circuit-canvas')).toBeVisible();
        if (await c.locator('.standalone-shell').getAttribute('data-theme') !== 'obsidian') {
            await c.getByRole('button', { name: /Switch theme/ }).click();
        }
        await expect(c.locator('.react-flow__node[data-id^="u_"]')).toHaveCount(2);
        await cmenu(c, 'View', 'Fit circuit');
        await cmenu(c, 'Edit', 'Begin editing');
        await capture(c, 'circuit-edit', 'Circuit Designer');
        const example = JSON.parse(readFileSync(join(root, 'docs/tutorials/example.json'), 'utf8'));
        for (const [name, driver, sink] of example.design.nets) {
            await cmenu(c, 'Connect', 'New connection');
            await c.getByLabel('Net label', { exact: true }).fill(name);
            await c.getByLabel('Endpoint A', { exact: true }).selectOption(driver.startsWith('top.') ? `boundary:${driver.slice(4)}` : driver.replace('.', ':'));
            await c.getByLabel('Endpoint B', { exact: true }).selectOption(sink.startsWith('top.') ? `boundary:${sink.slice(4)}` : sink.replace('.', ':'));
            await c.getByLabel('LSB for A', { exact: true }).fill('0');
            await c.getByLabel('LSB for B', { exact: true }).fill('0');
            await c.getByLabel('Width (0=full)', { exact: true }).fill('0');
            if (name === 'operand_a')
                await capture(c, 'circuit-connect-dialog', 'Circuit Designer');
            await c.getByRole('button', { name: 'Create net', exact: true }).click();
            await expect(c.getByRole('dialog')).not.toBeVisible();
        }
        await c.getByRole('button', { name: 'Save to Spec', exact: true }).click();
        await expect(c.locator('.notice')).toContainText('Changes saved to the source');
        expect((await snapshot()).designs[0].connections).toHaveLength(7);
        await capture(c, 'circuit-connected', 'Circuit Designer');
        await c.getByRole('menuitem', { name: 'File', exact: true }).click();
        await c.getByRole('menuitem', { name: 'Download', exact: true }).hover();
        await expect(c.getByRole('menuitem', { name: 'Download Circuit JSON', exact: true })).toBeVisible();
        await capture(c, 'circuit-download', 'Circuit Designer');
        await c.keyboard.press('Escape');
        await c.keyboard.press('Escape');
        await cmenu(c, 'Edit', 'Begin editing');
        await capture(c, 'circuit-edit-connected', 'Circuit Designer');
        await cmenu(c, 'Timing', 'Clock settings');
        await capture(c, 'circuit-clocks', 'Circuit Designer');
        await c.keyboard.press('Escape');
        await cmenu(c, 'Timing', 'Timing analysis');
        await capture(c, 'circuit-timing', 'Circuit Designer');
        await c.keyboard.press('Escape');
        await c.getByRole('menuitem', { name: 'Components', exact: true }).click();
        await capture(c, 'circuit-proposals', 'Circuit Designer');
        await c.keyboard.press('Escape');
        await c.getByRole('menuitem', { name: 'Edit', exact: true }).click();
        await c.getByRole('menuitem', { name: 'Preferences', exact: true }).hover();
        await c.getByRole('menuitem', { name: 'Actions and shortcuts', exact: true }).click();
        await capture(c, 'circuit-preferences', 'Circuit Designer');
        await c.keyboard.press('Escape');
        await cmenu(c, 'File', 'Cancel changes');
        await c.close();
        await open(page, 'circuit-hierarchy');
        const source = await snapshot();
        const ref = source.components.find((x: any) => x.ref.entity_id === 'registered_adder');
        await commit([{ type: 'create_entity', kind: 'design', name: 'Reuse practice', entity_id: 'reuse_practice', entry_design: true }, { type: 'upsert_instance', design: 'design:reuse_practice', instance: { name: 'u_left', component_vlnv: ref.vlnv } }, { type: 'upsert_instance', design: 'design:reuse_practice', instance: { name: 'u_right', component_vlnv: ref.vlnv } }]);
        const parent = await api('/circuit-designer/launch', { entity_kind: 'design', entity_id: 'reuse_practice' });
        await page.goto(parent.editor_url);
        if (await page.locator('.standalone-shell').getAttribute('data-theme') !== 'obsidian') {
            await page.getByRole('button', { name: /Switch theme/ }).click();
        }
        await expect(page.locator('.react-flow__node')).toHaveCount(2);
        await capture(page, 'circuit-hierarchy', 'Circuit Designer');
    });
    await group('planner', async () => {
        await start('planner', join(root, '.venv/bin/verification-planner'), ['--service-config', registry, '--storage-dir', join(starts, 'verification/planner-data')], root, `${planner}/api/verification/v1/health`);
        const plan = JSON.parse(readFileSync(join(starts, 'verification/starts.json'), 'utf8'));
        await page.goto(planner);
        await page.locator('#btnNewPlan').click();
        await capture(page, 'verification-source', 'Verification Planner');
        await page.keyboard.press('Escape');
        const select = async (key: string) => { await page.goto(planner); await page.locator('#planSelector').selectOption(plan.starts[key].plan_id); await expect(page.locator('#breadcrumbPath')).toHaveText(plan.starts[key].name); };
        await select('plan');
        await page.locator('#btnAddIntent').click();
        await page.locator('#intentFormTitle').fill('Disabled output holds');
        await page.locator('#intentFormSection').selectOption('tutorial-intents');
        await page.locator('#intentAddReqSelect').selectOption('req-hold');
        await page.locator('#intentFormPreconditions').fill('y=16, reset=0, enable=0, a=1, b=2');
        await page.locator('#intentFormTrigger').fill('A rising clk edge');
        await page.locator('#intentFormExpected').fill('y remains 16');
        await page.locator('.obs-name').first().fill('y');
        await page.locator('.obs-desc').first().fill('y remains 16');
        await page.locator('#btnSaveIntentReady').click();
        await expect(page.locator('#modalIntent')).not.toHaveClass(/open/);
        await page.locator('#btnReviewPlanHeader').click();
        await expect(page.locator('#btnConfirmReviewCheckpoint')).toBeEnabled();
        await capture(page, 'verification-plan', 'Verification Planner');
        page.once('dialog', dialog => dialog.accept());
        await page.locator('#btnConfirmReviewCheckpoint').click();
        await expect(page.locator('#modalReview')).not.toHaveClass(/open/);
        await select('coverage');
        await page.locator('[data-layer="coverage"]').click();
        await page.locator('#btnAddObjective').click();
        await page.locator('#objFormTitle').fill('Disabled output holds');
        await page.locator('#objFormFamily').selectOption('correctness');
        await page.locator('#objFormIntent').selectOption('int-hold');
        await page.locator('#objFormDescription').fill('y remains 16 when enable=0');
        await page.locator('#objFormAcceptance').selectOption('pass_verdict');
        await page.locator('#btnSaveObjective').click();
        await expect(page.locator('#modalAddObjective')).not.toHaveClass(/open/);
        await capture(page, 'verification-coverage', 'Verification Planner');
        await page.locator('#btnReviewCoverage').click();
        await expect(page.locator('#btnConfirmReviewCoverage')).toBeEnabled();
        page.once('dialog', dialog => dialog.accept());
        await page.locator('#btnConfirmReviewCoverage').click();
        await expect(page.locator('#modalReviewCoverage')).not.toHaveClass(/open/);
        await select('evidence');
        await page.locator('[data-layer="coverage"]').click();
        await page.locator('#btnImportResults').click();
        await page.locator('#importResultJson').fill(readFileSync(join(starts, 'verification/synthetic-results.json'), 'utf8'));
        await page.locator('#btnStageImportPreview').click();
        await expect(page.locator('#importPreviewBox')).toContainText('Validation Preview');
        await expect(page.locator('#btnCommitImport')).toBeEnabled();
        await capture(page, 'verification-evidence', 'Verification Planner');
        page.once('dialog', dialog => dialog.accept());
        await page.locator('#btnCommitImport').click();
        await expect(page.locator('#modalImportResults')).not.toHaveClass(/open/);
        await select('implementation');
        await page.locator('[data-layer="implementation"]').click();
        await page.locator('#btnSubnavBindings').click();
        await capture(page, 'verification-bindings', 'Verification Planner');
        await page.locator('#btnReviewImplementation').click();
        await expect(page.locator('#btnConfirmReviewImplementation')).toBeEnabled();
        await capture(page, 'verification-implementation', 'Verification Planner');
        page.once('dialog', dialog => dialog.accept());
        await page.locator('#btnConfirmReviewImplementation').click();
        await expect(page.locator('#modalReviewImplementation')).not.toHaveClass(/open/);
        await page.locator('#btnGenerateArtifacts').click();
        await page.locator('#btnRunGenPreview').click();
        await expect(page.locator('#genPreviewFeedback')).toContainText(/reference/i);
        await page.locator('#btnSubmitGeneration').click();
        await expect(page.locator('#genArtifactsList')).toContainText('synthetic-result-template.json');
        await capture(page, 'verification-artifacts', 'Verification Planner');
    });
    await group('assistant', async () => {
        if (!process.env.OPENAI_API_KEY)
            throw new Error('Live Assistant capture requires OPENAI_API_KEY.');
        await start('assistant', process.execPath, ['scripts/dev.mjs', '--service-config', registry, '--no-open'], join(root, 'ai-assistant'), `${assistant}/readyz`);
        await open(page, '04');
        const source = await snapshot();
        const q = new URLSearchParams({ service_base_url: spec, document_id: source.document_id, owner_document_key: source.owner_document_key, edit_context_id: source.edit_access.context_id });
        const a = await context.newPage();
        await a.goto(`${assistant}/launch/spec-document?${q}`);
        await expect(a.locator('html')).toHaveAttribute('data-spec2gds-launch', 'ready', { timeout: 60000 });
        const prompt = readFileSync(join(starts, 'register-prompt.txt'), 'utf8');
        await a.locator('[data-composer-input][contenteditable="true"]').fill(prompt);
        await a.getByRole('button', { name: 'Send message', exact: true }).click();
        const review = a.locator('[data-s2g-architecture-review="pending"]').last();
        await expect(review).toBeVisible({ timeout: 180000 });
        const approve = review.getByRole('button', { name: 'Approve architecture', exact: true });
        await expect(approve).toBeEnabled();
        await approve.evaluate(element => element.scrollIntoView({ block: 'center' }));
        await capture(a, 'assistant-architecture', 'AI Assistant');
        await review.getByRole('button', { name: 'Approve architecture', exact: true }).click();
        await expect.poll(async () => (await snapshot()).components.some((x: any) => x.display_name === 'Enabled 16-bit register'), { timeout: 180000 }).toBe(true);
        const authored = await snapshot();
        const register = authored.components.find((x: any) => x.display_name === 'Enabled 16-bit register');
        const exampleRegister = JSON.parse(readFileSync(join(root, 'docs/tutorials/example.json'), 'utf8')).components.reg16;
        expect(authored.components).toHaveLength(2);
        expect(authored.components.find((x: any) => x.ref.entity_id === 'add16')).toEqual(source.components[0]);
        expect(register.ports.map((x: any) => [x.name, x.direction, x.range || null])).toEqual(exampleRegister.ports.map((x: any[]) => x.slice(0, 3)));
        const body = authored.entity_sections.find((x: any) => x.parent.entity_id === register.ref.entity_id && x.section_type === 'sv').content;
        expect(body.replace(/\s+/g, '')).toBe(exampleRegister.systemverilog.replace(/\s+/g, ''));
        await capture(a, 'assistant-saved', 'AI Assistant');
        await a.close();
        // Restricted content review requires a private restricted Spec process, not a mocked proposal.
        const original = children.find(x => x.spawnargs.includes(join(root, '.venv/bin/spec2gds-spec-service')))!;
        // Close the editor's event stream before waiting for Uvicorn shutdown.
        await page.goto('about:blank');
        const exited = once(original, 'exit');
        process.kill(-original.pid!, 'SIGTERM');
        const stopped = await Promise.race([exited.then(() => true), new Promise<boolean>(done => setTimeout(() => done(false), 5000))]);
        if (!stopped) {
            process.kill(-original.pid!, 'SIGKILL');
            await exited;
        }
        await start('spec-restricted', join(root, '.venv/bin/spec2gds-spec-service'), ['--service-config', registry, '--require-designer-approval'], root, `${spec}/health`);
        await open(page, 'assistant-restricted');
        const restricted = await snapshot();
        const query = new URLSearchParams({ service_base_url: spec, document_id: restricted.document_id, owner_document_key: restricted.owner_document_key, edit_context_id: restricted.edit_access.context_id });
        const b = await context.newPage();
        await b.goto(`${assistant}/launch/spec-document?${query}`);
        await expect(b.locator('html')).toHaveAttribute('data-spec2gds-launch', 'ready', { timeout: 60000 });
        await b.locator('[data-composer-input][contenteditable="true"]').fill('Change only the existing 16-bit modulo adder explanation: append the sentence "Arithmetic wraps modulo 65536." Keep all interfaces, SystemVerilog, other explanations, and connections unchanged. Submit this text-only edit for restricted content review.');
        await b.getByRole('button', { name: 'Send message', exact: true }).click();
        await expect.poll(async () => {
            const pending = b.locator('[data-s2g-architecture-review="pending"]').last();
            if (await pending.isVisible()) {
                await pending.getByRole('button', { name: 'Approve architecture', exact: true }).click();
            }
            return (await api('/documents/view')).activity.pending_review_count;
        }, { timeout: 180000 }).toBeGreaterThan(0);
        await page.locator('#editor-activity-trigger').click();
        await expect(page.getByText('AI Assistant submission history', { exact: true })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Options for Assistant submission', exact: true }).first()).toBeVisible({ timeout: 180000 });
        await capture(page, 'assistant-history', 'Spec Editor');
        await page.getByRole('button', { name: 'Options for Assistant submission', exact: true }).first().click();
        await page.getByRole('menuitem', { name: 'Details and diff', exact: true }).click();
        const diff = page.locator('.utility-sidebar pre').last();
        await expect(diff).toContainText('Arithmetic wraps modulo 65536.');
        await diff.scrollIntoViewIfNeeded();
        await capture(page, 'assistant-review', 'Spec Editor');
        const beforeApproval = await snapshot();
        await page.getByRole('button', { name: 'Options for Assistant submission', exact: true }).first().click();
        await page.getByRole('menuitem', { name: 'Approve', exact: true }).click();
        await expect.poll(async () => (await api('/documents/view')).activity.pending_review_count).toBe(0);
        const afterApproval = await snapshot();
        expect(afterApproval.source_revision_hash).not.toBe(beforeApproval.source_revision_hash);
        expect(afterApproval.designs).toEqual(beforeApproval.designs);
        for (const before of beforeApproval.components) {
            const after = afterApproval.components.find((x: any) => x.ref.entity_id === before.ref.entity_id);
            expect(after.ports).toEqual(before.ports);
        }
        await b.close();
    });
    await group('layouts', async () => {
        await open(page, 'complete');
        for (const theme of ['clean', 'obsidian']) {
            await page.setViewportSize({ width: 1440, height: 900 });
            await closePanel(page);
            if (await page.locator('html').getAttribute('data-theme') !== theme)
                await page.getByRole('button', { name: /Switch theme/ }).click();
            for (const width of [1440, 1280, 1024, 390]) {
                await page.setViewportSize({ width, height: 900 });
                await closePanel(page);
                await capture(page, `layout-${theme}-${width}-closed`, 'Spec Editor', component(page));
                await page.locator('#editor-diagnostics-trigger').click();
                await capture(page, `layout-${theme}-${width}-open`, 'Spec Editor');
            }
        }
        await page.setViewportSize({ width: 1440, height: 900 });
    });
}
finally {
    run.finished_at = new Date().toISOString();
    save();
    await context.tracing.stop({ path: join(raw, 'trace.zip') }).catch(() => { });
    await browser.close();
    for (const child of children.reverse()) {
        if (child.pid)
            try {
                process.kill(-child.pid, 'SIGTERM');
            }
            catch { }
    }
    await Promise.all(children.map(async (c) => { if (c.exitCode === null && c.signalCode === null)
        await Promise.race([once(c, 'exit'), new Promise(r => setTimeout(r, 5000))]); if (c.pid)
        try {
            process.kill(-c.pid, 'SIGKILL');
        }
        catch { } }));
}
process.exitCode = errors ? 1 : 0;
