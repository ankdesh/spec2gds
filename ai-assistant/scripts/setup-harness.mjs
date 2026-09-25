/** Prepare the exact DeepSeek Harness checkout pinned by harness.lock.json. */
import { execFileSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  renameSync,
  rmSync,
} from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function defaultRun(command, args, options = {}) {
  return execFileSync(command, args, {
    cwd: options.cwd,
    encoding: "utf8",
    stdio: options.stdio || ["ignore", "pipe", "pipe"],
  }).trim();
}

function parseVersion(value) {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/.exec(value);
  if (!match) throw new Error(`Unsupported version: ${value}`);
  return match.slice(1).map(Number);
}

function compareVersions(left, right) {
  for (let index = 0; index < 3; index += 1) {
    if (left[index] !== right[index]) return left[index] < right[index] ? -1 : 1;
  }
  return 0;
}

export function satisfiesNodeRange(version, range) {
  const current = parseVersion(version);
  return range.split("||").some(rawClause => {
    const clause = rawClause.trim();
    if (clause.startsWith("^")) {
      const minimum = parseVersion(clause.slice(1));
      return current[0] === minimum[0] && compareVersions(current, minimum) >= 0;
    }
    if (clause.startsWith(">=")) {
      return compareVersions(current, parseVersion(clause.slice(2).trim())) >= 0;
    }
    return compareVersions(current, parseVersion(clause)) === 0;
  });
}

export function validateLock(lock, nodeVersion = process.versions.node) {
  if (!lock || typeof lock !== "object") throw new Error("harness.lock.json must contain an object.");
  if (typeof lock.repository !== "string" || !lock.repository.trim()) {
    throw new Error("harness.lock.json must define a repository.");
  }
  if (typeof lock.commit !== "string" || !/^[0-9a-f]{40}$/i.test(lock.commit)) {
    throw new Error("harness.lock.json must define a full 40-character Git commit.");
  }
  if (typeof lock.node !== "string" || !lock.node.trim()) {
    throw new Error("harness.lock.json must define a Node.js version range.");
  }
  if (!satisfiesNodeRange(nodeVersion, lock.node)) {
    throw new Error(`Node.js ${nodeVersion} does not satisfy the Harness requirement ${lock.node}.`);
  }
  const packageManager = /^pnpm@(\d+\.\d+\.\d+)$/.exec(String(lock.packageManager || ""));
  if (!packageManager) {
    throw new Error("harness.lock.json packageManager must pin an exact pnpm version.");
  }
  return { ...lock, pnpmVersion: packageManager[1] };
}

function normalizeRemote(value) {
  return value.trim().replace(/\/+$/, "").replace(/\.git$/, "");
}

function commandError(error) {
  const detail = String(error?.stderr || error?.stdout || error?.message || error).trim();
  return detail ? `\n${detail}` : "";
}

function runChecked(runCommand, command, args, options, description) {
  try {
    return runCommand(command, args, options);
  } catch (error) {
    throw new Error(`${description} failed.${commandError(error)}`, { cause: error });
  }
}

function git(runCommand, cwd, args, description) {
  return runChecked(runCommand, "git", args, { cwd }, description);
}

function clonePinnedCheckout(runCommand, repository, commit, destination) {
  const parent = dirname(destination);
  mkdirSync(parent, { recursive: true });
  const stagingRoot = mkdtempSync(join(parent, `.${basename(destination)}.setup-`));
  const stagingCheckout = join(stagingRoot, "checkout");
  try {
    runChecked(
      runCommand,
      "git",
      ["clone", "--no-checkout", repository, stagingCheckout],
      {},
      "Harness clone",
    );
    git(runCommand, stagingCheckout, ["checkout", "--detach", commit], "Pinned Harness checkout");
    renameSync(stagingCheckout, destination);
  } finally {
    rmSync(stagingRoot, { recursive: true, force: true });
  }
}

