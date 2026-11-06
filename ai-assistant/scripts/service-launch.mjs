/** Apply resolved endpoints through a Harness patch, without network env settings. */
import { mkdirSync, writeFileSync, existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { randomUUID } from "node:crypto";
import { resolveConfig, listenerOverrides, parseLaunchArgs, endpointUrl } from "../../runtime/service-config.mjs";

export async function profileEntries(profile, anchor, home) {
  const require = createRequire(anchor);
  const { loadProfileDirectory, loadOptionalPatches, composeEntries } = await import(pathToFileURL(require.resolve("@ankdesh/dsh-app-boot")).href);
  const value = loadProfileDirectory("spec2gds", resolve(home, "profiles", profile), anchor);
  return composeEntries([...value.layers.map(layer => layer.patches), value.patches, loadOptionalPatches("spec2gds", resolve(home, "cordis.patch.yml")) ?? []]);
}

export function prepareServiceLaunch(args, directory, entries = []) {
  const { options, rest } = parseLaunchArgs(args, ["spec-root"]);
  if (rest.includes("--help")) console.log("AI Assistant launch options: --service-config PATH --host HOST --port PORT --public-host HOST --spec-root PATH (CLI > file > defaults). Other options go to the Harness.");
  const overrides = listenerOverrides("ai_assistant", options);
  if (options["public-host"] !== undefined) overrides.public_host = options["public-host"];
  if (options["spec-root"] !== undefined) overrides.spec_editor = { spec_root: resolve(process.cwd(), options["spec-root"]) };
  const config = resolveConfig(options["service-config"], overrides);
  if (options["spec-root"] !== undefined && (!existsSync(config.spec_editor.spec_root) || !statSync(config.spec_editor.spec_root).isDirectory())) throw new Error("Spec root must be an existing directory.");
  const allowlist = endpoint => [...new Set([
    endpointUrl(endpoint, config.public_host, { local: true }), endpointUrl(endpoint, config.public_host),
  ])].join(",");
  const specAllowlist = allowlist(config.spec_editor.service);
  const circuitAllowlist = allowlist(config.circuit_designer.service);
  const baseline = id => entries.find(row => row.id === id)?.config ?? {};
  const patch = [
    { id: "spec2gds-assistant", config: { ...baseline("spec2gds-assistant"), specAllowlist, circuitAllowlist, specDocumentRoot: config.spec_editor.spec_root } },
    { id: "event-http-sources", config: { ...baseline("event-http-sources"), allowedOrigins: [...new Set([specAllowlist, circuitAllowlist].join(",").split(",").map(value => new URL(value).origin))] } },
    { id: "webserver", config: { ...baseline("webserver"), host: config.ai_assistant.service.host, port: config.ai_assistant.service.port } },
  ];
  const run = resolve(directory, "temp", "TEMP_serve-all", randomUUID());
  mkdirSync(run, { recursive: true, mode: 0o700 });
  const overlay = resolve(run, "network.patch.yml");
  writeFileSync(overlay, JSON.stringify(patch, null, 2));
  writeFileSync(resolve(run, "services.json"), JSON.stringify(config, null, 2));
  return { config, args: ["--patch", overlay, ...rest], url: endpointUrl(config.ai_assistant.ui, config.public_host) };
}
