/** Submit one non-interactive spec2gds request through the DSH headless profile. */
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const options = {};
const task = [];
let passthrough = false;
for (let index = 0; index < args.length; index += 1) {
  const value = args[index];
  if (passthrough) { task.push(value); continue; }
  if (value === "--") { passthrough = true; continue; }
  if (value === "--json") { options.json = true; continue; }
  if (["--domain", "--service-url", "--document-id", "--scope", "--entity-kind", "--entity-id", "--session-id"].includes(value)) {
    const next = args[++index];
    if (!next) throw new Error(`${value} requires a value`);
    options[value.slice(2)] = next;
    continue;
  }
  task.push(value);
}
if (!task.length) throw new Error("Usage: npm run request -- [binding options] -- <one-off request>");
const state = resolve(process.env.ASSISTANT_STATE || resolve(root, ".dev"));
const scratchRoot = resolve(process.env.SPEC2GDS_SCRATCH_ROOT || resolve(state, "workspaces"));
const env = { ...process.env, ASSISTANT_PROFILE: "spec2gds-headless", ASSISTANT_STATE: state, SPEC2GDS_SCRATCH_ROOT: scratchRoot };
const headless = [];
if (options.json) headless.push("--json");
if (options["session-id"]) {
  headless.push("--session-id", options["session-id"]);
} else {
  const domain = options.domain;
  if (domain !== "spec" && domain !== "circuit") throw new Error("A fresh request requires --domain spec|circuit.");
  if (!options["service-url"] || !options["document-id"]) throw new Error("A fresh request requires --service-url and --document-id.");
  const binding = {
    domain,
    serviceBaseUrl: options["service-url"],
    documentId: options["document-id"],
    scope: domain === "circuit" ? "document" : options.scope || "document",
    ...(options["entity-kind"] ? { entityKind: options["entity-kind"] } : {}),
    ...(options["entity-id"] ? { entityId: options["entity-id"] } : {}),
  };
  env.SPEC2GDS_BINDING_JSON = JSON.stringify(binding);
  env.DSH_PRODUCT_RUN_CWD = resolve(scratchRoot, `request-${randomUUID()}`);
  mkdirSync(env.DSH_PRODUCT_RUN_CWD, { recursive: true, mode: 0o700 });
}
headless.push(task.join(" "));
const child = spawn(process.execPath, [resolve(root, "scripts/dev.mjs"), ...headless], { cwd: env.DSH_PRODUCT_RUN_CWD || root, env, stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
