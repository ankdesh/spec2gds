/** Real processes and private durable storage. No product API responses are mocked. */
import { test as base, expect, type Page, type TestInfo } from "@playwright/test";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { once } from "node:events";
import { createWriteStream, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
export async function freePort(): Promise<number> {
  const server = createServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No private port available");
  await new Promise<void>(done => server.close(() => done()));
  return address.port;
}

export async function stop(child: ChildProcess): Promise<void> {
  if (!child.pid) return;
  const signal = (value: NodeJS.Signals) => {
    try { process.kill(-child.pid!, value); }
    catch (error: any) { if (error.code !== "ESRCH") throw error; }
  };
  if (child.exitCode !== null || child.signalCode !== null) { signal("SIGKILL"); return; }
  const exited = once(child, "exit");
  signal("SIGTERM");
  const timer = setTimeout(() => signal("SIGKILL"), 5_000);
  try { await exited; } finally { clearTimeout(timer); signal("SIGKILL"); }
}

export class Stack {
  readonly directory: string;
  readonly spec: string;
  readonly planner: string;
  readonly circuit: string;
  readonly circuitUI: string;
  readonly env: NodeJS.ProcessEnv;
  private readonly children = new Map<string, ChildProcess>();
  private readonly sentinels: Map<string, Buffer | undefined>;
  private readonly commands = new Map<string, [string, string[], string, string]>();

  private constructor(info: TestInfo, ports: number[]) {
    this.directory = info.outputPath("private");
    mkdirSync(this.directory, { recursive: true, mode: 0o700 });
    const [spec, planner, circuit, ui] = ports;
    this.spec = `http://127.0.0.1:${spec}`;
    this.planner = `http://127.0.0.1:${planner}`;
    this.circuit = `http://127.0.0.1:${circuit}`;
    this.circuitUI = `http://127.0.0.1:${ui}`;
    const paths = [join(root, "config/services.json"), join(root, ".circuit-designer/preferences.json")];
    this.sentinels = new Map(paths.map(path => [path, existsSync(path) ? readFileSync(path) : undefined]));
    const config = JSON.parse(readFileSync(paths[0], "utf8"));
    config.public_host = "127.0.0.1";
    Object.assign(config.spec_editor.service, { host: "127.0.0.1", port: spec });
    Object.assign(config.spec_editor.ui, { host: "127.0.0.1", port: spec });
    Object.assign(config.circuit_designer.service, { host: "127.0.0.1", port: circuit });
    Object.assign(config.circuit_designer.ui, { host: "127.0.0.1", port: ui });
    config.logging.enabled = false;
    config.logging.file = join(this.directory, "events.jsonl");
    config.activities.scratch_root = join(this.directory, "generated");
    config.activities.extension_modules = ["e2e_activity_fixture:register"];
    config.circuit_designer.preferences_file = join(this.directory, "preferences.json");
    const configPath = join(this.directory, "services.json");
    writeFileSync(configPath, JSON.stringify(config));
    this.env = { ...process.env,
      SPEC2GDS_SERVICE_CONFIG: configPath, SPEC2GDS_PUBLIC_HOST: "127.0.0.1",
      SPEC_EDITOR_STATE_ROOT: join(this.directory, "spec-state"),
      SPEC_DOCUMENT_ROOT: this.directory, ASSISTANT_STATE: join(this.directory, "assistant-state"),
      SPEC2GDS_SCRATCH_ROOT: join(this.directory, "scratch"),
      SPEC2GDS_E2E_BARRIER: join(this.directory, "barrier"),
      PYTHONPATH: `${join(root, "tests/ui-scenarios/e2e")}:${root}${process.env.PYTHONPATH ? `:${process.env.PYTHONPATH}` : ""}`,
      CIRCUIT_DESIGNER_PREFERENCES_FILE: config.circuit_designer.preferences_file,
      CIRCUIT_DESIGNER_HOST: "127.0.0.1", CIRCUIT_DESIGNER_PORT: String(circuit),
      CIRCUIT_DESIGNER_UI_HOST: "127.0.0.1", CIRCUIT_DESIGNER_UI_PORT: String(ui),
      CIRCUIT_DESIGNER_SERVICE_ORIGIN: this.circuit,
      CIRCUIT_DESIGNER_E2E_API_URL: `${this.circuit}/api/circuit-designer/v1`,
    };
    this.commands.set("spec", [join(root, ".venv/bin/spec2gds-spec-service"), ["--host", "127.0.0.1", "--port", String(spec)], root, `${this.spec}/health`]);
    this.commands.set("verification", [join(root, ".venv/bin/verification-planner"), ["--host", "127.0.0.1", "--port", String(planner), "--storage-dir", join(this.directory, "planner")], root, `${this.planner}/api/verification/v1/health`]);
    const uiMode = process.env.CIRCUIT_DESIGNER_UI_MODE ?? (existsSync(join(root, "circuit-designer/apps/standalone/dist/index.html")) ? "preview" : "dev");
    const uiScript = uiMode === "dev" ? "dev:standalone" : "preview:standalone";
    this.commands.set("circuit-ui", ["npm", ["run", uiScript], join(root, "circuit-designer"), `${this.circuitUI}/api/circuit-designer/v1/health`]);
  }

  static async create(info: TestInfo): Promise<Stack> {
    const ports = new Set<number>();
    while (ports.size < 4) ports.add(await freePort());
    return new Stack(info, [...ports]);
  }
  async start(name: string): Promise<void> {
    const [command, args, cwd, health] = this.commands.get(name)!;
    const log = createWriteStream(join(this.directory, `${name}.log`), { flags: "a" });
    const child = spawn(command, args, { cwd, env: this.env, detached: true, stdio: ["ignore", "pipe", "pipe"] });
    this.children.set(name, child);
    child.stdout?.pipe(log, { end: false }); child.stderr?.pipe(log, { end: false });
    let failure: Error | undefined;
    child.on("error", error => { failure = error; });
    child.once("exit", () => log.end());
    await expect.poll(async () => {
      if (failure) throw failure;
      if (child.exitCode !== null || child.signalCode !== null) throw new Error(`${name} stopped before readiness`);
      try { return (await fetch(health)).ok; } catch { return false; }
    }, { timeout: 60_000 }).toBe(true);
  }
  async restart(name: string): Promise<void> {
    await stop(this.children.get(name)!);
    await this.start(name);
  }
  async close(): Promise<void> {
    await Promise.all([...this.children.values()].map(stop));
    for (const [path, before] of this.sentinels) {
      expect(existsSync(path) ? readFileSync(path) : undefined, `Shared file changed: ${path}`).toEqual(before);
    }
  }
  path(name = "coverage-authoring.spec"): string { return join(this.directory, name); }
  async json(path: string, body?: unknown): Promise<any> {
    const response = await fetch(`${this.spec}${path}`, body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await response.json();
    expect(response.ok, JSON.stringify(data)).toBe(true);
    return data;
  }
  async snapshot(): Promise<any> { return this.json("/documents/snapshot"); }
  async commit(operations: unknown[], snapshot?: any): Promise<any> {
    const current = snapshot ?? await this.snapshot();
    return this.json(`/transactions?service_document_key=${current.service_document_key ?? current.owner_document_key}`, {
      expected_source_revision_hash: current.source_revision_hash, operations,
    });
  }
  archive(path: string): Record<string, string> {
    const process = spawnSync(join(root, ".venv/bin/python"), ["-c",
      "import base64,json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps({n:(z.read(n).decode('utf-8') if n.endswith(('.xml','.sv','.json','.svg')) else base64.b64encode(z.read(n)).decode('ascii')) for n in z.namelist()}))", path], { encoding: "utf8" });
    expect(process.status, process.stderr).toBe(0);
    return JSON.parse(process.stdout);
  }
  seedSample(): void {
    const result = spawnSync(join(root, ".venv/bin/python"), ["-c",
      "import sys; from spec2gds.spec.spec_format.testing import write_test_package; write_test_package(sys.argv[1])", this.path()],
      { env: this.env, encoding: "utf8" });
    expect(result.status, result.stderr).toBe(0);
  }
}

export const test = base.extend<{ stack: Stack }>({
  stack: async ({}, use, info) => {
    const stack = await Stack.create(info);
    try {
      if (info.project.name === "verification") await stack.start("verification");
      else {
        await stack.start("spec");
        if (info.project.name === "circuit") {
          await stack.start("circuit"); await stack.start("circuit-ui");
        }
      }
      await use(stack);
    } finally { await stack.close(); }
  },
});
export { expect };

export async function openSpec(page: Page, stack: Stack, path = stack.path()): Promise<void> {
  await page.goto(`${stack.spec}/editor`);
  if (await page.getByRole("button", { name: "Menu", exact: true }).isVisible()) await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /Open Spec/ }).click();
  await page.getByLabel("Server-local package path").fill(path);
  await page.getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.locator(".spec-paper")).toBeVisible();
}

export async function newSpec(page: Page, stack: Stack): Promise<void> {
  await page.goto(`${stack.spec}/editor`);
  if (await page.getByRole("button", { name: "Menu", exact: true }).isVisible()) await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "File", exact: true }).click();
  await page.getByRole("menuitem", { name: /New Spec/ }).click();
  await page.getByLabel("Spec name").fill("Coverage authoring");
  await page.getByLabel("Server-local package path").fill(stack.path());
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Coverage authoring", exact: true })).toBeVisible();
}
