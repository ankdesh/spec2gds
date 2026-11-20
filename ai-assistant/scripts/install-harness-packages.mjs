/** npm extracts the verified local archives and installs locked public dependencies. */
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { checkHarnessPackages } from "./check-harness-packages.mjs";
import { readHarnessRelease, verifyHarnessArchives } from "./harness-archives.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
console.log(verifyHarnessArchives(readHarnessRelease(root), `${root}/vendor/harness`));
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["ci", "--no-audit", "--no-fund"], { cwd: root, env: process.env, stdio: "inherit" });
if (result.error) throw result.error;
if (result.status !== 0) process.exitCode = result.status || 1;
else console.log(checkHarnessPackages(root));
