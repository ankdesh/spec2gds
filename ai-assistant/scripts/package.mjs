/** Refuse dirty/unpinned Harness inputs, then delegate release assembly. */
import { existsSync, readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync, spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"));
const output = process.argv[2];
if (!output) throw new Error("Usage: npm run package -- NEW_OUTPUT_DIRECTORY");
if (!existsSync(resolve(root, "lib/index.js")) || !existsSync(resolve(root, "web/dist/index.html"))) throw new Error("Run npm run build before packaging.");
const lock = JSON.parse(readFileSync(resolve(root, "harness.lock.json"), "utf8"));
const head = execFileSync("git", ["rev-parse", "HEAD"], { cwd: harness, encoding: "utf8" }).trim();
if (head !== lock.commit) throw new Error("Harness HEAD does not match harness.lock.json.");
const dirty = execFileSync("git", ["status", "--porcelain"], { cwd: harness, encoding: "utf8" }).trim();
if (dirty) throw new Error("Refusing to package from a dirty Harness checkout. Commit or remove every Harness change first.");
const result = spawnSync(process.execPath, [resolve(harness, "scripts/product-pack.mjs"), root, resolve(output)], { stdio: "inherit" });
if (result.error) throw result.error;
process.exitCode = result.status || (result.signal ? 1 : 0);
