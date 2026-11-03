/** Prepare an installed Harness profile and start the Assistant. */
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { prepareServiceLaunch, profileEntries } from "./service-launch.mjs";
import { checkHarnessPackages } from "./check-harness-packages.mjs";

// The pinned Harness CLI enters through import.meta.main. Older Node 24
// releases otherwise exit with success without starting the requested profile.
if (typeof import.meta.main !== "boolean") {
  throw new Error("The Harness CLI requires Node 22.19+ in the 22.x line or Node 24.2+. Node 24.0/24.1 cannot launch it.");
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
checkHarnessPackages(root);
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
if (!existsSync(resolve(root, "lib/index.js")) || !existsSync(resolve(root, "bundles/web/lib/client.js"))) {
  throw new Error("Build the assistant first: npm run build");
}
// Installed packages prepare the same named profile used by releases.
const { prepareProductProfile, packageDirectory } = await import("@ankdesh/ankdesh-product-tools");
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
const anchor = resolve(packageDirectory("@ankdesh/dsh", root), "package.json");
const launch = prepareServiceLaunch(process.argv.slice(2), resolve(root, ".."), await profileEntries(profile, anchor, env.DSH_HOME));
if (profile === "spec2gds-web") console.log(`AI Assistant: ${launch.url}`);
const child = spawn(process.execPath, [resolve(packageDirectory("@ankdesh/dsh", root), "lib/bin.js"), "--profile", profile, ...launch.args], {
  cwd: env.DSH_PRODUCT_RUN_CWD || root, env, stdio: "inherit",
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
