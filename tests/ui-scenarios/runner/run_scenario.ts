/** Isolated integration scenarios; run separately from non-UI acceptance. */
import assert from "node:assert/strict";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { createWriteStream, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, cpSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect, type Page } from "@playwright/test";
import { modelFixture } from "./model_fixture.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.PLAYWRIGHT_BROWSERS_PATH || join(root, "circuit-designer/.playwright-browsers");
const args = process.argv.slice(2);
function option(name: string, fallback: string): string {
  const index = args.indexOf(name);
  if (index < 0) return fallback;
  const value = args[index + 1];
  if (!value || value.startsWith("--")) throw new Error(`${name} needs a value`);
  return value;
}
const scenario = option("--scenario", "automatic");
assert.ok(["automatic", "restricted", "live", "binding", "repeated"].includes(scenario), "Unknown named scenario");
const approval = option("--approval-mode", scenario === "restricted" ? "review" : "automatic");
assert.equal(approval, scenario === "restricted" ? "review" : "automatic", "Scenario requires its matching approval mode");
const liveModel = args.includes("--live-model");
if (liveModel && !process.env.OPENAI_API_KEY) throw new Error("Live smoke requires OPENAI_API_KEY; deterministic runs do not.");
const runId = new Date().toISOString().replace(/[:.]/g, "-");
const output = resolve(option("--output", join(root, "tests/ui-scenarios/results", `${scenario}-${runId}`)));
mkdirSync(output, { recursive: true });
const isolated = mkdtempSync(join(tmpdir(), "spec2gds-ui-"));
const documentId = `scenario_${Date.now()}`;
const packagePath = join(isolated, "packages", `${documentId}.spec`);
mkdirSync(dirname(packagePath), { recursive: true });
const children = new Set<ChildProcess>();
const failures: any[] = [], records: any[] = [];
let stopping = false;

