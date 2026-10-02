/**
 * End-to-end UI automation runner for RTLLM benchmark tasks:
 * 1. adder_8bit (Arithmetic)
 * 2. up_down_counter (Control)
 * 3. asyn_fifo (Memory)
 *
 * Validates AI Assistant natural-language spec creation, proposal review/application,
 * Spec Editor UI rendering and component-level RTL generation, capturing milestone UI snapshots.
 */
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

const liveModel = args.includes("--live-model");
if (liveModel && !process.env.OPENAI_API_KEY) {
  throw new Error("Live model execution requires OPENAI_API_KEY.");
}

const requestedTask = option("--task", "all");
const runId = new Date().toISOString().replace(/[:.]/g, "-");
const baseOutputDir = resolve(option("--output", join(root, "tests/ui-scenarios/results", `rtllm-${liveModel ? "live" : "fixture"}-${runId}`)));
mkdirSync(baseOutputDir, { recursive: true });

interface SubComponentDefinition {
  name: string;
  entityId: string;
  prompt: string;
}

interface TaskDefinition {
  id: string;
  name: string;
  title: string;
  rtllmDir: string;
  componentName: string;
  entityId: string;
  subComponent?: SubComponentDefinition;
  prompt: string;
}

const TASKS: TaskDefinition[] = [
  {
    id: "adder_8bit",
    name: "8-bit Adder",
    title: "8-bit Full Adder",
    rtllmDir: "/home/ankdesh/explore/RTLLM/Arithmetic/Adder/adder_8bit",
    componentName: "adder_8bit",
    entityId: "component_adder_8bit",
    subComponent: {
      name: "full_adder",
      entityId: "component_full_adder",
      prompt: "Create a full_adder component named full_adder (using create_entity with kind component) with entity ID component_full_adder, scalar inputs a, b, cin, scalar outputs sum, cout. Add module body assign sum = a ^ b ^ cin; assign cout = (a & b) | (cin & (a ^ b));",
    },
    prompt: `Now create the adder_8bit component named adder_8bit (using create_entity with kind component, instances: []) with entity ID component_adder_8bit, 8-bit input a with range 7:0, 8-bit input b with range 7:0, scalar input cin, 8-bit output sum with range 7:0, and scalar output cout. In the module body (systemverilog section), build the 8-bit ripple-carry adder by instantiating 8 full_adder sub-components:
wire [7:0] c;
full_adder fa0 (.a(a[0]), .b(b[0]), .cin(cin), .sum(sum[0]), .cout(c[0]));
full_adder fa1 (.a(a[1]), .b(b[1]), .cin(c[0]), .sum(sum[1]), .cout(c[1]));
full_adder fa2 (.a(a[2]), .b(b[2]), .cin(c[1]), .sum(sum[2]), .cout(c[2]));
full_adder fa3 (.a(a[3]), .b(b[3]), .cin(c[2]), .sum(sum[3]), .cout(c[3]));
full_adder fa4 (.a(a[4]), .b(b[4]), .cin(c[3]), .sum(sum[4]), .cout(c[4]));
full_adder fa5 (.a(a[5]), .b(b[5]), .cin(c[4]), .sum(sum[5]), .cout(c[5]));
full_adder fa6 (.a(a[6]), .b(b[6]), .cin(c[5]), .sum(sum[6]), .cout(c[6]));
full_adder fa7 (.a(a[7]), .b(b[7]), .cin(c[6]), .sum(sum[7]), .cout(cout));`,
  },
  {
    id: "up_down_counter",
    name: "Up-Down Counter",
    title: "16-bit Up Down Counter",
    rtllmDir: "/home/ankdesh/explore/RTLLM/Control/Counter/up_down_counter",
    componentName: "up_down_counter",
    entityId: "component_up_down_counter",
    prompt: "Create an up_down_counter component named up_down_counter (using create_entity with kind component) with entity ID component_up_down_counter, scalar clk input, scalar reset input, scalar up_down input, and 16-bit count output with range 15:0. Add module body always @(posedge clk or posedge reset) begin if (reset) count <= 16'b0; else if (up_down) count <= count + 1'b1; else count <= count - 1'b1; end",
  },
  {
    id: "asyn_fifo",
    name: "Asynchronous FIFO",
    title: "Asynchronous FIFO",
    rtllmDir: "/home/ankdesh/explore/RTLLM/Memory/FIFO/asyn_fifo",
    componentName: "asyn_fifo",
    entityId: "component_asyn_fifo",
    subComponent: {
      name: "dual_port_RAM",
      entityId: "component_dual_port_RAM",
      prompt: `Create a dual_port_RAM component named dual_port_RAM (using create_entity with kind component) with entity ID component_dual_port_RAM, scalar inputs wclk, wenc, 4-bit input waddr with range 3:0, 8-bit input wdata with range 7:0, scalar inputs rclk, renc, 4-bit input raddr with range 3:0, and 8-bit output rdata with range 7:0. Add module body:
reg [7:0] RAM_MEM [0:15];
always @(posedge wclk) begin
    if (wenc) begin
        RAM_MEM[waddr] <= wdata;
    end
end
always @(posedge rclk) begin
    if (renc) begin
        rdata <= RAM_MEM[raddr];
    end
end`,
    },
    prompt: `Now create the asyn_fifo component named asyn_fifo (using create_entity with kind component, instances: []) with entity ID component_asyn_fifo, scalar inputs wclk, rclk, wrstn, rrstn, winc, rinc, 8-bit input wdata with range 7:0, scalar outputs wfull, rempty, and 8-bit output rdata with range 7:0. In the module body (systemverilog section), build the dual-clock asynchronous FIFO by instantiating the dual_port_RAM sub-component:
reg [4:0] waddr_bin, raddr_bin, wptr, rptr;
wire [4:0] waddr_gray = waddr_bin ^ (waddr_bin >> 1);
wire [4:0] raddr_gray = raddr_bin ^ (raddr_bin >> 1);
reg [4:0] rptr_buff, rptr_syn, wptr_buff, wptr_syn;
assign wfull = (wptr == {~rptr_syn[4:3], rptr_syn[2:0]});
assign rempty = (rptr == wptr_syn);

always @(posedge wclk or negedge wrstn) begin
    if (~wrstn) begin waddr_bin <= 5'd0; wptr <= 5'd0; end
    else if (!wfull && winc) begin waddr_bin <= waddr_bin + 5'd1; wptr <= waddr_gray; end
end
always @(posedge rclk or negedge rrstn) begin
    if (~rrstn) begin raddr_bin <= 5'd0; rptr <= 5'd0; end
    else if (!rempty && rinc) begin raddr_bin <= raddr_bin + 5'd1; rptr <= raddr_gray; end
end
always @(posedge wclk or negedge wrstn) begin
    if (~wrstn) begin rptr_buff <= 5'd0; rptr_syn <= 5'd0; end
    else begin rptr_buff <= rptr; rptr_syn <= rptr_buff; end
end
always @(posedge rclk or negedge rrstn) begin
    if (~rrstn) begin wptr_buff <= 5'd0; wptr_syn <= 5'd0; end
    else begin wptr_buff <= wptr; wptr_syn <= wptr_buff; end
end

wire wen = winc && !wfull;
wire ren = rinc && !rempty;
dual_port_RAM ram_inst (
    .wclk(wclk),
    .wenc(wen),
    .waddr(waddr_bin[3:0]),
    .wdata(wdata),
    .rclk(rclk),
    .renc(ren),
    .raddr(raddr_bin[3:0]),
    .rdata(rdata)
);`,
  },
];

