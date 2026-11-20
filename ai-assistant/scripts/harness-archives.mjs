/** Preserve the published release bytes while installing archives from this repository. */
import { createHash } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";

export function readHarnessRelease(product) {
  const lock = JSON.parse(readFileSync(resolve(product, "harness.lock.json"), "utf8"));
  const bytes = readFileSync(resolve(product, "releases/harness-release-manifest.json"));
  if (createHash("sha256").update(bytes).digest("hex") !== lock.releaseManifestSha256) {
    throw new Error("Harness release inventory differs from harness.lock.json.");
  }
  const release = JSON.parse(bytes);
  if (release.releaseId !== lock.releaseId) throw new Error("Harness release IDs do not match.");
  return release;
}

export function archiveFilename(published) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*\.tgz$/.test(published.file ?? "")) {
    throw new Error(`Invalid Harness archive filename for ${published.name}.`);
  }
  return published.file;
}

export function verifyHarnessArchives(release, directory) {
  const root = realpathSync(directory);
  const filenames = new Set();
  for (const published of release.packages) {
    const filename = archiveFilename(published);
    if (filenames.has(filename)) throw new Error(`Duplicate Harness archive: ${filename}`);
    filenames.add(filename);
    const path = realpathSync(resolve(root, filename));
    const location = relative(root, path);
    if (location === ".." || location.startsWith("../") || isAbsolute(location)) {
      throw new Error(`Harness archive points outside its vendor directory: ${filename}`);
    }
    const bytes = readFileSync(path);
    if (createHash("sha256").update(bytes).digest("hex") !== published.sha256
        || `sha512-${createHash("sha512").update(bytes).digest("base64")}` !== published.integrity) {
      throw new Error(`Harness archive checksum differs from the published release: ${filename}`);
    }
  }
  return { releaseId: release.releaseId, archives: filenames.size };
}

export function localizeHarnessLock(lock, release, directory = "vendor/harness") {
  const result = structuredClone(lock);
  const expected = new Map(release.packages.map(value => [value.name, value]));
  for (const [path, entry] of Object.entries(result.packages)) {
    const name = path.split("node_modules/").at(-1);
    if (!name.startsWith("@ankdesh/")) continue;
    const published = expected.get(name);
    if (!published || entry.link || entry.version !== published.version || entry.integrity !== published.integrity) {
      throw new Error(`Harness lock differs from the tested archive: ${name}`);
    }
    entry.resolved = `file:${directory}/${archiveFilename(published)}`;
  }
  return result;
}
