import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, cpSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolveConfig, endpointUrl, parseLaunchArgs } from "./service-config.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
mkdirSync(resolve(root, "temp"), { recursive: true });
const directory = mkdtempSync(resolve(root, "temp/TEMP_config-"));
const cases = JSON.parse(readFileSync(resolve(root, "tests/fixtures/service-config.json"), "utf8"));
for (const item of cases) test(item.name, () => {
  for (const key of ["SPEC2GDS_SERVICE_CONFIG", "SPEC2GDS_PUBLIC_HOST", "CIRCUIT_DESIGNER_HOST", "ASSISTANT_PORT"]) process.env[key] = "obsolete-invalid-value";
  const path = resolve(directory, `${item.name}.json`);
  writeFileSync(path, JSON.stringify({ public_host: "design.test", ...item.config }));
  if (item.error) assert.throws(() => resolveConfig(path, item.overrides), new RegExp(item.error));
  else {
    const config = resolveConfig(path, item.overrides);
    assert.equal(endpointUrl(config.spec_editor.service, config.public_host), item.url);
    assert.equal(endpointUrl(config.spec_editor.service, config.public_host, { local: true }), item.local);
    const snapshot = resolve(directory, `${item.name}-snapshot.json`);
    writeFileSync(snapshot, JSON.stringify(config));
    assert.deepEqual(resolveConfig(snapshot), config);
  }
});
test("explicit missing files and invalid CLI ports fail", () => {
  assert.throws(() => resolveConfig(resolve(directory, "missing.json")), /ENOENT/);
  assert.throws(() => parseLaunchArgs(["--port", "0"]), /port/);
  const original = process.env.INIT_CWD;
  process.env.INIT_CWD = directory;
  assert.equal(parseLaunchArgs(["--service-config", "defaults.json"]).options["service-config"], resolve(directory, "defaults.json"));
  if (original === undefined) delete process.env.INIT_CWD; else process.env.INIT_CWD = original;
  assert.deepEqual(parseLaunchArgs(["--", "--port", "0"]).rest, ["--", "--port", "0"]);
  assert.deepEqual(parseLaunchArgs(["--host=::1", "--no-open", "--port", "6420"]), { options: { host: "::1", port: 6420 }, rest: ["--no-open"] });
});
test("packaged Assistant resolver works without a checkout", async () => {
  const release = resolve(directory, "release");
  mkdirSync(resolve(release, "scripts"), { recursive: true });
  cpSync(resolve(root, "runtime/service-config.cjs"), resolve(release, "runtime/service-config.cjs"), { recursive: true });
  cpSync(resolve(root, "runtime/service-config.mjs"), resolve(release, "runtime/service-config.mjs"), { recursive: true });
  cpSync(resolve(root, "runtime/src/spec2gds_runtime/service-defaults.json"), resolve(release, "runtime/src/spec2gds_runtime/service-defaults.json"), { recursive: true });
  const adapter = readFileSync(resolve(root, "ai-assistant/scripts/service-launch.mjs"), "utf8").replace("../../runtime/", "../runtime/");
  writeFileSync(resolve(release, "scripts/service-launch.mjs"), adapter);
  const { prepareServiceLaunch } = await import(pathToFileURL(resolve(release, "scripts/service-launch.mjs")).href);
  const configPath = resolve(directory, "defaults.json");
  const launch = prepareServiceLaunch(["--service-config", configPath, "--port", "6543", "--public-host", "release.test", "--no-open"], release, [{ id: "event-http-sources", config: { tickMillis: 1000 } }, { id: "spec2gds-assistant", config: { provider: "openai", maxStepsPerTurn: 3 } }]);
  assert.equal(launch.url, "http://release.test:6543");
  const patch = JSON.parse(readFileSync(launch.args[1], "utf8"));
  assert.deepEqual(patch.find(row => row.id === "webserver").config, { host: "0.0.0.0", port: 6543 });
  assert.equal(patch.find(row => row.id === "event-http-sources").config.tickMillis, 1000);
  assert.equal(patch.find(row => row.id === "spec2gds-assistant").config.provider, "openai");
  assert.equal(patch.find(row => row.id === "spec2gds-assistant").config.specAllowlist, "http://127.0.0.1:6010,http://release.test:6010");
});
