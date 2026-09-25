/** Native release entry: prepare product-owned profiles and invoke the shipped Harness CLI. */
import { mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { prepareProductProfile } from "./harness-profile.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
if (process.env.ASSISTANT_ENV_FILE) process.loadEnvFile(process.env.ASSISTANT_ENV_FILE);
const release = JSON.parse(readFileSync(resolve(root, "release.json"), "utf8"));
if (release.platform !== process.platform || release.arch !== process.arch) throw new Error("This release targets a different platform or architecture.");
if (release.harnessDirty) throw new Error("Refusing to launch a release assembled from a dirty Harness checkout.");
const state = resolve(process.env.ASSISTANT_STATE || resolve(homedir(), ".local/state/spec2gds-assistant"));
mkdirSync(state, { recursive: true, mode: 0o700 });
const env = {
  ...process.env,
  ASSISTANT_STATE: state,
  DSH_HOME: resolve(state, "harness-dsh-ui"),
  SPEC2GDS_SCRATCH_ROOT: resolve(process.env.SPEC2GDS_SCRATCH_ROOT || resolve(state, "workspaces")),
};
mkdirSync(env.SPEC2GDS_SCRATCH_ROOT, { recursive: true, mode: 0o700 });

const application = resolve(root, "node_modules", release.application);
const recipe = JSON.parse(readFileSync(resolve(root, "harness.product.json"), "utf8"));
const profiles = Object.entries(recipe.profiles || {});
if (!profiles.length) throw new Error("The release does not declare any product profiles.");
for (const [profileName, profile] of profiles) {
  prepareProductProfile(application, env.DSH_HOME, {
    profileName,
    bundles: profile.bundles,
    localBundles: profile.localBundles.map(directory => resolve(application, directory)),
    patchReload: profile.patchReload,
  });
}
const profile = env.ASSISTANT_PROFILE || recipe.defaultProfile || profiles[0][0];
if (!Object.hasOwn(recipe.profiles, profile)) throw new Error(`Unknown assistant profile ${JSON.stringify(profile)}.`);
env.ASSISTANT_PROFILE = profile;
if (profile === "spec2gds-web") console.log(`spec2gds Harness assistant: http://127.0.0.1:${env.ASSISTANT_PORT || 6013}`);
const child = spawn(process.execPath, [resolve(root, "node_modules/@deepseek-ai/dsh/lib/bin.js"), "--profile", profile, ...process.argv.slice(2)], {
  cwd: env.DSH_PRODUCT_RUN_CWD || state,
  env,
  stdio: "inherit",
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
