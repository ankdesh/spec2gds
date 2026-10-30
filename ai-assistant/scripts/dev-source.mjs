/** Link this product to a local Harness checkout and run the focused profile. */
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

// The pinned Harness CLI enters through import.meta.main. Older Node 24
// releases otherwise exit with success without starting the requested profile.
if (typeof import.meta.main !== "boolean") {
  throw new Error("The Harness CLI requires Node 22.19+ in the 22.x line or Node 24.2+. Node 24.0/24.1 cannot launch it.");
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
if (existsSync(resolve(root, ".env"))) process.loadEnvFile(resolve(root, ".env"));
if (!process.env.HARNESS_SOURCE) throw new Error("Set HARNESS_SOURCE for the explicit dev:source command.");
let harness = resolve(process.env.HARNESS_SOURCE);
if (!existsSync(resolve(harness, "scripts/product-runtime.mjs")) && existsSync(resolve(harness, "deepseek-harness/scripts/product-runtime.mjs"))) {
  harness = resolve(harness, "deepseek-harness");
}
const state = resolve(process.env.ASSISTANT_STATE || resolve(root, ".dev"));
mkdirSync(state, { recursive: true, mode: 0o700 });
const env = {
  ...process.env,
  ASSISTANT_STATE: state,
  DSH_HOME: resolve(state, "harness-dsh-ui"),
  SPEC2GDS_SCRATCH_ROOT: resolve(process.env.SPEC2GDS_SCRATCH_ROOT || resolve(state, "workspaces")),
  SPEC_DOCUMENT_ROOT: resolve(process.env.SPEC_DOCUMENT_ROOT || resolve(state, "spec-documents")),
};
const profile = env.ASSISTANT_PROFILE || "spec2gds-web";
env.ASSISTANT_PROFILE = profile;
const registryPath = resolve(env.SPEC2GDS_SERVICE_CONFIG || resolve(root, "../config/services.json"));
if (existsSync(registryPath)) {
  const registry = JSON.parse(readFileSync(registryPath, "utf8"));
  const publicHost = env.SPEC2GDS_PUBLIC_HOST && env.SPEC2GDS_PUBLIC_HOST !== "auto"
    ? env.SPEC2GDS_PUBLIC_HOST
    : registry.public_host && registry.public_host !== "auto" ? registry.public_host : "127.0.0.1";
  const endpoint = (value, host) => {
    const selectedHost = ["0.0.0.0", "::", "[::]"].includes(String(value.host)) ? host : value.host;
    const defaultPort = value.scheme === "https" ? 443 : 80;
    const port = Number(value.port) === defaultPort ? "" : `:${Number(value.port)}`;
    return `${value.scheme}://${selectedHost}${port}${String(value.base_path || "").replace(/\/$/, "")}`;
  };
  const allowlist = (value) => [...new Set([endpoint(value, "127.0.0.1"), endpoint(value, publicHost)])].join(",");
  env.SPEC_SERVICE_ALLOWLIST ||= allowlist(registry.spec_editor.service);
  env.CIRCUIT_SERVICE_ALLOWLIST ||= allowlist(registry.circuit_designer.service);
  env.ASSISTANT_HOST ||= String(registry.ai_assistant.service.host);
  env.ASSISTANT_PORT ||= String(registry.ai_assistant.service.port);
}
if (!existsSync(resolve(root, "lib/index.js")) || !existsSync(resolve(root, "bundles/web/lib/client.js"))) {
  throw new Error("Build the assistant first: npm run build");
}
// Local Harness development uses source links for its own packages. Keep those
// links in a generated product tree so npm-installed build dependencies in the
// source checkout are never replaced or mixed into the running Cordis graph.
const runtimeProduct = resolve(state, "runtime-product");
rmSync(runtimeProduct, { recursive: true, force: true });
mkdirSync(runtimeProduct, { recursive: true, mode: 0o700 });
const manifest = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));
manifest.dependencies = Object.fromEntries(Object.entries(manifest.dependencies || {})
  .filter(([name]) => name !== "react" && name !== "react-dom"));
if (profile === "spec2gds-replay") manifest.dependencies["@ankdesh/dsh-llm-replay"] = "0.1.6-alpha.1";
writeFileSync(resolve(runtimeProduct, "package.json"), `${JSON.stringify(manifest, null, 2)}\n`);
for (const directory of ["lib", "profile", "bundles"]) {
  const target = resolve(runtimeProduct, directory);
  mkdirSync(dirname(target), { recursive: true });
  cpSync(resolve(root, directory), target, { recursive: true });
}
env.SPEC2GDS_CATALOG_ROOT = resolve(runtimeProduct, "profile", "catalog");
// Source packages retain their upstream scope. Rewrite only the generated runtime copy.
function sourceScope(directory) {
  for (const item of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, item.name);
    if (item.isDirectory()) sourceScope(path);
    else if (/\.(js|json|ya?ml)$/.test(item.name)) writeFileSync(path, readFileSync(path, "utf8").replaceAll("@ankdesh/", "@deepseek-ai/"));
  }
}
sourceScope(runtimeProduct);
const productConfig = JSON.parse(readFileSync(resolve(root, "harness.product.json"), "utf8"));
if (profile === "spec2gds-replay") {
  productConfig.profiles[profile] = {
    bundles: ["@spec2gds/harness-assistant", "@spec2gds/harness-headless", "@spec2gds/harness-replay"],
    localBundles: [".", "bundles/headless", "bundles/replay"],
    patchReload: "startup",
  };
}
writeFileSync(resolve(runtimeProduct, "harness.product.json"), `${JSON.stringify(productConfig, null, 2).replaceAll("@ankdesh/", "@deepseek-ai/")}\n`);
if (profile === "spec2gds-web") console.log(`spec2gds Harness assistant: http://127.0.0.1:${env.ASSISTANT_PORT || 6013}`);
if (!env.OPENAI_API_KEY) console.error("OPENAI_API_KEY is unset; model turns will fail.");
const child = spawn(process.execPath, [resolve(harness, "scripts/product-runtime.mjs"), "dev", runtimeProduct, profile, ...process.argv.slice(2)], { cwd: env.DSH_PRODUCT_RUN_CWD || runtimeProduct, env, stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
