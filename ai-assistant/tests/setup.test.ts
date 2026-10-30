import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, copyFileSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test, { type TestContext } from "node:test";
import { parseEnv } from "node:util";
import { updateHarnessSource } from "../scripts/harness-env.mjs";

function write(path: string, content: string, mode?: number) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, mode === undefined ? undefined : { mode });
}

function harnessFixture(root: string, marker: string) {
  write(join(root, "scripts/product-runtime.mjs"), "// Fixture Harness runtime\n");
  mkdirSync(join(root, "vendor"), { recursive: true });
  const native = join(root, "packages/core/example");
  write(join(native, "package.json"), JSON.stringify({ name: "@ankdesh/example", type: "module", exports: "./index.mjs" }));
  write(join(native, "index.mjs"), `export default ${JSON.stringify(marker)};\n`);
  for (const [name, command, entry] of [["typescript", "tsc", "bin/tsc"], ["tsx", "tsx", "dist/cli.mjs"]]) {
    const packageRoot = join(root, `node_modules/.pnpm/${name}@${marker}/node_modules/${name}`);
    write(join(packageRoot, "package.json"), JSON.stringify({ name, type: "module", exports: "./index.mjs", bin: name === "tsx" ? entry : { [command!]: entry } }));
    write(join(packageRoot, "index.mjs"), `export default ${JSON.stringify(marker)};\n`);
    write(join(packageRoot, entry!), `#!/usr/bin/env node\nconsole.log(${JSON.stringify(`${command}:${marker}`)});\n`, 0o755);
    symlinkSync(packageRoot, join(root, "node_modules", name!), "dir");
    // Copying or linking these pnpm wrappers would fail from the product .bin.
    write(join(root, "node_modules/.bin", command!), "#!/bin/sh\nexit 99\n", 0o755);
  }
  write(join(root, "node_modules/@types/node/index.d.ts"), `// ${marker}\n`);
  return root;
}

function fixture(t: TestContext) {
  const root = mkdtempSync(join(tmpdir(), "assistant-setup-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const product = join(root, "spec2gds/ai-assistant");
  mkdirSync(join(product, "scripts"), { recursive: true });
  for (const script of ["link-harness.mjs", "harness-env.mjs"]) {
    copyFileSync(resolve(import.meta.dirname, "../scripts", script), join(product, "scripts", script));
  }
  write(join(product, "package.json"), JSON.stringify({ type: "module" }));
  const first = harnessFixture(join(root, "deepseek-harness"), "first");
  const link = (harness = first) => spawnSync(process.execPath, [join(product, "scripts/link-harness.mjs"), harness], { cwd: product, encoding: "utf8" });
  const success = (harness = first) => {
    const result = link(harness);
    assert.equal(result.status, 0, result.stderr);
  };
  const verify = (harness = first, marker = "first") => {
    for (const [command, packageName, entry] of [["tsc", "typescript", "bin/tsc"], ["tsx", "tsx", "dist/cli.mjs"]]) {
      const executable = join(product, "node_modules/.bin", command!);
      assert.equal(realpathSync(executable), realpathSync(join(harness, "node_modules", packageName!, entry!)));
      const result = spawnSync(executable, ["--version"], { cwd: product, encoding: "utf8" });
      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stdout.trim(), `${command}:${marker}`);
      assert.equal(realpathSync(join(product, "node_modules", packageName!)), realpathSync(join(harness, "node_modules", packageName!)));
    }
    assert.equal(realpathSync(join(product, "node_modules/@types")), realpathSync(join(harness, "node_modules/@types")));
    const imported = spawnSync(process.execPath, ["--input-type=module", "-e", "import ts from 'typescript'; import tsx from 'tsx'; import native from '@ankdesh/example'; console.log(JSON.stringify([ts,tsx,native]));"], { cwd: product, encoding: "utf8" });
    assert.equal(imported.status, 0, imported.stderr);
    assert.deepEqual(JSON.parse(imported.stdout), [marker, marker, marker]);
    assert.equal(parseEnv(readFileSync(join(product, ".env"), "utf8")).HARNESS_SOURCE, realpathSync(harness));
  };
  return { root, product, first, link, success, verify };
}

test("fresh source linking provides imports and executable toolchain without registry installs", t => {
  const f = fixture(t);
  f.success();
  f.verify();
  assert.equal(statSync(join(f.product, ".env")).mode & 0o777, 0o600);
  f.success();
  f.verify();
  assert.equal(readFileSync(join(f.product, ".env"), "utf8").match(/^HARNESS_SOURCE=/gm)?.length, 1);
});

test("linking refreshes valid and dangling links when switching Harness checkouts", t => {
  const f = fixture(t);
  f.success();
  const second = harnessFixture(join(f.root, "Harness # with spaces"), "second");
  f.success(second);
  f.verify(second, "second");
  rmSync(second, { recursive: true });
  // All managed package and executable links now point at a deleted checkout.
  assert.equal(existsSync(join(f.product, "node_modules/.bin/tsx")), false);
  assert.equal(lstatSync(join(f.product, "node_modules/.bin/tsx")).isSymbolicLink(), true);
  f.success();
  f.verify();
});

test("replaced installed packages and real executable wrappers are backed up", t => {
  const f = fixture(t);
  for (const name of ["@ankdesh", "@types", "typescript", "tsx"]) {
    write(join(f.product, "node_modules", name, "keep.txt"), name);
  }
  for (const name of ["tsc", "tsx"]) write(join(f.product, "node_modules/.bin", name), `old-${name}`);
  write(join(f.product, "node_modules/unrelated/keep.txt"), "unrelated");
  f.success();
  f.verify();
  const backup = readdirSync(join(f.product, "node_modules")).find(name => name.startsWith(".harness-links-"))!;
  const generated = join(f.product, "node_modules", backup);
  for (const [name, target] of [["@ankdesh", "scope"], ["@types", "types"], ["typescript", "typescript"], ["tsx", "tsx"]]) {
    assert.equal(readFileSync(join(generated, `previous-installed-${target}`, "keep.txt"), "utf8"), name);
  }
  for (const name of ["tsc", "tsx"]) assert.equal(readFileSync(join(generated, `previous-installed-bin-${name}`), "utf8"), `old-${name}`);
  assert.equal(readFileSync(join(f.product, "node_modules/unrelated/keep.txt"), "utf8"), "unrelated");
});

test("missing toolchain executables fail before changing existing links or .env", t => {
  const f = fixture(t);
  f.success();
  const env = readFileSync(join(f.product, ".env"), "utf8");
  const scope = realpathSync(join(f.product, "node_modules/@ankdesh"));
  const broken = harnessFixture(join(f.root, "incomplete"), "broken");
  rmSync(join(broken, "node_modules/tsx/dist/cli.mjs"));
  const result = f.link(broken);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Harness toolchain is incomplete: missing .*cli\.mjs/);
  assert.match(result.stderr, /Run pnpm install/);
  assert.equal(readFileSync(join(f.product, ".env"), "utf8"), env);
  assert.equal(realpathSync(join(f.product, "node_modules/@ankdesh")), scope);
  f.verify();
});