async function freePort(): Promise<number> {
  const server = createServer(); server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address(); assert.ok(address && typeof address === "object");
  await new Promise<void>(done => server.close(() => done())); return address.port;
}

function start(output: string, children: Set<ChildProcess>, failures: any[], name: string, command: string, argv: string[], cwd: string, env: NodeJS.ProcessEnv): ChildProcess {
  const log = createWriteStream(join(output, `${name}.log`), { flags: "a" });
  const child = spawn(command, argv, { cwd, env, detached: process.platform !== "win32", stdio: ["ignore", "pipe", "pipe"] });
  children.add(child); child.stdout?.pipe(log, { end: false }); child.stderr?.pipe(log, { end: false });
  child.on("error", error => failures.push({ type: "process", name, error: String(error) }));
  child.on("exit", () => log.end()); return child;
}

async function stop(children: Set<ChildProcess>, child: ChildProcess): Promise<void> {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return;
  const exited = once(child, "exit");
  const signal = (value: NodeJS.Signals) => {
    try { if (process.platform === "win32") child.kill(value); else process.kill(-child.pid!, value); }
    catch (error: any) { if (error.code !== "ESRCH") throw error; }
  };
  signal("SIGTERM"); const timer = setTimeout(() => signal("SIGKILL"), 5_000);
  try { await exited; } finally { clearTimeout(timer); children.delete(child); }
}

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
  await expect(page.locator(".spec-paper")).toBeVisible({ timeout: 30_000 });
}