function verifyPackageManager(checkout, expected) {
  const manifestPath = join(checkout, "package.json");
  if (!existsSync(manifestPath)) throw new Error(`Harness package.json is missing at ${manifestPath}.`);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (manifest.packageManager !== expected) {
    throw new Error(
      `Harness packageManager is ${JSON.stringify(manifest.packageManager)}; expected ${expected}.`,
    );
  }
}

export function setupHarness(options = {}) {
  const runCommand = options.runCommand || defaultRun;
  const log = options.log || console.log;
  const lockPath = resolve(options.lockPath || join(root, "harness.lock.json"));
  const lock = validateLock(
    JSON.parse(readFileSync(lockPath, "utf8")),
    options.nodeVersion || process.versions.node,
  );
  const checkout = resolve(
    options.harnessPath || process.env.HARNESS_SOURCE || resolve(root, "../../deepseek-harness"),
  );

  if (!existsSync(checkout)) {
    log(`Cloning Harness ${lock.commit} into ${checkout}`);
    clonePinnedCheckout(runCommand, lock.repository, lock.commit, checkout);
  } else {
    if (!lstatSync(checkout).isDirectory()) {
      throw new Error(`Harness destination exists but is not a directory: ${checkout}`);
    }
    try {
      const topLevel = git(
        runCommand,
        checkout,
        ["rev-parse", "--show-toplevel"],
        "Harness repository check",
      );
      if (resolve(topLevel) !== checkout) throw new Error("destination is not the working-tree root");
    } catch (error) {
      throw new Error(`Harness destination is not a Git working tree: ${checkout}`, { cause: error });
    }
    const remote = git(runCommand, checkout, ["remote", "get-url", "origin"], "Harness origin lookup");
    if (normalizeRemote(remote) !== normalizeRemote(lock.repository)) {
      throw new Error(`Harness origin mismatch: expected ${lock.repository}, found ${remote}.`);
    }
    const dirty = git(
      runCommand,
      checkout,
      ["status", "--porcelain", "--untracked-files=normal"],
      "Harness status check",
    );
    if (dirty) {
      throw new Error(`Harness checkout has local changes; refusing to modify or build it: ${checkout}`);
    }
    const head = git(runCommand, checkout, ["rev-parse", "HEAD"], "Harness HEAD lookup");
    if (head !== lock.commit) {
      if (!options.update) {
        throw new Error(
          `Harness HEAD is ${head}, but ${lock.commit} is pinned. ` +
          "Run `npm run setup:harness -- --update` to switch this clean checkout.",
        );
      }
      log(`Updating Harness from ${head} to ${lock.commit}`);
      git(runCommand, checkout, ["fetch", "--prune", "origin"], "Harness fetch");
      git(runCommand, checkout, ["checkout", "--detach", lock.commit], "Pinned Harness checkout");
    }
  }

  const head = git(runCommand, checkout, ["rev-parse", "HEAD"], "Final Harness HEAD lookup");
  if (head !== lock.commit) {
    throw new Error(`Harness checkout verification failed: expected ${lock.commit}, found ${head}.`);
  }
  verifyPackageManager(checkout, lock.packageManager);

  const pnpm = ["exec", "--yes", `--package=pnpm@${lock.pnpmVersion}`, "--", "pnpm"];
  log(`Installing Harness dependencies with ${lock.packageManager}`);
  runChecked(
    runCommand,
    "npm",
    [...pnpm, "install", "--frozen-lockfile"],
    { cwd: checkout, stdio: "inherit" },
    "Harness dependency installation",
  );
  log("Building Harness");
  runChecked(
    runCommand,
    "npm",
    [...pnpm, "run", "build"],
    { cwd: checkout, stdio: "inherit" },
    "Harness build",
  );
  log(`Harness is ready at ${checkout}`);
  return { checkout, commit: lock.commit };
}

function usage() {
  return "Usage: npm run setup:harness -- [--update]";
}

function main() {
  const args = process.argv.slice(2);
  if (args.includes("--help")) {
    console.log(usage());
    return;
  }
  const unknown = args.filter(value => value !== "--update");
  if (unknown.length) throw new Error(`Unknown argument: ${unknown[0]}\n${usage()}`);
  setupHarness({ update: args.includes("--update") });
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
