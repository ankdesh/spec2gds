/** Refuse dirty/unpinned Harness inputs, then delegate release assembly. */
import { existsSync, readFileSync, cpSync, mkdirSync, mkdtempSync, rmSync, symlinkSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { execFileSync, spawnSync } from "node:child_process";

// Resolve from the script location so packaging also works from another cwd.
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let harness = resolve(process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"));
if (!existsSync(resolve(harness, "scripts/product-runtime.mjs")) && existsSync(resolve(harness, "deepseek-harness/scripts/product-runtime.mjs"))) {
  harness = resolve(harness, "deepseek-harness");
}
const output = process.argv[2];
if (!output) throw new Error("Usage: npm run package -- NEW_OUTPUT_DIRECTORY");
if (!existsSync(resolve(root, "lib/index.js")) || !existsSync(resolve(root, "bundles/web/lib/client.js"))) throw new Error("Run npm run build before packaging.");
const lock = JSON.parse(readFileSync(resolve(root, "harness.lock.json"), "utf8"));
const head = execFileSync("git", ["rev-parse", "HEAD"], { cwd: harness, encoding: "utf8" }).trim();
if (head !== lock.commit) throw new Error("Harness HEAD does not match harness.lock.json.");
const dirty = execFileSync("git", ["status", "--porcelain"], { cwd: harness, encoding: "utf8" }).trim();
if (dirty) throw new Error("Refusing to package from a dirty Harness checkout. Commit or remove every Harness change first.");
// The canonical guides live at repository level. Stage them for the release;
// do not restore a second editable documentation source under this npm package.
const staging = mkdtempSync(resolve(tmpdir(), "spec2gds-release-inputs-"));
try {
  for (const entry of ["package.json", "lib", "profile", "bundles", "deployment", "README.md", "harness.product.json", "harness.lock.json"]) {
    cpSync(resolve(root, entry), resolve(staging, entry), { recursive: true });
  }
  symlinkSync(resolve(root, "node_modules"), resolve(staging, "node_modules"), "dir");
  mkdirSync(resolve(staging, "docs"));
  for (const guide of ["ai-assistant.md", "ai-assistant-operations.md", "ai-assistant-flows.md", "TERMINOLOGY.md"]) {
    cpSync(resolve(root, "../docs", guide), resolve(staging, "docs", guide));
  }
  const result = spawnSync(process.execPath, [resolve(harness, "scripts/product-pack.mjs"), staging, resolve(output)], { stdio: "inherit" });
  if (result.error) throw result.error;
  process.exitCode = result.status || (result.signal ? 1 : 0);
} finally { rmSync(staging, { recursive: true, force: true }); }
