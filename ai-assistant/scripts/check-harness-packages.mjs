/** Check the installed Harness against the published package inventory. */
import { createHash } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const json = path => JSON.parse(readFileSync(path, "utf8"));

function archiveMatches(published, resolved, registry) {
  if (published.tarball) return resolved === published.tarball;
  // Promoted manifests pin archive integrity, while npm locks retain registry URLs.
  try {
    const archive = new URL(resolved);
    const prefix = `/download/${published.name}/${published.version}/`;
    return archive.origin === new URL(registry).origin
      && !archive.username && !archive.password && !archive.search && !archive.hash
      && archive.pathname.startsWith(prefix)
      && /^[a-f0-9]{40}$/.test(archive.pathname.slice(prefix.length));
  } catch {
    return false;
  }
}

export function checkHarnessPackages(product = root) {
  const releaseLock = json(resolve(product, "harness.lock.json"));
  const bytes = readFileSync(resolve(product, "releases/harness-release-manifest.json"));
  if (createHash("sha256").update(bytes).digest("hex") !== releaseLock.releaseManifestSha256) {
    throw new Error("Harness release inventory differs from harness.lock.json.");
  }
  const release = JSON.parse(bytes);
  if (release.releaseId !== releaseLock.releaseId) throw new Error("Harness release IDs do not match.");
  const registry = release.registry ?? releaseLock.registry ?? "https://npm.pkg.github.com";
  const expected = new Map(release.packages.map(value => [value.name, value]));
  const lock = json(resolve(product, "package-lock.json"));
  let count = 0;
  for (const [path, entry] of Object.entries(lock.packages)) {
    const name = path.split("node_modules/").at(-1);
    if (!name.startsWith("@ankdesh/")) continue;
    const published = expected.get(name);
    if (!published || entry.version !== published.version || entry.integrity !== published.integrity
        || !archiveMatches(published, entry.resolved, registry) || entry.link) {
      throw new Error(`Harness lock must use the published archive for ${name}. Run npm ci after restoring the package lock.`);
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
