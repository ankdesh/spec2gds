/**
 * 1080p Playwright Chromium screen recorder against isolated private loopback services.
 * Conforms strictly to repository isolation rules (no /tmp; strictly temp/TEMP_*).
 */
import assert from "node:assert/strict";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { createWriteStream, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = join(root, "circuit-designer/.playwright-browsers");
}
const { chromium, expect } = await import("@playwright/test");

const args = process.argv.slice(2);
function option(name: string, fallback: string): string {
  const idx = args.indexOf(name);
  if (idx < 0) return fallback;
  const val = args[idx + 1];
  if (!val || val.startsWith("--")) throw new Error(`${name} requires a value`);
  return val;
}

const episodeId = option("--episode", "pilot");
const outputDir = resolve(
  option("--output", join(root, "temp/TEMP_tutorial_videos/run-direct"))
);
const dryRun = args.includes("--dry-run");

console.log(`[Recorder] Episode: ${episodeId}`);
console.log(`[Recorder] Target output: ${outputDir}`);

if (dryRun) {
  console.log("[Recorder] Dry-run enabled. Skipping browser launch and service execution.");
  process.exit(0);
}

// Ensure isolated directories inside temp/TEMP_*
const envDir = join(outputDir, "environment", episodeId);
const rawDir = join(outputDir, "originals", episodeId);
const startsDir = join(outputDir, "starts", episodeId);
rmSync(envDir, { recursive: true, force: true });
mkdirSync(envDir, { recursive: true });
mkdirSync(rawDir, { recursive: true });
rmSync(startsDir, { recursive: true, force: true });
mkdirSync(startsDir, { recursive: true });

const children = new Set<ChildProcess>();
let stopping = false;

async function freePort(): Promise<number> {
  const server = createServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address === "object");
  await new Promise<void>((done) => server.close(() => done()));
  return address.port;
}

function startProcess(
  name: string,
  command: string,
  argv: string[],
  cwd: string,
  env: NodeJS.ProcessEnv
): ChildProcess {
  const logStream = createWriteStream(join(envDir, `${name}.log`), { flags: "a" });
  const child = spawn(command, argv, {
    cwd,
    env,
    detached: process.platform !== "win32",
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.add(child);
  child.stdout?.pipe(logStream, { end: false });
  child.stderr?.pipe(logStream, { end: false });
  child.on("exit", () => logStream.end());
  return child;
}

async function stopProcess(child: ChildProcess): Promise<void> {
  if (!child.pid) return;
  const signal = (value: NodeJS.Signals) => {
    try {
      if (process.platform === "win32") child.kill(value);
      else process.kill(-child.pid!, value);
    } catch (e: any) {
      if (e.code !== "ESRCH") throw e;
    }
  };
  if (child.exitCode !== null || child.signalCode !== null) {
    children.delete(child);
    return;
  }
  const exited = once(child, "exit");
  signal("SIGTERM");
  const timer = setTimeout(() => signal("SIGKILL"), 5_000);
  try {
    await exited;
  } finally {
    clearTimeout(timer);
    signal("SIGKILL");
    children.delete(child);
  }
}

for (const sig of ["SIGINT", "SIGTERM"] as const) {
  process.once(sig, () => {
    stopping = true;
    void Promise.all([...children].map(stopProcess)).finally(() => {
      process.exit(1);
    });
  });
}

async function waitForHealth(url: string, child: ChildProcess, timeoutMs = 60_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`Service exited prematurely before healthy at ${url}`);
    }
    try {
      const resp = await fetch(url);
      if (resp.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`Timed out waiting for health check at ${url}`);
}

async function createNewSpec(page: Page, title: string = "Registered adder"): Promise<void> {
  if (await page.getByRole("button", { name: "Menu", exact: true }).isVisible()) {
    await page.getByRole("button", { name: "Menu", exact: true }).click();
  }
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /New Spec/ }).click();
  await page.getByLabel("Spec name").fill(title);
  await page.getByRole("button", { name: "Create Spec", exact: true }).click();
  await expect(page.locator(".spec-paper")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible({ timeout: 20_000 });
}

