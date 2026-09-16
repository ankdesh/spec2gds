/** Native release entry: prepare external state and invoke the shipped Harness CLI. */
import { existsSync, mkdirSync, readFileSync } from "node:fs";
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
const env = { ...process.env, ASSISTANT_STATE: state, DSH_HOME: resolve(state, "harness") };
prepareProductProfile(resolve(root, "node_modules", release.application), env.DSH_HOME);
console.log(`spec2gds Harness assistant: http://127.0.0.1:${env.ASSISTANT_PORT || 6013}`);
const child = spawn(process.execPath, [resolve(root, "node_modules/@deepseek-ai/dsh/lib/bin.js"), "--profile", "product"], { cwd: state, env, stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
