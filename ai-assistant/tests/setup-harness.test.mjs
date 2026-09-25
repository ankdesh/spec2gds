import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { setupHarness } from "../scripts/setup-harness.mjs";

function run(command, args, options = {}) {
  return execFileSync(command, args, {
    cwd: options.cwd,
    encoding: "utf8",
    stdio: options.stdio || ["ignore", "pipe", "pipe"],
  }).trim();
}

function git(cwd, ...args) {
  return run("git", args, { cwd });
}

function createFixture(t) {
  const directory = mkdtempSync(join(tmpdir(), "spec2gds-setup-harness-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const repository = join(directory, "remote");
  mkdirSync(repository);
  git(repository, "init", "--quiet");
  git(repository, "config", "user.name", "Setup Test");
  git(repository, "config", "user.email", "setup@example.invalid");
  writeFileSync(join(repository, "package.json"), JSON.stringify({ packageManager: "pnpm@11.7.0" }));
  writeFileSync(join(repository, "marker.txt"), "pinned\n");
  git(repository, "add", ".");
  git(repository, "commit", "--quiet", "-m", "pinned");
  const pinned = git(repository, "rev-parse", "HEAD");
  writeFileSync(join(repository, "marker.txt"), "newer\n");
  git(repository, "commit", "--quiet", "-am", "newer");
  const newer = git(repository, "rev-parse", "HEAD");
  const lockPath = join(directory, "harness.lock.json");
  writeFileSync(lockPath, JSON.stringify({
    repository,
    commit: pinned,
    node: "^22.19.0 || >=24.0.0",
    packageManager: "pnpm@11.7.0",
  }));
  return { directory, repository, pinned, newer, lockPath, checkout: join(directory, "deepseek-harness") };
}

function cloneAt(fixture, commit) {
  run("git", ["clone", "--quiet", fixture.repository, fixture.checkout]);
  git(fixture.checkout, "checkout", "--quiet", "--detach", commit);
}

function setupOptions(fixture, overrides = {}) {
  const packageCommands = [];
  const runCommand = overrides.runCommand || ((command, args, options) => {
    if (command === "npm") {
      packageCommands.push({ args, cwd: options.cwd });
      return "";
    }
    return run(command, args, options);
  });
  return {
    lockPath: fixture.lockPath,
    harnessPath: fixture.checkout,
    nodeVersion: "24.0.0",
    log: () => {},
    runCommand,
    packageCommands,
    ...overrides,
  };
}

test("clones the pinned commit and installs and builds Harness", t => {
  const fixture = createFixture(t);
  const options = setupOptions(fixture);
  const result = setupHarness(options);

  assert.equal(result.commit, fixture.pinned);
  assert.equal(git(fixture.checkout, "rev-parse", "HEAD"), fixture.pinned);
  assert.equal(git(fixture.checkout, "rev-parse", "--abbrev-ref", "HEAD"), "HEAD");
  assert.deepEqual(options.packageCommands.map(command => command.args.slice(-2)), [
    ["install", "--frozen-lockfile"],
    ["run", "build"],
  ]);
  assert.ok(options.packageCommands.every(command => command.cwd === fixture.checkout));
});

test("uses an existing checkout already at the pinned commit", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.pinned);
  const options = setupOptions(fixture);

  setupHarness(options);

  assert.equal(git(fixture.checkout, "rev-parse", "HEAD"), fixture.pinned);
  assert.equal(options.packageCommands.length, 2);
});

test("refuses to switch an existing checkout without --update", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.newer);

  assert.throws(
    () => setupHarness(setupOptions(fixture)),
    /npm run setup:harness -- --update/,
  );
  assert.equal(git(fixture.checkout, "rev-parse", "HEAD"), fixture.newer);
});

test("fetches and detaches at the pinned commit with --update", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.newer);

  setupHarness(setupOptions(fixture, { update: true }));

  assert.equal(git(fixture.checkout, "rev-parse", "HEAD"), fixture.pinned);
  assert.equal(git(fixture.checkout, "rev-parse", "--abbrev-ref", "HEAD"), "HEAD");
});

test("rejects a dirty checkout", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.pinned);
  writeFileSync(join(fixture.checkout, "marker.txt"), "dirty\n");

  assert.throws(() => setupHarness(setupOptions(fixture)), /has local changes/);
});

test("rejects a checkout with a different origin", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.pinned);
  git(fixture.checkout, "remote", "set-url", "origin", join(fixture.directory, "other"));

  assert.throws(() => setupHarness(setupOptions(fixture)), /origin mismatch/);
});

test("does not overwrite a non-Git destination", t => {
  const fixture = createFixture(t);
  mkdirSync(fixture.checkout);
  writeFileSync(join(fixture.checkout, "keep.txt"), "keep\n");

  assert.throws(() => setupHarness(setupOptions(fixture)), /not a Git working tree/);
});

test("propagates a fetch failure without moving the checkout", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.newer);
  rmSync(fixture.repository, { recursive: true, force: true });

  assert.throws(() => setupHarness(setupOptions(fixture, { update: true })), /Harness fetch failed/);
  assert.equal(git(fixture.checkout, "rev-parse", "HEAD"), fixture.newer);
});

test("propagates a build failure", t => {
  const fixture = createFixture(t);
  cloneAt(fixture, fixture.pinned);
  const runCommand = (command, args, options) => {
    if (command === "npm" && args.at(-1) === "build") throw new Error("simulated build failure");
    if (command === "npm") return "";
    return run(command, args, options);
  };

  assert.throws(
    () => setupHarness(setupOptions(fixture, { runCommand })),
    /Harness build failed[\s\S]*simulated build failure/,
  );
});
