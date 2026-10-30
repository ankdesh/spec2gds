/** Prepare an installed Harness profile and start the Assistant. */
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
// Installed packages prepare the same named profile used by releases.
const { prepareProductProfile, packageDirectory } = await import("@ankdesh/dsh-product-tools");
const productConfig = JSON.parse(readFileSync(resolve(root, "harness.product.json"), "utf8"));
if (profile === "spec2gds-replay") {
  productConfig.profiles[profile] = {
    bundles: ["@spec2gds/harness-assistant", "@spec2gds/harness-headless", "@spec2gds/harness-replay"],
    localBundles: [".", "bundles/headless", "bundles/replay"], patchReload: "startup",
  };
}
const selected = productConfig.profiles[profile];
if (!selected) throw new Error(`Unknown Assistant profile ${profile}`);
prepareProductProfile(root, env.DSH_HOME, {
  profileName: profile, bundles: selected.bundles,
  localBundles: selected.localBundles.map(path => resolve(root, path)), patchReload: selected.patchReload,
});
env.SPEC2GDS_CATALOG_ROOT = resolve(root, "profile/catalog");
const child = spawn(process.execPath, [resolve(packageDirectory("@ankdesh/dsh", root), "lib/bin.js"), "--profile", profile, ...process.argv.slice(2)], {
  cwd: env.DSH_PRODUCT_RUN_CWD || root, env, stdio: "inherit",
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
