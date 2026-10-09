import { spawnSync } from "node:child_process";
import { globSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const environment = { ...process.env };
if (process.platform !== "win32") {
  environment.TMPDIR = "/tmp";
  environment.TMP = "/tmp";
  environment.TEMP = "/tmp";
}
if (environment.SPEC2GDS_TEST_COVERAGE_DIR) {
  let failed = false;
  for (const path of globSync(["packages/*/package.json", "apps/*/package.json"])) {
    const manifest = JSON.parse(readFileSync(path, "utf8"));
    if (!manifest.scripts?.test) continue;
    const result = spawnSync(npmCommand, ["run", "test", "--workspace", manifest.name, "--",
      "--coverage", "--coverage.include=src/**", "--coverage.reporter=json-summary", "--coverage.reporter=html",
      `--coverage.reportsDirectory=${resolve(environment.SPEC2GDS_TEST_COVERAGE_DIR, manifest.name.replaceAll("@", "").replaceAll("/", "-"))}`,
    ], { env: environment, stdio: "inherit" });
    if (result.status !== 0) failed = true;
  }
  process.exit(failed ? 1 : 0);
}
const result = spawnSync(npmCommand, ["run", "test", "--workspaces", "--if-present"], {
  env: environment,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
