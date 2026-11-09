import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import test, { type TestContext } from "node:test";
import { checkHarnessPackages } from "../scripts/check-harness-packages.mjs";

const root = resolve(import.meta.dirname, "..");
function fixture(t: TestContext) {
  const tempRoot = resolve(root, "../temp/TEMP_harness-packages-tests");
  mkdirSync(tempRoot, { recursive: true });
  const directory = mkdtempSync(join(tempRoot, "fixture-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const product = join(directory, "product");
  const name = "@ankdesh/dsh", version = "0.1.6-ankdesh.2";
  const entry = { name, version, integrity: "sha512-published", tarball: "https://npm.pkg.github.com/download/@ankdesh/dsh/0.1.6-ankdesh.2/archive" };
  const bytes = JSON.stringify({ releaseId: version, packages: [entry] });
  const write = (path: string, value: unknown) => { mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, JSON.stringify(value)); };
  write(join(product, "harness.lock.json"), { releaseId: version, releaseManifestSha256: createHash("sha256").update(bytes).digest("hex") });
  mkdirSync(join(product, "releases")); writeFileSync(join(product, "releases/harness-release-manifest.json"), bytes);
  const lock = { packages: { [`node_modules/${name}`]: { version, integrity: entry.integrity, resolved: entry.tarball } } };
  write(join(product, "package-lock.json"), lock);
  write(join(product, "node_modules", name, "package.json"), { name, version });
  return { directory, product, name, lock, write };
}

test("the application resolves the published release without a Harness source checkout", () => {
  const checked = checkHarnessPackages(root);
  assert.equal(checked.releaseId, "0.1.6-ankdesh.2");
  assert.equal(checked.publishedPackages, 175);
  assert.ok(checked.installedPackages > 150);
});

test("a source checkout link is rejected even when its package version matches", t => {
  const f = fixture(t);
  const installed = join(f.product, "node_modules", f.name), external = join(f.directory, "source-package");
  cpSync(installed, external, { recursive: true }); rmSync(installed, { recursive: true });
  symlinkSync(external, installed, "dir");
  assert.throws(() => checkHarnessPackages(f.product), /outside the installed node_modules/);
});

test("candidate archive checksums cannot replace the published package", t => {
  const f = fixture(t);
  f.lock.packages[`node_modules/${f.name}`]!.integrity = "sha512-candidate";
  f.write(join(f.product, "package-lock.json"), f.lock);
  assert.throws(() => checkHarnessPackages(f.product), /published archive/);
});

test("promoted manifests retain their checksum and validate registry archive identity", t => {
  const f = fixture(t);
  const manifestPath = join(f.product, "releases/harness-release-manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  delete manifest.packages[0].tarball;
  manifest.packages[0].file = "ankdesh-dsh-0.1.6-ankdesh.2.tgz";
  manifest.profiles = {};
  const bytes = JSON.stringify(manifest);
  writeFileSync(manifestPath, bytes);
  f.write(join(f.product, "harness.lock.json"), {
    status: "promoted", releaseId: manifest.releaseId,
    releaseManifestSha256: createHash("sha256").update(bytes).digest("hex"),
  });
  const archive = `https://npm.pkg.github.com/download/${f.name}/${manifest.releaseId}/${"a".repeat(40)}`;
  f.lock.packages[`node_modules/${f.name}`]!.resolved = archive;
  f.write(join(f.product, "package-lock.json"), f.lock);
  assert.equal(checkHarnessPackages(f.product).installedPackages, 1);
  assert.equal(readFileSync(manifestPath, "utf8"), bytes);
  for (const invalid of [archive.replace("npm.pkg.github.com", "example.com"),
    archive.replace(manifest.releaseId, "0.1.6-ankdesh.1"), `${archive}?unexpected=1`]) {
    f.lock.packages[`node_modules/${f.name}`]!.resolved = invalid;
    f.write(join(f.product, "package-lock.json"), f.lock);
    assert.throws(() => checkHarnessPackages(f.product), /published archive/);
  }
});

test("normal commands do not provide a source-development path", () => {
  const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
  assert.equal(manifest.scripts["dev:source"], undefined);
  assert.doesNotMatch(readFileSync(join(root, "scripts/dev.mjs"), "utf8"), /HARNESS_SOURCE|product-runtime\.mjs/);
});