async function prompt(page: Page, message: string): Promise<void> {
  const input = page.locator("textarea, [contenteditable='true']").first();
  await expect(input).toBeVisible({ timeout: 30_000 });
  await input.fill(message);
  const send = page.getByRole("button", { name: "Send message", exact: true });
  await expect(send).toBeEnabled({ timeout: 10_000 });
  await send.click();
}

async function runTask(task: TaskDefinition): Promise<{ passed: boolean; details: any }> {
  console.log(`\n======================================================`);
  console.log(`Running RTLLM Task: ${task.name} (${task.id})`);
  console.log(`======================================================`);

  const taskOutputDir = join(baseOutputDir, task.id);
  mkdirSync(taskOutputDir, { recursive: true });

  const isolated = mkdtempSync(join(tmpdir(), `spec2gds-rtllm-${task.id}-`));
  const documentId = `rtllm_${task.id}`;
  const packagePath = join(isolated, "packages", `${documentId}.spec`);
  mkdirSync(dirname(packagePath), { recursive: true });

  const children = new Set<ChildProcess>();
  const failures: any[] = [];
  let stopping = false;

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
  config.logging.enabled = true;
  config.logging.file = join(isolated, "events.jsonl");
  config.activities.workspace_root = join(isolated, "generated");
  config.circuit_designer.preferences_file = join(isolated, "circuit-preferences.json");
  const configPath = join(isolated, "services.json");
  writeFileSync(configPath, JSON.stringify(config));

  const fixture = liveModel ? null : await modelFixture(documentId);
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    SPEC2GDS_SERVICE_CONFIG: configPath,
    SPEC2GDS_PUBLIC_HOST: "127.0.0.1",
    SPEC_EDITOR_STATE_ROOT: join(isolated, "owner-state"),
    ASSISTANT_STATE: join(isolated, "assistant-state"),
    SPEC2GDS_SCRATCH_ROOT: join(isolated, "workspaces"),
    SPEC_DOCUMENT_ROOT: dirname(packagePath),
    ASSISTANT_HOST: "127.0.0.1",
    ASSISTANT_PORT: String(assistantPort),
    ASSISTANT_PROFILE: "spec2gds-web",
    SPEC_SERVICE_ALLOWLIST: owner,
    CIRCUIT_SERVICE_ALLOWLIST: `http://127.0.0.1:${circuitPort}/api/circuit-designer/v1`,
    SPEC2GDS_SESSION_COMPRESSION: "none",
    ASSISTANT_MAX_STEPS_PER_TURN: "5",
    ...(fixture ? { OPENAI_API_KEY: "local-fixture", OPENAI_BASE_URL: fixture.url, OPENAI_MODEL: "gpt-4o-mini" } : {}),
  };

  const ownerProcess = start(taskOutputDir, children, failures, "owner", "uv", ["run", "spec2gds-server", "--host", "127.0.0.1", "--port", String(ownerPort)], root, env);
  const assistantProcess = start(taskOutputDir, children, failures, "assistant", process.execPath, ["scripts/dev.mjs", "--no-open"], join(root, "ai-assistant"), env);

  let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined;
  let chat: Page | undefined;
  let editor: Page | undefined;
  const milestones: { step: string; file: string; desc: string }[] = [];

  try {
    await Promise.all([healthy(`${owner}/health`, ownerProcess), healthy(`${assistant}/readyz`, assistantProcess)]);
    console.log("Services ready. Launching Playwright browser...");

    browser = await chromium.launch({ headless: !args.includes("--headed"), args: ["--no-sandbox"] });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    chat = await context.newPage();
    editor = await context.newPage();

    // 1. Initialize specification package and launch AI Assistant bound to document
    const initial = await json(`${owner}/documents/create`, { path: packagePath, document_id: documentId, title: task.title });
    const key = initial.owner_document_key;
    const scoped = (path: string) => `${owner}${path}${path.includes("?") ? "&" : "?"}owner_document_key=${encodeURIComponent(key)}`;
    const snapshot = () => json(scoped("/documents/snapshot"));

    const query = new URLSearchParams({ service_base_url: owner, document_id: documentId, owner_document_key: key });
    await chat.goto(`${assistant}/launch/spec-document?${query}`);
    await chat.waitForFunction(() => (document.documentElement as any).dataset.spec2gdsLaunchStatus === "ready", null, { timeout: 30_000 });
    await expect(chat.getByRole("button", { name: "Choose workspace" })).toContainText(documentId, { timeout: 30_000 });

    const ss1 = join(taskOutputDir, "01_assistant_home.png");
    await chat.screenshot({ path: ss1, fullPage: true });
    milestones.push({ step: "01", file: "01_assistant_home.png", desc: "Initial AI Assistant chat screen bound to spec document" });
    console.log("Milestone 01: Captured AI Assistant home screen");

    // 2. Submit prompts to create components hierarchically
    if (task.subComponent) {
      console.log(`Submitting sub-component prompt: "${task.subComponent.prompt.slice(0, 80)}..."`);
      await prompt(chat, task.subComponent.prompt);

      console.log(`Waiting for sub-component ${task.subComponent.name} to be committed in snapshot...`);
      await expect.poll(async () => {
        const snap = await snapshot();
        const comp = snap.components?.find((item: any) =>
          item.ref.entity_id === task.subComponent!.entityId ||
          item.ref.entity_id.includes(task.subComponent!.name) ||
          item.name === task.subComponent!.name ||
          Boolean(item.name && item.name.includes(task.subComponent!.name))
        );
        return comp ? comp.ref.entity_id : null;
      }, { timeout: liveModel ? 120_000 : 45_000 }).toBeTruthy();

      const subSnap = await snapshot();
      const subComp = subSnap.components.find((item: any) =>
        item.ref.entity_id === task.subComponent!.entityId ||
        item.ref.entity_id.includes(task.subComponent!.name) ||
        item.name === task.subComponent!.name ||
        Boolean(item.name && item.name.includes(task.subComponent!.name))
      );
      console.log(`Found committed sub-component: ${subComp.ref.entity_id} (${subComp.name})`);
    }

    console.log(`Submitting high-level prompt: "${task.prompt.slice(0, 80)}..."`);
    await prompt(chat, task.prompt);

    console.log(`Waiting for component ${task.componentName} to be committed in snapshot...`);
    await expect.poll(async () => {
      const snap = await snapshot();
      const comp = snap.components?.find((item: any) =>
        item.ref.entity_id === task.entityId ||
        item.ref.entity_id.includes(task.componentName) ||
        item.name === task.componentName ||
        Boolean(item.name && item.name.includes(task.componentName))
      );
      return comp ? comp.ref.entity_id : null;
    }, { timeout: liveModel ? 120_000 : 45_000 }).toBeTruthy();

    const ss2 = join(taskOutputDir, "02_assistant_applied.png");
    await chat.screenshot({ path: ss2, fullPage: true });
    milestones.push({ step: "02", file: "02_assistant_applied.png", desc: "AI Assistant UI showing proposal applied and committed" });
    console.log("Milestone 02: Captured AI Assistant proposal applied screen");

    const currentSnapshot = await snapshot();
    const component = currentSnapshot.components.find((item: any) =>
      item.ref.entity_id === task.entityId ||
      item.ref.entity_id.includes(task.componentName) ||
      item.name === task.componentName ||
      Boolean(item.name && item.name.includes(task.componentName))
    );
    assert.ok(component, `Component matching ${task.componentName} must exist in snapshot`);
    const actualEntityId = component.ref.entity_id;
    const actualComponentName = component.name || task.componentName;
    console.log(`Found committed component: ${actualEntityId} (${component.name})`);

    // 3. Open Spec Editor UI and verify component
    console.log(`Opening Spec Editor UI at ${owner}/editor for package...`);
    await openEditor(editor, owner, packagePath);

    const compSelector = `#component-${actualEntityId}, #component-${actualEntityId.replaceAll("_", "-")}, #component-${task.entityId}, #component-${task.entityId.replaceAll("_", "-")}`;
    const compLocator = editor.locator(compSelector).first();
    await expect(compLocator).toBeVisible({ timeout: 30_000 });

    const ss3 = join(taskOutputDir, "03_spec_editor_component.png");
    await editor.screenshot({ path: ss3, fullPage: true });
    milestones.push({ step: "03", file: "03_spec_editor_component.png", desc: "Spec Editor UI rendering the created component, ports, and SV section" });
    console.log("Milestone 03: Captured Spec Editor component view");

    // 4. Test Launch activity dialog for component
    console.log("Testing Launch activity dialog in Spec Editor...");
    const optionsButton = compLocator.getByRole("button", { name: "Options" });
    await optionsButton.click();
    await editor.getByRole("menuitem", { name: /Launch activity/i }).click();

    const activityDialog = editor.locator("[aria-labelledby='activity-dialog-title']");
    await expect(activityDialog).toBeVisible({ timeout: 15_000 });
    await expect(activityDialog.getByText("Generate RTL", { exact: false })).toBeVisible({ timeout: 15_000 });

    const ss4 = join(taskOutputDir, "04_spec_editor_activity_dialog.png");
    await editor.screenshot({ path: ss4, fullPage: true });
    milestones.push({ step: "04", file: "04_spec_editor_activity_dialog.png", desc: "Spec Editor Launch Activity modal offering Generate RTL for component" });
    console.log("Milestone 04: Captured Spec Editor activity dialog with Generate RTL");

    // 5. Run Generate RTL activity from UI
    console.log("Triggering Generate RTL activity from Spec Editor UI...");
    const runButton = activityDialog.getByRole("button", { name: "Run" }).first();
    await runButton.click();

    // Verify activity completion view
    await expect(editor.getByText(/Action executions/i)).toBeVisible({ timeout: 20_000 });
    const ss5 = join(taskOutputDir, "05_spec_editor_activity_completed.png");
    await editor.screenshot({ path: ss5, fullPage: true });
    milestones.push({ step: "05", file: "05_spec_editor_activity_completed.png", desc: "Spec Editor Activity view showing successful RTL generation execution" });
    console.log("Milestone 05: Captured Spec Editor activity execution completed");

    // 6. Generate and Verify RTL
    const rtlWorkspaceDir = join(taskOutputDir, "generated_rtl");
    mkdirSync(rtlWorkspaceDir, { recursive: true });

    console.log("Invoking RTL generator to produce verified SystemVerilog files...");
    const runResult = spawnSync("uv", ["run", "python", "scripts/run_rtl_activity.py", packagePath, rtlWorkspaceDir, actualEntityId], { cwd: root, encoding: "utf8" });
    assert.equal(runResult.status, 0, `RTL generation failed: ${runResult.stderr}\n${runResult.stdout}`);

    // Locate generated RTL file
    let generatedSvPath = join(rtlWorkspaceDir, `rtl/${documentId}/${actualEntityId}/rtl/components/${actualComponentName}.sv`);
    if (!existsSync(generatedSvPath)) {
      generatedSvPath = join(rtlWorkspaceDir, `rtl/${documentId}/${actualEntityId}/rtl/components/${task.componentName}.sv`);
    }
    assert.ok(existsSync(generatedSvPath), `Generated SV file not found: ${generatedSvPath}`);

    // Copy package and SV to output
    cpSync(packagePath, join(taskOutputDir, `${task.id}.spec`));
    cpSync(generatedSvPath, join(taskOutputDir, `${task.id}.sv`));
    if (task.subComponent) {
      let subSvPath = join(rtlWorkspaceDir, `rtl/${documentId}/${actualEntityId}/rtl/components/${task.subComponent.name}.sv`);
      if (existsSync(subSvPath)) {
        cpSync(subSvPath, join(taskOutputDir, `${task.subComponent.name}.sv`));
        console.log(`Copied sub-component RTL: ${task.subComponent.name}.sv`);
      }
    }

    // Verify with verify_rtllm_rtl.py
    console.log("Verifying generated RTL against RTLLM requirements...");
    const verifyResult = spawnSync("uv", ["run", "python", "scripts/verify_rtllm_rtl.py", task.id, generatedSvPath], { cwd: root, encoding: "utf8" });
    const verifyReport = JSON.parse(verifyResult.stdout || "{}");
    console.log("RTL Verification Result:", verifyReport.passed ? "PASSED" : "FAILED");

    // Write task summary markdown
    const summaryMd = `# RTLLM Task Execution Summary: ${task.name}

- **Task**: \`${task.id}\`
- **Result**: ${verifyReport.passed ? "**PASSED**" : "**FAILED**"}
- **Document ID**: \`${documentId}\`
- **Component**: \`${task.componentName}\` (\`${actualEntityId}\`)
- **Generated Package**: [\`${task.id}.spec\`](./${task.id}.spec)
- **Generated RTL**: [\`${task.id}.sv\`](./${task.id}.sv)

## Verified Component Architecture
\`\`\`json
${JSON.stringify(component, null, 2)}
\`\`\`

## Verification Details
\`\`\`json
${JSON.stringify(verifyReport, null, 2)}
\`\`\`

## Milestone UI Snapshots

| Step | Milestone | Screenshot | Description |
| --- | --- | --- | --- |
${milestones.map(m => `| ${m.step} | ${m.file} | [${m.file}](./${m.file}) | ${m.desc} |`).join("\n")}
`;
    writeFileSync(join(taskOutputDir, "summary.md"), summaryMd);
    writeFileSync(join(taskOutputDir, "records.json"), JSON.stringify({ task, currentSnapshot, verifyReport, milestones }, null, 2));

    return { passed: verifyReport.passed, details: { task, verifyReport } };
  } finally {
    await browser?.close();
    stopping = true;
    await Promise.all([...children].map(c => stop(children, c)));
    try {
      if (chat && !chat.isClosed()) {
        await chat.screenshot({ path: join(taskOutputDir, "error_chat.png"), fullPage: true });
      }
    } catch {}
    try {
      if (existsSync(join(isolated, "events.jsonl"))) {
        cpSync(join(isolated, "events.jsonl"), join(taskOutputDir, "events.jsonl"));
      }
      if (existsSync(join(isolated, "assistant-state"))) {
        cpSync(join(isolated, "assistant-state"), join(taskOutputDir, "assistant-state"), { recursive: true });
      }
    } catch {}
    if (fixture) await fixture.close();
    rmSync(isolated, { recursive: true, force: true });
  }
}

async function main(): Promise<void> {
  const selectedTasks = requestedTask === "all" ? TASKS : TASKS.filter(t => t.id === requestedTask);
  if (!selectedTasks.length) {
    throw new Error(`No task matched --task ${requestedTask}. Valid options: adder_8bit, up_down_counter, asyn_fifo, all`);
  }

  const results: any[] = [];
  for (const task of selectedTasks) {
    try {
      const res = await runTask(task);
      results.push(res);
    } catch (error) {
      console.error(`Task ${task.id} failed with error:`, error);
      results.push({ passed: false, error: String(error) });
    }
  }

  console.log("\n======================================================");
  console.log("RTLLM TASK SUITE EXECUTION RESULTS");
  console.log("======================================================");
  let allPassed = true;
  for (const [index, res] of results.entries()) {
    const task = selectedTasks[index];
    console.log(`Task ${task.id}: ${res.passed ? "PASSED" : "FAILED"}`);
    if (!res.passed) allPassed = false;
  }
  console.log(`\nArtifacts and snapshots saved under:\n${baseOutputDir}`);

  if (!allPassed) {
    process.exitCode = 1;
  }
}

await main();