test("symlinked checkout paths persist their physical destination", t => {
  const f = fixture(t);
  const alias = join(f.root, "checkout alias");
  symlinkSync(f.first, alias, "dir");
  f.success(alias);
  f.verify();
});

test("unified setup installs locked packages without a Harness checkout", t => {
  const f = fixture(t), workspace = dirname(f.product);
  mkdirSync(join(workspace, "scripts"), { recursive: true });
  mkdirSync(join(workspace, "circuit-designer"));
  const setup = join(workspace, "scripts/setup-all.sh");
  copyFileSync(resolve(import.meta.dirname, "../../scripts/setup-all.sh"), setup);
  const commands = join(f.root, "setup-commands.log"), bin = join(f.root, "stub-tools");
  for (const command of ["uv", "npm", "npx"]) {
    write(join(bin, command), '#!/bin/sh\nprintf "%s:%s\\n" "$PWD" "$*" >> "$SETUP_TEST_COMMANDS"\n', 0o755);
  }
  // A clone, source link, or pnpm build would fail this installation.
  for (const command of ["git", "pnpm"]) write(join(bin, command), '#!/bin/sh\nexit 99\n', 0o755);
  const result = spawnSync("bash", [setup], { cwd: f.root, encoding: "utf8", env: {
    ...process.env, PATH: `${bin}:${process.env.PATH}`, NODE_AUTH_TOKEN: "fixture-token", SETUP_TEST_COMMANDS: commands,
  } });
  assert.equal(result.status, 0, result.stderr);
  const log = readFileSync(commands, "utf8");
  assert.ok(log.includes(`${f.product}:ci --no-audit --no-fund\n`));
  assert.ok(log.includes(`${f.product}:run build\n`));
  assert.equal(existsSync(join(f.product, ".env")), false);
});

test(".env updates remove stale duplicates while preserving settings, comments and permissions", t => {
  const f = fixture(t);
  const env = join(f.product, ".env");
  const settings = '# Settings\r\nOPENAI_API_KEY="fixture-only-key" # keep\r\nOTHER="first\r\nHARNESS_SOURCE=literal content\r\nlast"\r\n';
  write(env, settings + "HARNESS_SOURCE='/missing/deepseek-harness/\r\ndeepseek-harness' # first checkout\r\nexport HARNESS_SOURCE = /another/missing/path # duplicate checkout\r\nASSISTANT_PORT=6013");
  chmodSync(env, 0o640);
  f.success();
  const updated = readFileSync(env, "utf8");
  assert.ok(updated.startsWith(settings));
  assert.ok(updated.includes("# first checkout"));
  assert.ok(updated.includes("# duplicate checkout"));
  assert.ok(updated.endsWith("ASSISTANT_PORT=6013"));
  assert.deepEqual(parseEnv(updated), { OPENAI_API_KEY: "fixture-only-key", OTHER: "first\nHARNESS_SOURCE=literal content\nlast", HARNESS_SOURCE: realpathSync(f.first), ASSISTANT_PORT: "6013" });
  assert.equal(statSync(env).mode & 0o777, 0o640);
  f.success();
  assert.equal(readFileSync(env, "utf8"), updated);
});

test(".env appends a safely quoted path and preserves a symlinked settings file", t => {
  const f = fixture(t);
  const target = join(f.root, "private-settings.env");
  write(target, "# Existing settings\nASSISTANT_PORT=6013");
  chmodSync(target, 0o600);
  symlinkSync(target, join(f.product, ".env"));
  const harness = join(f.root, "someone's Harness # with spaces");
  updateHarnessSource(f.product, harness);
  const source = readFileSync(target, "utf8");
  assert.ok(source.startsWith("# Existing settings\nASSISTANT_PORT=6013\n"));
  assert.equal(parseEnv(source).HARNESS_SOURCE, harness);
  assert.equal(lstatSync(join(f.product, ".env")).isSymbolicLink(), true);
  assert.equal(statSync(target).mode & 0o777, 0o600);
});