async function freePort(): Promise<number> {
  const server = createServer(); server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); assert.ok(address && typeof address === "object");
  await new Promise<void>(done => server.close(() => done())); return address.port;
}
function start(name: string, command: string, argv: string[], cwd: string, env: NodeJS.ProcessEnv): ChildProcess {
  const log = createWriteStream(join(output, `${name}.log`), { flags: "a" });
  const child = spawn(command, argv, { cwd, env, detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"] });
  children.add(child); child.stdout?.pipe(log, { end: false }); child.stderr?.pipe(log, { end: false });
  child.on("error", error => failures.push({ type: "process", name, error: String(error) }));
  child.on("exit", () => log.end()); return child;
}
async function stop(child: ChildProcess): Promise<void> {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
  const exited = once(child, "exit");
  const signal = (value: NodeJS.Signals) => {
    try { if (process.platform === "win32") child.kill(value); else process.kill(-child.pid!, value); }
    catch (error: any) { if (error.code !== "ESRCH") throw error; }
  };
  signal("SIGTERM"); const timer = setTimeout(() => signal("SIGKILL"), 5_000);
  try { await exited; } finally { clearTimeout(timer); children.delete(child); }
}
for (const signal of ["SIGINT", "SIGTERM"] as const) process.once(signal, () => {
  stopping = true; void Promise.all([...children].map(stop)).finally(() => { process.exitCode = 1; });
});
async function json(url: string, body?: unknown): Promise<any> {
  const response = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(`${response.status} ${url}: ${JSON.stringify(value)}`);
  return value;
}
async function healthy(url: string, child: ChildProcess): Promise<void> {
  await expect.poll(async () => {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Service stopped before readiness: ${url}`);
    try { return (await fetch(url)).ok; } catch { return false; }
  }, { timeout: 120_000 }).toBe(true);
}
async function openEditor(page: Page, owner: string, path: string): Promise<void> {
  if (page.url() === "about:blank") await page.goto(`${owner}/editor`);
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Open Specification/ }).click();
  await page.getByLabel("Server-local package path").fill(path);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator(".spec-paper")).toBeVisible();
}
async function prompt(page: Page, message: string): Promise<void> {
  const input = page.locator("textarea, [contenteditable='true']").first();
  await expect(input).toBeVisible({ timeout: 30_000 });
  await input.fill(message);
  const send = page.getByRole("button", { name: "Send message", exact: true });
  await expect(send).toBeEnabled({ timeout: 10_000 });
  await send.click();
}
function savedSnapshot(path: string): any {
  const saved = spawnSync("uv", ["run", "--project", root, "python", "-c",
    "import json,sys; from spec2gds.agent_spec.spec_format.v1_api import V1Session,_snapshot; print(json.dumps(_snapshot(V1Session(sys.argv[1]))))", path], { cwd: root, encoding: "utf8" });
  assert.equal(saved.status, 0, saved.stderr); return JSON.parse(saved.stdout);
}

async function run(): Promise<void> {
  // Allocate sequentially so ephemeral ports are distinct within this run.
  const ports = new Set<number>();
  while (ports.size < 4) ports.add(await freePort());
  const [ownerPort, assistantPort, circuitPort, circuitUiPort] = [...ports];
  const owner = `http://127.0.0.1:${ownerPort}`, assistant = `http://127.0.0.1:${assistantPort}`;
  const config = JSON.parse(readFileSync(join(root, "config/services.json"), "utf8"));
  config.public_host = "127.0.0.1";
  for (const [name, port, uiPort] of [["spec_editor", ownerPort, ownerPort], ["ai_assistant", assistantPort, assistantPort], ["circuit_designer", circuitPort, circuitUiPort]] as const) {
    config[name].service.host = config[name].ui.host = "127.0.0.1";
    config[name].service.port = port; config[name].ui.port = uiPort;
  }
  config.logging.enabled = false; config.logging.file = join(isolated, "events.jsonl");
  config.activities.workspace_root = join(isolated, "generated");
  config.circuit_designer.preferences_file = join(isolated, "circuit-preferences.json");
  const configPath = join(isolated, "services.json"); writeFileSync(configPath, JSON.stringify(config));
  const fixture = liveModel ? null : await modelFixture(documentId);
  const env = { ...process.env, SPEC2GDS_SERVICE_CONFIG: configPath, SPEC2GDS_PUBLIC_HOST: "127.0.0.1",
    SPEC_EDITOR_STATE_ROOT: join(isolated, "owner-state"), ASSISTANT_STATE: join(isolated, "assistant-state"),
    SPEC2GDS_SCRATCH_ROOT: join(isolated, "workspaces"), SPEC_DOCUMENT_ROOT: dirname(packagePath),
    ASSISTANT_HOST: "127.0.0.1", ASSISTANT_PORT: String(assistantPort), ASSISTANT_PROFILE: "spec2gds-web",
    SPEC_SERVICE_ALLOWLIST: owner, CIRCUIT_SERVICE_ALLOWLIST: `http://127.0.0.1:${circuitPort}/api/circuit-designer/v1`,
    SPEC2GDS_SESSION_COMPRESSION: "none", ASSISTANT_MAX_STEPS_PER_TURN: "5",
    ...(fixture ? { OPENAI_API_KEY: "local-fixture", OPENAI_BASE_URL: fixture.url, OPENAI_MODEL: "gpt-4o-mini" } : {}) };
  const ownerArgs = ["run", "spec2gds-server", "--host", "127.0.0.1", "--port", String(ownerPort), ...(approval === "review" ? ["--require-human-approval"] : [])];
  let ownerProcess = start("owner", "uv", ownerArgs, root, env);
  const assistantProcess = start("assistant", process.execPath, ["scripts/dev.mjs", "--no-open"], join(root, "ai-assistant"), env);
  let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined;
  try {
    await Promise.all([healthy(`${owner}/health`, ownerProcess), healthy(`${assistant}/readyz`, assistantProcess)]);
    assert.equal((await json(`${owner}/assistant/capabilities`)).approval_policy, approval);
    if (!process.env.PLAYWRIGHT_BROWSERS_PATH) process.env.PLAYWRIGHT_BROWSERS_PATH = join(root, "circuit-designer/.playwright-browsers");
    browser = await chromium.launch({ headless: !args.includes("--headed"), args: ["--no-sandbox"] });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    const chat = await context.newPage(), editor = await context.newPage();
    const confirmations: string[] = [];
    for (const page of [chat, editor]) {
      page.setDefaultTimeout(60_000);
      page.on("pageerror", error => failures.push({ type: "pageerror", message: String(error) }));
      page.on("dialog", dialog => {
        failures.push({ type: "dialog", message: dialog.message() });
        void dialog.dismiss();
      });
      page.on("console", message => {
        if (message.type() !== "error") return;
        const url = message.location().url;
        const expected = (stopping && url.startsWith(owner) && /\/(events|activity-events|documents\/view)(?:\?|$)/.test(url))
          || (scenario === "live" && url.startsWith(owner) && /\/transactions(?:\?|$)/.test(url) && message.text().includes("409"));
        failures.push({ type: "console", message: message.text(), url, expected });
      });
      page.on("requestfailed", request => {
        const url = request.url(), message = request.failure()?.errorText ?? "";
        const expected = (stopping && url.startsWith(owner) && /\/(events|activity-events|documents\/view)(?:\?|$)/.test(url))
          || (/\/(events|activity-events)(?:\?|$)/.test(url) && /ERR_ABORTED|AbortError/.test(message));
        failures.push({ type: "network", url, message, expected });
      });
    }
    await chat.exposeFunction("recordConfirmation", (text: string) => confirmations.push(text));
    await chat.addInitScript(() => document.addEventListener("click", event => {
      const target = (event.target as Element).closest("button");
      if (target && /Approve and apply|Continue proposal|Create specification and continue/.test(target.textContent ?? "")) void (window as any).recordConfirmation(target.textContent);
    }));
    try {
      let initial: any;
      if (scenario === "automatic") {
        await chat.goto(`${assistant}/launch`);
        await chat.waitForFunction(() => (document.documentElement as any).dataset.spec2gdsLaunchStatus === "ready", null, { timeout: 30_000 });
        await prompt(chat, `Create a new spec document ${documentId} titled Iterative scenario. Add timer_core with entity ID component_timer_core, scalar clk and rst_n inputs, an 8-bit irq output, and module body assign irq = {8{clk & rst_n}};`);
        await expect.poll(() => existsSync(packagePath), { timeout: 30_000 }).toBe(true);
        initial = await json(`${owner}/documents/snapshot`);
      } else {
        initial = await json(`${owner}/documents/create`, { path: packagePath, document_id: documentId, title: "Iterative scenario" });
        const query = new URLSearchParams({ service_base_url: owner, document_id: documentId, owner_document_key: initial.owner_document_key });
        await chat.goto(`${assistant}/launch/spec-document?${query}`);
        await chat.waitForFunction(() => (document.documentElement as any).dataset.spec2gdsLaunchStatus === "ready", null, { timeout: 30_000 });
        await expect(chat.getByRole("button", { name: "Choose workspace" })).toContainText(documentId, { timeout: 30_000 });
        await prompt(chat, "Create timer_core with entity ID component_timer_core, scalar clk and rst_n inputs, an 8-bit irq output, and assign irq = {8{clk & rst_n}};");
      }
      const key = initial.owner_document_key;
      const scoped = (path: string) => `${owner}${path}${path.includes("?") ? "&" : "?"}owner_document_key=${encodeURIComponent(key)}`;
      const snapshot = () => json(scoped("/documents/snapshot"));
      const history = () => json(scoped("/assistant/history?limit=25"));
      if (scenario === "restricted") {
        await chat.getByRole("button", { name: "Continue proposal", exact: true }).click();
        await expect(chat.getByRole("button", { name: "Approve and apply", exact: true })).toBeVisible({ timeout: 30_000 });
        assert.equal((await snapshot()).source_revision_hash, initial.source_revision_hash);
        await chat.getByRole("button", { name: "Approve and apply", exact: true }).click();
      }
      await expect.poll(async () => (await snapshot()).components.map((item: any) => item.ref.entity_id), { timeout: 30_000 }).toEqual(["component_timer_core"]);
      if (approval === "automatic") await expect(chat.getByText("Applied automatically", { exact: true }).last()).toBeVisible();
      let current = await snapshot(); records.push({ snapshot: current, history: await history() });
      await openEditor(editor, owner, packagePath);
      await expect(editor.locator("#component-component_timer_core, #component-component-timer-core")).toBeVisible();
      assert.equal(current.components[0].ports.find((port: any) => port.name === "irq").range, "7:0");
      assert.equal(current.entity_sections[0].content, "assign irq = {8{clk & rst_n}};");
      if (scenario === "restricted") {
        await prompt(chat, "Refine irq to 16 bits.");
        await expect.poll(async () => (await history()).items.length, { timeout: 30_000 }).toBe(2);
        const pending = (await history()).items[0];
        await json(scoped(`/assistant/proposals/${pending.proposal_id}/reject`), {});
        assert.equal((await snapshot()).source_revision_hash, current.source_revision_hash);
        await prompt(chat, "Refine irq to 16 bits again.");
        await expect.poll(async () => (await history()).items.length, { timeout: 30_000 }).toBe(3);
        const stale = (await history()).items[0];
        await json(scoped("/transactions"), { expected_source_revision_hash: current.source_revision_hash, operations: [{ type: "set_document_title", title: "Human revision" }] });
        const response = await fetch(scoped(`/assistant/proposals/${stale.proposal_id}/approve`), { method: "POST" });
        assert.equal(response.status, 409);
      } else {
        if (scenario === "live") {
          const component = editor.locator("#component-component_timer_core, #component-component-timer-core");
          await component.getByRole("button", { name: "Options" }).click();
          await component.getByRole("menuitem", { name: "Edit text…" }).click();
          await component.getByLabel("Specification text").fill("Preserve this exact draft.");
        }
        let bKey: string | undefined;
        if (scenario === "binding") {
          const copied = join(isolated, "packages", "copied.spec"); cpSync(packagePath, copied);
          const b = await json(`${owner}/documents/open`, { path: copied }); bKey = b.owner_document_key;
          assert.notEqual(key, bKey); await openEditor(editor, owner, copied);
        }
        await prompt(chat, "Refine timer_core irq to 16 bits and update its module body to assign irq = {16{clk & rst_n}};");
        await expect.poll(async () => (await snapshot()).components[0].ports.find((port: any) => port.name === "irq").range, { timeout: 30_000 }).toBe("15:0");
        current = await snapshot(); assert.equal(current.entity_sections[0].content, "assign irq = {16{clk & rst_n}};");
        if (scenario === "live") {
          const component = editor.locator("#component-component_timer_core, #component-component-timer-core");
          await expect(component.getByLabel("Specification text")).toHaveValue("Preserve this exact draft.");
          await expect(editor.getByText(/Saved updates are pending/)).toBeVisible();
          await component.getByRole("button", { name: "Save changes" }).click();
          await expect(component.getByRole("alert")).toContainText("preserved draft");
          await component.getByRole("button", { name: "Cancel", exact: true }).click();
          await expect(editor.locator(".spec-paper")).toContainText("15:0", { timeout: 5_000 });
        } else if (scenario === "binding") {
          assert.equal((await json(`${owner}/documents/snapshot?owner_document_key=${bKey}`)).components[0].ports.find((port: any) => port.name === "irq").range, "7:0");
          await expect(editor.locator(".spec-paper")).toContainText("7:0");
          stopping = true; await stop(ownerProcess);
          ownerProcess = start("owner", "uv", ownerArgs, root, env);
          await healthy(`${owner}/health`, ownerProcess); stopping = false;
          assert.equal((await snapshot()).source_revision_hash, current.source_revision_hash);
          await openEditor(editor, owner, packagePath);
          await expect(editor.locator(".spec-paper")).toContainText("15:0", { timeout: 5_000 });
        } else await expect(editor.locator(".spec-paper")).toContainText("15:0", { timeout: 5_000 });
        if (scenario === "repeated") {
          for (let index = 2; index < 100; index++) {
            current = await snapshot();
            const artifact = { proposal_id: `iteration_${index}`, document_id: documentId, scope: "document", target: null,
              base_source_revision_hash: current.source_revision_hash, title: `Iteration ${index}`, summary: `Iteration ${index}`, rationale: "Repeated refinement", assumptions: [],
              operations: [{ operation_id: "metadata", type: "set_entity_metadata", entity: current.components[0].ref, description: `Iteration ${index}` }] };
            const first = await json(scoped("/assistant/proposals/submit"), artifact);
            assert.equal((await json(scoped("/assistant/proposals/submit"), artifact)).source_revision_hash, first.source_revision_hash);
          }
          let count = 0, before: number | null = null;
          do { const page = await json(scoped(`/assistant/history?limit=25${before === null ? "" : `&before=${before}`}`)); count += page.items.length; before = page.next_cursor; } while (before !== null);
          assert.equal(count, 100);
          await editor.getByRole("button", { name: /Activity/ }).click();
          await expect(editor.getByText("Assistant submission history", { exact: true })).toBeVisible();
          assert.ok(await editor.locator(".activity-item").count() <= 75);
        }
      }
      current = await snapshot(); const disk = savedSnapshot(packagePath);
      assert.equal(disk.source_revision_hash, current.source_revision_hash);
      assert.deepEqual(disk.components, current.components); assert.deepEqual(disk.entity_sections, current.entity_sections);
      records.push({ snapshot: current, history: await history(), disk });
      if (approval === "automatic") assert.deepEqual(confirmations, [], "Automatic workflow must require zero confirmation interactions");
      await chat.screenshot({ path: join(output, "assistant.png"), fullPage: true });
      await editor.screenshot({ path: join(output, "editor.png"), fullPage: true });
      assert.deepEqual(failures.filter(failure => !failure.expected), [], "Unexpected console, page, process, and network failures must fail the scenario");
    } catch (error) {
      await Promise.allSettled([chat.screenshot({ path: join(output, "failed-assistant.png"), fullPage: true }), editor.screenshot({ path: join(output, "failed-editor.png"), fullPage: true })]);
      throw error;
    } finally {
      await context.tracing.stop({ path: join(output, "trace.zip") });
      writeFileSync(join(output, "records.json"), JSON.stringify({ scenario, approval, documentId, records, failures, confirmations }, null, 2));
    }
  } finally {
    await browser?.close(); stopping = true; await Promise.all([...children].map(stop));
    if (fixture) { writeFileSync(join(output, "model-requests.json"), JSON.stringify(fixture.requests, null, 2)); await fixture.close(); }
    if (existsSync(dirname(packagePath))) cpSync(dirname(packagePath), join(output, "packages"), { recursive: true });
    rmSync(isolated, { recursive: true, force: true });
  }
}
await run();
console.log(`Scenario ${scenario} passed. Artifacts: ${output}`);