async function main() {
  const ports = new Set<number>();
  while (ports.size < 5) ports.add(await freePort());
  const [specPort, plannerPort, circuitPort, circuitUiPort, catalogPort] = [...ports];

  const specUrl = `http://127.0.0.1:${specPort}`;
  const circuitUrl = `http://127.0.0.1:${circuitPort}`;
  const circuitUiUrl = `http://127.0.0.1:${circuitUiPort}`;
  const plannerUrl = `http://127.0.0.1:${plannerPort}`;
  const catalogUrl = `http://127.0.0.1:${catalogPort}`;

  // Configure services.json
  const baseConfig = JSON.parse(readFileSync(join(root, "config/services.json"), "utf8"));
  baseConfig.public_host = "127.0.0.1";
  baseConfig.spec_editor.spec_root = startsDir;
  Object.assign(baseConfig.spec_editor.service, { host: "127.0.0.1", port: specPort });
  Object.assign(baseConfig.spec_editor.ui, { host: "127.0.0.1", port: specPort });
  Object.assign(baseConfig.circuit_designer.service, { host: "127.0.0.1", port: circuitPort });
  Object.assign(baseConfig.circuit_designer.ui, { host: "127.0.0.1", port: circuitUiPort });
  Object.assign(baseConfig.verification_planner.service, { host: "127.0.0.1", port: plannerPort });
  Object.assign(baseConfig.verification_planner.ui, { host: "127.0.0.1", port: plannerPort });
  Object.assign(baseConfig.spec_catalog.service, { host: "127.0.0.1", port: catalogPort });
  Object.assign(baseConfig.spec_catalog.ui, { host: "127.0.0.1", port: catalogPort });
  baseConfig.spec_catalog.catalog_root = join(root, "spec_catalog_service/catalog");
  baseConfig.spec_catalog.state_dir = join(envDir, "catalog-state");
  baseConfig.logging.enabled = false;
  baseConfig.logging.file = join(envDir, "events.jsonl");
  baseConfig.activities.scratch_root = join(envDir, "generated");
  baseConfig.circuit_designer.preferences_file = join(envDir, "preferences.json");

  const configPath = join(envDir, "services.json");
  writeFileSync(configPath, JSON.stringify(baseConfig, null, 2));

  const childEnv: NodeJS.ProcessEnv = {
    ...process.env,
    SPEC_EDITOR_STATE_ROOT: join(envDir, "spec-state"),
    SPEC_DOCUMENT_ROOT: startsDir,
    ASSISTANT_STATE: join(envDir, "assistant-state"),
    SPEC2GDS_SCRATCH_ROOT: join(envDir, "scratch"),
    PYTHONPATH: `${join(root, "tests/ui-scenarios/e2e")}:${root}${process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""}`,
  };

  console.log("[Recorder] Starting Spec service...");
  const specProc = startProcess(
    "spec",
    join(root, ".venv/bin/spec2gds-spec-service"),
    ["--service-config", configPath],
    root,
    childEnv
  );
  await waitForHealth(`${specUrl}/health`, specProc);
  console.log("[Recorder] Spec service ready at", specUrl);

  let circuitProc: ChildProcess | null = null;
  let circuitUiProc: ChildProcess | null = null;
  if (["pilot", "V00", "V07", "V08"].includes(episodeId)) {
    console.log("[Recorder] Starting Circuit service & UI...");
    circuitProc = startProcess(
      "circuit",
      "npm",
      ["run", "service", "--", "--service-config", configPath],
      join(root, "circuit-designer"),
      childEnv
    );
    await waitForHealth(`${circuitUrl}/api/circuit-designer/v1/health`, circuitProc);

    const uiScript = existsSync(join(root, "circuit-designer/apps/standalone/dist/index.html"))
      ? "preview:standalone"
      : "dev:standalone";
    circuitUiProc = startProcess(
      "circuit-ui",
      "npm",
      ["run", uiScript, "--", "--service-config", configPath],
      join(root, "circuit-designer"),
      childEnv
    );
    await waitForHealth(`${circuitUiUrl}/api/circuit-designer/v1/health`, circuitUiProc);
    console.log("[Recorder] Circuit Designer ready at", circuitUiUrl);
  }

  let plannerProc: ChildProcess | null = null;
  let catalogProc: ChildProcess | null = null;
  if (["V00", "V05"].includes(episodeId)) {
    console.log(`[Recorder] Starting Catalog service for episode ${episodeId}...`);
    catalogProc = startProcess(
      "catalog",
      join(root, ".venv/bin/spec2gds-catalog-service"),
      ["--service-config", configPath],
      root,
      childEnv
    );
    await waitForHealth(`${catalogUrl}/api/spec-catalog/v1/health`, catalogProc);
  }

  if (episodeId === "V00") {
    console.log("[Recorder] Starting Verification Planner for V00 tour...");
    plannerProc = startProcess(
      "verification",
      join(root, ".venv/bin/verification-planner"),
      ["--service-config", configPath, "--storage-dir", join(envDir, "planner")],
      root,
      childEnv
    );
    await waitForHealth(`${plannerUrl}/api/verification/v1/health`, plannerProc);
  }

  // Seed initial test spec package
  const packagePath = join(startsDir, "tutorial.spec");
  spawnSync(
    join(root, ".venv/bin/python"),
    [
      "-c",
      "import sys; from spec2gds.spec.spec_format.testing import write_test_package; write_test_package(sys.argv[1])",
      packagePath,
    ],
    { env: childEnv }
  );

  // Launch Playwright Chromium in 1080p
  console.log("[Recorder] Launching 1080p Playwright Chromium...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: rawDir,
      size: { width: 1920, height: 1080 },
    },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();
  const timelineActions: Array<{ action: string; timestamp: number }> = [];

  function recordAction(action: string) {
    timelineActions.push({ action, timestamp: Date.now() });
    console.log(`[Action] ${action}`);
  }

  try {
    if (episodeId === "pilot") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Registered adder tutorial");
      await page.waitForTimeout(2000);

      recordAction("Add Component Definition");
      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("Registered adder");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Add Ports with Explicit Range");
      const component = page.locator("[id^='component-']").first();
      await expect(component).toBeVisible({ timeout: 15_000 });
      await component.getByRole("button", { name: "Options for Ports", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add port", exact: true }).click();

      const portDraft = component.locator(".spec-port-editor");
      // Add 'a' port
      await portDraft.getByLabel("Port ID", { exact: true }).fill("a");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Input operand A");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // Add 'b' port
      await portDraft.getByLabel("Port ID", { exact: true }).fill("b");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Input operand B");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // Add 'clk' port
      await portDraft.getByLabel("Port ID", { exact: true }).fill("clk");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("");
      await portDraft.getByLabel("Description", { exact: true }).fill("Clock signal");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // Add 'sum' port and commit
      await portDraft.getByLabel("Port ID", { exact: true }).fill("sum");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("out");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Registered sum output");
      await portDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Add SystemVerilog section");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add SystemVerilog section…", exact: true }).click();
      await component.locator(".cm-content").fill(
        "always_ff @(posedge clk) begin\n  sum <= a + b;\nend"
      );
      await component.getByRole("button", { name: "Add section", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Verify Component Lint");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Verify Component", exact: true }).click();
      await page.waitForTimeout(3000);

      recordAction("Inspect Interface Preview & Handoff");
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await page.waitForTimeout(3000);

      recordAction("Handoff to Circuit Designer");
      await page.goto(`${circuitUiUrl}`);
      await expect(page.getByTestId("circuit-canvas")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(4000);

    } else if (episodeId === "V00") {
      recordAction("System Tour: Spec Editor");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "System tour spec");
      await page.waitForTimeout(3000);

      recordAction("System Tour: Circuit Designer");
      await page.goto(`${circuitUiUrl}`);
      await expect(page.getByTestId("circuit-canvas")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(4000);

      recordAction("System Tour: Verification Planner");
      await page.goto(`${plannerUrl}`);
      await page.waitForTimeout(3000);

      recordAction("System Tour: Spec Catalog");
      await page.goto(`${catalogUrl}`);
      await page.waitForTimeout(3000);

    } else if (episodeId === "V01") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Coverage authoring");
      await page.waitForTimeout(2000);

      recordAction("Navigate Contents Hierarchy");
      await page.locator("#components").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1500);
      await page.locator(".spec-cover").scrollIntoViewIfNeeded();
      await page.waitForTimeout(1500);

      recordAction("Rename Spec Document");
      await page.locator(".spec-cover").getByRole("button", { name: "Options for Spec", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Edit name", exact: true }).click();
      await page.getByLabel("Spec name", { exact: true }).fill("Released Spec 1.0");
      await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(2500);

      recordAction("Demonstrate Draft State and Discarding Edits");
      await page.locator(".spec-cover").getByRole("button", { name: "Options for Spec", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Edit name", exact: true }).click();
      await page.getByLabel("Spec name", { exact: true }).fill("Temporary Draft Unsaved");
      await page.waitForTimeout(1500);
      await page.getByRole("button", { name: "Cancel", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Demonstrate Theme Toggle");
      await page.getByRole("button", { name: /Switch theme/ }).click();
      await page.waitForTimeout(2000);
      await page.getByRole("button", { name: /Switch theme/ }).click();
      await page.waitForTimeout(2000);

    } else if (episodeId === "V02") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "ALU Component Tutorial");
      await page.waitForTimeout(2000);

      recordAction("Add Component Definition");
      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("Arithmetic Logic Unit");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(2000);

      const component = page.locator("[id^='component-']").first();
      await expect(component).toBeVisible({ timeout: 15_000 });

      recordAction("Edit Component Definition");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      if (await page.getByRole("menuitem", { name: "Rename", exact: true }).isVisible()) {
        await page.getByRole("menuitem", { name: "Rename", exact: true }).click();
        await component.getByLabel("Name", { exact: true }).fill("ALU 16-Bit Core");
        const saveBtn = component.getByRole("button", { name: "Save to Spec", exact: true });
        if (await saveBtn.isVisible()) {
          await saveBtn.click();
        } else {
          await page.keyboard.press("Enter");
        }
        await page.waitForTimeout(1500);
      } else {
        await page.keyboard.press("Escape");
      }

      recordAction("Add Ports with Explicit Range and Save and Add Another");
      await component.getByRole("button", { name: "Options for Ports", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add port", exact: true }).click();

      const portDraft = component.locator(".spec-port-editor");
      // data_a (vector 15:0)
      await portDraft.getByLabel("Port ID", { exact: true }).fill("data_a");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("15:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Input operand A");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // data_b (vector 15:0)
      await portDraft.getByLabel("Port ID", { exact: true }).fill("data_b");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("15:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Input operand B");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // clk (scalar 1-bit, range empty)
      await portDraft.getByLabel("Port ID", { exact: true }).fill("clk");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("");
      await portDraft.getByLabel("Description", { exact: true }).fill("System clock");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      // result (vector 15:0, Save to Spec)
      await portDraft.getByLabel("Port ID", { exact: true }).fill("result");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("out");
      await portDraft.getByLabel("Range", { exact: true }).fill("15:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("ALU result");
      await portDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Edit Port Definition");
      const resRow = component.locator(".spec-port-row").filter({ has: page.getByRole("rowheader", { name: "result", exact: true }) });
      await resRow.getByRole("button", { name: "Options for port result", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Edit", exact: true }).click();
      const editPortDraft = component.locator(".spec-port-editor");
      await editPortDraft.getByLabel("Description", { exact: true }).fill("16-bit ALU output result");
      await editPortDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      recordAction("Duplicate Port");
      await resRow.getByRole("button", { name: "Options for port result", exact: true }).click();
      await page.getByRole("menuitem", { name: "Duplicate", exact: true }).click();
      const dupDraft = component.locator(".spec-port-editor");
      await dupDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      recordAction("Delete Port");
      page.once("dialog", (dialog) => dialog.accept());
      const dupRow = component.locator(".spec-port-row").filter({ has: page.getByRole("rowheader", { name: "result_2", exact: true }) });
      await dupRow.getByRole("button", { name: "Options for port result_2", exact: true }).click();
      await page.getByRole("menuitem", { name: "Delete port", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Configure Parameters");
      const paramsDetails = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Parameters", { exact: true }) });
      await paramsDetails.locator("summary").click();
      await paramsDetails.getByRole("button", { name: "Options for Parameters", exact: true }).click();
      await page.getByRole("menuitem", { name: "Add parameter", exact: true }).click();
      await page.getByLabel("Parameter ID").fill("WIDTH");
      await page.getByLabel("RTL type").fill("int unsigned");
      await page.getByLabel("Default expression").fill("16");
      await page.getByLabel("Parameter description").fill("ALU bit width");
      await page.getByRole("button", { name: "Save parameter to Spec", exact: true }).click();
      await page.waitForTimeout(2500);

    } else if (episodeId === "V03") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Barrel Shifter Spec");
      await page.waitForTimeout(2000);

      recordAction("Add Component with Ports");
      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("Barrel Shifter");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(2000);

      const component = page.locator("[id^='component-']").first();
      await expect(component).toBeVisible({ timeout: 15_000 });

      await component.getByRole("button", { name: "Options for Ports", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add port", exact: true }).click();
      const portDraft = component.locator(".spec-port-editor");
      await portDraft.getByLabel("Port ID", { exact: true }).fill("data_in");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Input data vector");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1000);

      await portDraft.getByLabel("Port ID", { exact: true }).fill("data_out");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("out");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByLabel("Description", { exact: true }).fill("Shifted output data vector");
      await portDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      recordAction("Author Narrative & Details");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      if (await page.getByRole("menuitem", { name: "Edit text…" }).isVisible()) {
        await page.getByRole("menuitem", { name: "Edit text…" }).click();
        const descField = component.getByLabel("Component explanation");
        if (await descField.isVisible()) {
          await descField.fill("High-performance barrel shifter with parameterized shift stages.");
          await component.getByRole("button", { name: "Save to Spec", exact: true }).click();
        }
      } else if (await page.getByRole("menuitem", { name: "Edit details" }).isVisible()) {
        await page.getByRole("menuitem", { name: "Edit details" }).click();
        const descField = page.getByLabel("Description");
        if (await descField.isVisible()) {
          await descField.fill("High-performance barrel shifter with parameterized shift stages.");
          await page.getByRole("button", { name: "Save to Spec", exact: true }).click();
        }
      } else {
        await page.keyboard.press("Escape");
      }
      await page.waitForTimeout(2000);

      recordAction("Add SystemVerilog Implementation Section");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add SystemVerilog section…", exact: true }).click();
      await component.locator(".cm-content").fill(
        "always_comb begin\n  data_out = data_in << 1;\nend"
      );
      await component.getByRole("button", { name: "Add section", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Inspect Hardware Settings");
      const hwSettings = component.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Hardware settings", { exact: true }) });
      await hwSettings.locator("summary").click();
      await page.waitForTimeout(2000);

      recordAction("Inspect Compact Preview, Expand, and Download SVG");
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(2000);
      const previewCard = component.locator(".spec-topology-card").filter({ has: page.getByRole("img") }).first();
      if (await previewCard.isVisible()) {
        await previewCard.scrollIntoViewIfNeeded();
        await page.waitForTimeout(1500);
        const previewOpts = previewCard.getByRole("button", { name: "Options for circuit preview", exact: true });
        if (await previewOpts.isVisible()) {
          await previewOpts.click();
          const expandItem = page.getByRole("menuitem", { name: "Expand", exact: true });
          if (await expandItem.isVisible()) {
            await expandItem.click();
            await expect(page.getByRole("dialog", { name: /Interface preview|Circuit topology/ })).toBeVisible({ timeout: 5000 });
            await page.waitForTimeout(2000);
            await page.keyboard.press("Escape");
            await page.waitForTimeout(1000);
          }
          const downloadPromise = page.waitForEvent("download");
          await previewOpts.click();
          await page.getByRole("menuitem", { name: "Download SVG" }).click();
          const download = await downloadPromise;
          console.log(`[Recorder] Downloaded SVG: ${download.suggestedFilename()}`);
        }
      }
      await page.waitForTimeout(3000);

    } else if (episodeId === "V04") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Verification Diagnostics Spec");
      await page.waitForTimeout(2000);

      recordAction("Add Component with SystemVerilog");
      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("Adder Unit");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(2000);

      const component = page.locator("[id^='component-']").first();
      await expect(component).toBeVisible({ timeout: 15_000 });

      await component.getByRole("button", { name: "Options for Ports", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add port", exact: true }).click();
      const portDraft = component.locator(".spec-port-editor");
      await portDraft.getByLabel("Port ID", { exact: true }).fill("a");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      await portDraft.getByLabel("Port ID", { exact: true }).fill("b");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("in");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByRole("button", { name: "Save and add another", exact: true }).click();
      await page.waitForTimeout(1500);

      await portDraft.getByLabel("Port ID", { exact: true }).fill("sum");
      await portDraft.getByLabel("Direction", { exact: true }).selectOption("out");
      await portDraft.getByLabel("Range", { exact: true }).fill("7:0");
      await portDraft.getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add SystemVerilog section…", exact: true }).click();
      await component.locator(".cm-content").fill(
        "always_comb begin\n  sum = a + b;\nend"
      );
      await component.getByRole("button", { name: "Add section", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Verify Component Lint: Passed");
      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Verify Component", exact: true }).click();
      await expect(page.locator(".app-toast")).toContainText("Lint passed", { timeout: 15_000 });
      await page.waitForTimeout(2500);

      recordAction("Induce Lint Failure and Observe Draft Preservation");
      await component.locator(".spec-sv-section").getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Edit", exact: true }).click();
      await component.locator(".cm-content").fill("always_comb begin\n  sum = a + ;\nend");
      await component.locator(".spec-sv-section").getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Verify Component", exact: true }).click();
      await expect(page.locator(".app-toast")).toContainText("Lint failed. Your saved text is preserved.", { timeout: 15_000 });
      await page.waitForTimeout(2500);

      recordAction("Open Diagnostics Panel and Inspect Technical Details");
      const diagTrigger = page.locator("#editor-diagnostics-trigger");
      await expect(diagTrigger).toBeVisible({ timeout: 10_000 });
      await diagTrigger.click();
      const sidebar = page.locator(".utility-sidebar");
      await expect(sidebar).toBeVisible({ timeout: 5000 });
      await page.waitForTimeout(2000);

      recordAction("Navigate to Source Finding");
      const goToSourceBtn = page.locator(".diagnostic-finding").getByRole("button", { name: "Go to source" }).first();
      if (await goToSourceBtn.isVisible()) {
        await goToSourceBtn.click();
        await page.waitForTimeout(2000);
      }

      const closePanelBtn = page.getByRole("button", { name: "Close side panel" });
      if (await closePanelBtn.isVisible()) {
        await closePanelBtn.click();
        await page.waitForTimeout(1000);
      }

      recordAction("Correct Syntax and Re-verify Clean");
      await component.locator(".spec-sv-section").getByRole("button", { name: "Options for SystemVerilog", exact: true }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Edit", exact: true }).click();
      await component.locator(".cm-content").fill("always_comb begin\n  sum = a + b;\nend");
      await component.locator(".spec-sv-section").getByRole("button", { name: "Save to Spec", exact: true }).click();
      await page.waitForTimeout(1500);

      await component.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Verify Component", exact: true }).click();
      await expect(page.locator(".app-toast")).toContainText("Lint passed", { timeout: 15_000 });
      await page.waitForTimeout(2500);

    } else if (episodeId === "V05") {
      recordAction("Open Spec Catalog Browser");
      await page.goto(`${catalogUrl}`);
      await expect(page.locator("#components-grid")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(2500);

      recordAction("Search and Filter Catalog");
      await page.locator("#input-search").fill("barrel_shift");
      await page.waitForTimeout(2000);

      recordAction("Inspect Version and Evidence");
      const firstCard = page.locator(".component-card").first();
      if (await firstCard.isVisible()) {
        await firstCard.click();
        await expect(page.locator("#modal-details")).toBeVisible({ timeout: 5000 });
        await page.waitForTimeout(3000);
        await page.locator("#btn-close-details").click();
        await page.waitForTimeout(1500);
      }

      recordAction("Open Spec Editor and Import Renamed Copy");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Catalog IP Reuse Spec");
      await page.waitForTimeout(2000);

      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menuitem", { name: "Import from catalog…", exact: true }).click();

      const dialog = page.getByRole("dialog", { name: "Component library", exact: true });
      await expect(dialog).toBeVisible({ timeout: 10_000 });
      await dialog.getByLabel("Search Components").fill("barrel_shift");
      await dialog.getByRole("button", { name: /barrel_shift/ }).first().click();
      await page.waitForTimeout(1500);

      await dialog.getByLabel("Import as a renamed copy").check();
      await dialog.getByRole("button", { name: "Review import", exact: true }).click();
      await dialog.getByLabel(/Local name for/).first().fill("Local barrel shifter");
      await dialog.getByRole("button", { name: "Review import", exact: true }).click();
      await dialog.getByRole("button", { name: "Import into Spec", exact: true }).click();
      await expect(dialog).not.toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(2500);

      recordAction("Inspect Catalog Origin Badge");
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
      await page.waitForTimeout(2000);

      recordAction("Publish Teaching Package to Private Catalog");
      await page.goto(`${catalogUrl}`);
      await expect(page.locator("#btn-upload")).toBeVisible({ timeout: 10_000 });
      await page.locator("#btn-upload").click();
      await expect(page.locator("#modal-upload")).toBeVisible({ timeout: 5000 });
      await page.locator("#input-file").setInputFiles(packagePath);
      await page.waitForTimeout(1000);
      await page.locator("#btn-submit-upload").click();
      await expect(page.locator("#upload-feedback")).toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(2500);
      await page.locator("#btn-close-upload").click();
      await page.waitForTimeout(1500);

    } else if (episodeId === "V06") {
      recordAction("Open Spec Editor and Create Spec");
      await page.goto(`${specUrl}/editor`);
      await createNewSpec(page, "Hierarchical System Spec");
      await page.waitForTimeout(2000);

      recordAction("Add Definitions for Adder and Register");
      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("adder_block");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(1500);

      await page.locator("#components").locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component…", exact: true }).click();
      await page.getByLabel("Component name").fill("register_stage");
      await page.getByRole("button", { name: "Create component", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Create Composite Design");
      const designsSection = page.locator("#designs");
      await designsSection.scrollIntoViewIfNeeded();
      await designsSection.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add design…", exact: true }).click();
      await page.getByLabel("Design name").fill("soc_top");
      await page.getByRole("button", { name: "Create design", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Add Component Instances to Design");
      const design = page.locator("[id^='design-']").first();
      await expect(design).toBeVisible({ timeout: 15_000 });

      await design.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component instance…", exact: true }).click();
      await design.getByLabel("Instance ID").fill("u_adder");
      await design.getByRole("button", { name: "Add instance", exact: true }).click();
      await page.waitForTimeout(1500);

      await design.locator(":scope > .spec-section__header").getByRole("button", { name: /^Options for / }).click();
      await page.getByRole("menu").getByRole("menuitem", { name: "Add component instance…", exact: true }).click();
      await design.getByLabel("Instance ID").fill("u_reg");
      await design.getByRole("button", { name: "Add instance", exact: true }).click();
      await page.waitForTimeout(2000);

      recordAction("Configure Entry Design and Hardware Settings");
      const designHwSettings = design.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Hardware settings", { exact: true }) });
      await designHwSettings.locator("summary").click();
      await page.waitForTimeout(1500);
      const entryCheckbox = design.locator("input[type='checkbox']").first();
      if (await entryCheckbox.isVisible()) {
        await entryCheckbox.check();
        await page.waitForTimeout(1500);
      }

      recordAction("Configure Internal Design on Component");
      const adderComp = page.locator("[id^='component-']").first();
      const compHwSettings = adderComp.locator(".spec-hardware-controls > details").filter({ has: page.getByText("Hardware settings", { exact: true }) });
      await compHwSettings.locator("summary").click();
      await page.waitForTimeout(1500);
      const internalSelect = adderComp.locator("select[aria-label='Internal Design']");
      if (await internalSelect.isVisible()) {
        await internalSelect.click();
        await page.waitForTimeout(2000);
      }

    } else if (episodeId === "V07") {
      recordAction("Open Circuit Designer and Begin Editing");
      await page.goto(`${circuitUiUrl}`);
      await expect(page.getByTestId("circuit-canvas")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(2000);

      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
      await page.getByRole("menuitem", { name: "Begin editing", exact: true }).click();
      await page.waitForTimeout(1500);

      recordAction("Place First Local Component Instance");
      await page.getByRole("menuitem", { name: "Components", exact: true }).click();
      await page.getByRole("menuitem", { name: "New local component", exact: true }).click();
      await page.getByLabel("Name", { exact: true }).fill("alu_stage");
      await page.getByRole("button", { name: "Add to Design" }).click();
      await expect(page.locator(".react-flow__node")).toHaveCount(1, { timeout: 10_000 });
      await page.waitForTimeout(2000);

      recordAction("Move Instance Snapped to Grid");
      const firstNode = page.locator(".react-flow__node").first();
      await firstNode.click();
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(1500);

      recordAction("Place Second Component Instance");
      await page.getByRole("menuitem", { name: "Components", exact: true }).click();
      await page.getByRole("menuitem", { name: "New local component", exact: true }).click();
      await page.getByLabel("Name", { exact: true }).fill("reg_stage");
      await page.getByRole("button", { name: "Add to Design" }).click();
      await expect(page.locator(".react-flow__node")).toHaveCount(2, { timeout: 10_000 });
      await page.waitForTimeout(2000);

      recordAction("Configure Boundary Port in Inspector");
      await page.getByRole("menuitem", { name: "View", exact: true }).click();
      await page.getByRole("menuitemcheckbox", { name: /Show Inspector/ }).click();
      await page.waitForTimeout(1500);
      const addBoundaryBtn = page.getByRole("button", { name: "Add port to Design" });
      if (await addBoundaryBtn.isVisible()) {
        await addBoundaryBtn.click();
        await page.getByRole("dialog", { name: "Add port", exact: true }).getByRole("button", { name: "Add port", exact: true }).click();
        await page.waitForTimeout(1500);
      }

      recordAction("Connect Ports with Net Wire");
      const sourceHandle = page.locator('.react-flow__handle[data-handleid$=":output"]').first();
      const targetHandle = page.locator('.react-flow__handle[data-handleid$=":input"]').last();
      if (await sourceHandle.isVisible() && await targetHandle.isVisible()) {
        await sourceHandle.dragTo(targetHandle);
        await page.waitForTimeout(2000);
      }

      recordAction("Demonstrate Port Width Mismatch Warning and Undo");
      const boundaryPort = page.locator(".cd-boundary-terminal, .react-flow__handle[data-handleid^='boundary:']").first();
      if (await boundaryPort.isVisible()) {
        await boundaryPort.click();
        const widthInput = page.getByLabel("Wire width or range");
        if (await widthInput.isVisible()) {
          await widthInput.fill("8");
          await page.waitForTimeout(1000);
        }
      }
      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
      await page.getByRole("menuitem", { name: /^Undo/ }).click();
      await page.waitForTimeout(1500);

      recordAction("Demonstrate Cancel Changes");
      await page.getByRole("menuitem", { name: "File", exact: true }).click();
      await page.getByRole("menuitem", { name: /Cancel changes/ }).click();
      await page.waitForTimeout(2000);

      recordAction("Begin Editing and Commit with Save to Spec");
      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
      await page.getByRole("menuitem", { name: /Begin editing/ }).click();
      await page.waitForTimeout(1000);

      await page.getByRole("menuitem", { name: "Components", exact: true }).click();
      await page.getByRole("menuitem", { name: /New local component/ }).click();
      await page.getByLabel("Name", { exact: true }).fill("committed_alu");
      await page.getByRole("button", { name: "Add to Design" }).click();
      await page.waitForTimeout(1500);

      const saveBtn = page.getByRole("button", { name: /Save to Spec|Save changes/ });
      if (await saveBtn.isVisible()) {
        await saveBtn.click();
      } else {
        await page.getByRole("menuitem", { name: "File", exact: true }).click();
        await page.getByRole("menuitem", { name: /Save changes|Save to Spec/ }).click();
      }
      await page.waitForTimeout(3000);

    } else if (episodeId === "V08") {
      recordAction("Open Circuit Designer and Begin Editing");
      await page.goto(`${circuitUiUrl}`);
      await expect(page.getByTestId("circuit-canvas")).toBeVisible({ timeout: 15_000 });
      await page.waitForTimeout(2000);

      await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
      await page.getByRole("menuitem", { name: /Begin editing/ }).click();
      await page.waitForTimeout(1000);

      recordAction("Place Instances for Layout Demonstration");
      await page.getByRole("menuitem", { name: "Components", exact: true }).click();
      await page.getByRole("menuitem", { name: /New local component/ }).click();
      await page.getByLabel("Name", { exact: true }).fill("stage_a");
      await page.getByRole("button", { name: "Add to Design" }).click();
      await page.waitForTimeout(1500);

      await page.getByRole("menuitem", { name: "Components", exact: true }).click();
      await page.getByRole("menuitem", { name: /New local component/ }).click();
      await page.getByLabel("Name", { exact: true }).fill("stage_b");
      await page.getByRole("button", { name: "Add to Design" }).click();
      await page.waitForTimeout(1500);

      recordAction("Connect Net between Instances for Routing");
      const outHandle = page.locator('.react-flow__handle[data-handleid$=":output"]').first();
      const inHandle = page.locator('.react-flow__handle[data-handleid$=":input"]').last();
      if (await outHandle.isVisible() && await inHandle.isVisible()) {
        await outHandle.dragTo(inHandle);
        await page.waitForTimeout(1500);
      }

      recordAction("Navigate Canvas: Zoom and Fit Circuit");
      await page.getByRole("menuitem", { name: "View", exact: true }).click();
      await page.getByRole("menuitem", { name: /Zoom in/ }).click();
      await page.waitForTimeout(1000);
      await page.getByRole("menuitem", { name: "View", exact: true }).click();
      await page.getByRole("menuitem", { name: /Zoom out/ }).click();
      await page.waitForTimeout(1000);
      await page.getByRole("menuitem", { name: "View", exact: true }).click();
      await page.getByRole("menuitem", { name: /Fit circuit/ }).click();
      await page.waitForTimeout(2000);

      recordAction("Inspect Properties with Show Inspector");
      await page.getByRole("menuitem", { name: "View", exact: true }).click();
      await page.getByRole("menuitemcheckbox", { name: /Show Inspector/ }).click();
      await page.waitForTimeout(2000);

      recordAction("Demonstrate Route Locking and Rerouting");
      const hitSegment = page.locator(".cd-net__hit-segment").first();
      if (await hitSegment.isVisible()) {
        await hitSegment.click({ button: "right" });
        await page.waitForTimeout(1000);
        const lockRoute = page.getByRole("menuitem", { name: /Lock whole route|Lock selected route/ });
        if (await lockRoute.isVisible()) {
          await lockRoute.click();
          await page.waitForTimeout(1500);

          await hitSegment.click({ button: "right" });
          await page.waitForTimeout(1000);
          await page.getByRole("menuitem", { name: /Unlock whole route|Unlock selected route/ }).click();
          await page.waitForTimeout(1000);
        }

        await hitSegment.click({ button: "right" });
        await page.waitForTimeout(1000);
        const reroute = page.getByRole("menuitem", { name: /Reroute/ });
        if (await reroute.isVisible()) {
          await reroute.click();
          await page.waitForTimeout(1500);
        }
      }

      recordAction("Arrange and Route All");
      await page.getByRole("menuitem", { name: "Route", exact: true }).click();
      await page.getByRole("menuitem", { name: /Arrange and route all/ }).click();
      await page.waitForTimeout(3000);
    }
  } finally {
    // Close context to cleanly flush video recording
    console.log("[Recorder] Closing browser context and flushing video...");
    const videoObj = page.video();
    await context.close();
    await browser.close();

    const videoPath = await videoObj?.path();
    console.log("[Recorder] Raw video saved to:", videoPath);

    // Save timeline actions
    writeFileSync(
      join(outputDir, "originals", `${episodeId}_actions.json`),
      JSON.stringify(timelineActions, null, 2)
    );

    // Shutdown private services
    console.log("[Recorder] Shutting down private loopback services...");
    await Promise.all([...children].map(stopProcess));
  }
  console.log("[Recorder] Execution completed successfully.");
}

main().catch((err) => {
  console.error("[Recorder] Fatal error during capture:", err);
  void Promise.all([...children].map(stopProcess)).finally(() => process.exit(1));
});
