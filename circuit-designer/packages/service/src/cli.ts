import { resolve } from "node:path";
import { CircuitDesignerService } from "./server";
import { resolvedServiceDirectory } from "./service-registry";
import { StructuredLogger, loadObservabilityConfig } from "@spec2gds/observability/node";

import { resolveConfig, parseLaunchArgs, listenerOverrides, endpointUrl } from "../../../../runtime/service-config.mjs";
const { options, rest } = parseLaunchArgs(process.argv.slice(2));
if (rest.includes("--help")) {
  console.log("Circuit Designer service: [--service-config PATH] [--host HOST] [--port PORT] [--public-host HOST] [--no-shared-directory]");
  process.exit(0);
}
if (rest.some(value => value !== "--no-shared-directory")) throw new Error(`Unknown arguments: ${rest.join(" ")}`);
const config = resolveConfig(options["service-config"], {
  ...listenerOverrides("circuit_designer", options),
  ...(options["public-host"] === undefined ? {} : { public_host: options["public-host"] }),
});
const { host, port } = config.circuit_designer.service;
const logger = new StructuredLogger("circuit-designer", loadObservabilityConfig(options["service-config"], config));
const serviceDirectory = rest.includes("--no-shared-directory") ? undefined : resolvedServiceDirectory(config);
const providerAllowlist = config.circuit_designer.provider_allowlist ?? [];
const preferencesPath = process.env.CIRCUIT_DESIGNER_PREFERENCES_FILE
  ? resolve(process.env.CIRCUIT_DESIGNER_PREFERENCES_FILE) : config.circuit_designer.preferences_file;
const service = new CircuitDesignerService({ serviceDirectory, providerAllowlist, preferencesPath, logger });
logger.event({ component: "process", event: "starting", message: "Starting Circuit Designer service", details: { host, port } });
await service.listen(port, host);
console.log(
  `Circuit Designer v1 listening on ${endpointUrl(config.circuit_designer.service, config.public_host)} (ephemeral memory)`,
);

const shutdown = async (): Promise<void> => {
  logger.event({ component: "process", event: "stopping", message: "Stopping Circuit Designer service" });
  await service.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
