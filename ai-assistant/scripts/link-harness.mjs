/** Link compile-time dependencies to the same Harness workspaces used by product-runtime. */
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, symlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const product = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const harness = resolve(process.argv[2] || process.env.HARNESS_SOURCE || join(product, "../../deepseek-harness"));
if (!existsSync(join(harness, "scripts/product-runtime.mjs"))) throw new Error(`Not a Harness checkout: ${harness}`);
const modules = join(product, "node_modules");
mkdirSync(modules, { recursive: true });
const generated = mkdtempSync(join(modules, ".harness-links-"));
const namespace = join(generated, "@deepseek-ai");
mkdirSync(namespace);
const directories = [];
for (const group of ["vendor", "packages"]) {
  for (const entry of readdirSync(join(harness, group), { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const directory = join(harness, group, entry.name);
    if (group === "vendor") directories.push(directory);
    else for (const member of readdirSync(directory, { withFileTypes: true })) {
      if (member.isDirectory()) directories.push(join(directory, member.name));
    }
  }
}
for (const directory of directories) {
  const manifest = join(directory, "package.json");
  if (!existsSync(manifest)) continue;
  const { name } = JSON.parse(readFileSync(manifest, "utf8"));
  if (name?.startsWith("@deepseek-ai/")) symlinkSync(directory, join(namespace, name.slice("@deepseek-ai/".length)), "dir");
}
const scope = join(modules, "@deepseek-ai");
if (existsSync(scope) || (() => { try { return lstatSync(scope).isSymbolicLink(); } catch { return false; } })()) {
  if (lstatSync(scope).isSymbolicLink()) rmSync(scope);
  else renameSync(scope, join(generated, "previous-installed-scope"));
}
symlinkSync(namespace, scope, "dir");
// Source development uses the fork's toolchain; a fresh checkout needs no registry
// installation of the unpublished event packages to run build/typecheck/tests.
mkdirSync(join(modules, ".bin"), { recursive: true });
for (const [command, packageName] of [["tsc", "typescript"], ["tsx", "tsx"]]) {
  const packageRoot = join(harness, "node_modules", packageName);
  const manifest = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
  const entry = typeof manifest.bin === "string" ? manifest.bin : manifest.bin[command];
  const local = join(modules, ".bin", command);
  // Link the actual executable: pnpm shell wrappers resolve relative to .bin.
  if (!existsSync(local)) symlinkSync(realpathSync(join(packageRoot, entry)), local);
}
if (!existsSync(join(modules, "@types"))) symlinkSync(join(harness, "node_modules", "@types"), join(modules, "@types"), "dir");
console.log(`Assistant dependencies linked to ${harness}`);
