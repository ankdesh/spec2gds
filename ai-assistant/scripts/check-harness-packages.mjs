/** Check the installed Harness against the published package inventory. */
import { readFileSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { archiveFilename, readHarnessRelease, verifyHarnessArchives } from "./harness-archives.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const json = path => JSON.parse(readFileSync(path, "utf8"));

export function checkHarnessPackages(product = root) {
  const release = readHarnessRelease(product);
  verifyHarnessArchives(release, resolve(product, "vendor/harness"));
  const expected = new Map(release.packages.map(value => [value.name, value]));
  const lock = json(resolve(product, "package-lock.json"));
  let count = 0;
  for (const [path, entry] of Object.entries(lock.packages)) {
    const name = path.split("node_modules/").at(-1);
    if (!name.startsWith("@ankdesh/")) continue;
    const published = expected.get(name);
    if (!published || entry.version !== published.version || entry.integrity !== published.integrity
        || entry.resolved !== `file:vendor/harness/${archiveFilename(published)}` || entry.link) {
      throw new Error(`Harness lock must use the vendored published archive for ${name}. Run npm ci after restoring the package lock.`);
    }
    const directory = realpathSync(resolve(product, path));
    const location = relative(resolve(product, "node_modules"), directory);
    if (location === ".." || location.startsWith("../") || isAbsolute(location)) {
      throw new Error(`Harness package ${name} points outside the installed node_modules directory. Run npm ci.`);
    }
    const installed = json(resolve(directory, "package.json"));
    if (installed.name !== name || installed.version !== published.version) {
      throw new Error(`Installed Harness package ${name} differs from the published release. Run npm ci.`);
    }
    count += 1;
  }
  if (!count) throw new Error("The package lock contains no published Harness packages.");
  return { releaseId: release.releaseId, installedPackages: count, publishedPackages: release.packages.length };
}

if (import.meta.main) console.log(JSON.stringify(checkHarnessPackages()));
