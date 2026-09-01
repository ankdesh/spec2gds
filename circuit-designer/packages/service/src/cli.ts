import { CircuitDesignerService } from "./server";
import { loadServiceRegistry, resolvedServiceDirectory } from "./service-registry";
import { StructuredLogger, loadObservabilityConfig } from "@spec2gds/observability/node";

const legacyRegistry = process.env.SPEC2GDS_SERVICE_CONFIG ? loadServiceRegistry() : undefined;
const port = Number(process.env.CIRCUIT_DESIGNER_PORT ?? legacyRegistry?.circuit_designer.service.port ?? 6011);
const host = process.env.CIRCUIT_DESIGNER_HOST ?? legacyRegistry?.circuit_designer.service.host ?? "0.0.0.0";
const logger = new StructuredLogger("circuit-designer", loadObservabilityConfig());
const serviceDirectory = legacyRegistry ? resolvedServiceDirectory() : undefined;
const providerAllowlist = (process.env.CIRCUIT_DESIGNER_PROVIDER_ALLOWLIST ?? "")
  .split(",").map((value) => value.trim()).filter(Boolean);
const service = new CircuitDesignerService({ serviceDirectory, providerAllowlist, logger });
logger.event({ component: "process", event: "starting", message: "Starting Circuit Designer service", details: { host, port } });
await service.listen(port, host);
console.log(
  `Circuit Designer v1 listening on http://${host}:${port}/api/circuit-designer/v1 (ephemeral memory)`,
);

const shutdown = async (): Promise<void> => {
  logger.event({ component: "process", event: "stopping", message: "Stopping Circuit Designer service" });
  await service.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
