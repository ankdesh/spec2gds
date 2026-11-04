/** Consume product launch options before forwarding Vite options. */
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { resolveConfig, parseLaunchArgs, endpointUrl } from "../../runtime/service-config.mjs";

const [application, command, ...args] = process.argv.slice(2);
const { options, rest } = parseLaunchArgs(args);
if (rest.includes("--help")) {
  console.log("UI launch options: --service-config PATH --host HOST --port PORT --public-host HOST (CLI > file > defaults). Other options go to Vite.");
  process.exit(0);
}
const fields = Object.fromEntries(["host", "port"].filter(key => options[key] !== undefined).map(key => [key, options[key]]));
const overrides = application === "editor" ? { spec_editor: { dev_ui: fields } } : { circuit_designer: { ui: fields } };
if (options["public-host"] !== undefined) overrides.public_host = options["public-host"];
const config = resolveConfig(options["service-config"], overrides);
console.log(`${application === "editor" ? "Spec Editor" : "Circuit Designer"}: ${endpointUrl(application === "editor" ? config.spec_editor.dev_ui : config.circuit_designer.ui, config.public_host)}`);
const root = fileURLToPath(new URL("../..", import.meta.url));
const directory = resolve(root, "temp", "TEMP_serve-all", `vite_${randomUUID()}`);
mkdirSync(directory, { recursive: true });
const source = resolve(root, `circuit-designer/apps/${application}/vite.config.ts`);
const overlay = resolve(directory, "vite.config.mts");
writeFileSync(overlay, `import { configure } from ${JSON.stringify(pathToFileURL(source).href)};\nexport default configure(${JSON.stringify(config)});\n`);
const vite = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const child = spawn(process.execPath, [vite, ...(command === "dev" ? [] : [command]), "--config", overlay, ...rest], { stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
