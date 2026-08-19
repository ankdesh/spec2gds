import { CircuitDesignerService } from "./server";
import { loadServiceRegistry, resolvedServiceDirectory } from "./service-registry";
import { StructuredLogger, loadObservabilityConfig } from "@spec2gds/observability/node";

const configured = loadServiceRegistry().circuit_designer.service;
const port = Number(process.env.CIRCUIT_DESIGNER_PORT ?? configured.port);
const host = process.env.CIRCUIT_DESIGNER_HOST ?? configured.host;
const logger = new StructuredLogger("circuit-designer", loadObservabilityConfig());
const service = new CircuitDesignerService({ serviceDirectory: resolvedServiceDirectory(), logger });
logger.event({ component: "process", event: "starting", message: "Starting Circuit Designer service", details: { host, port } });
await service.listen(port, host);
console.log(
  `Circuit Designer v1 listening on ${resolvedServiceDirectory().services.circuit_designer.service_url} (ephemeral memory)`,
);

const shutdown = async (): Promise<void> => {
  logger.event({ component: "process", event: "stopping", message: "Stopping Circuit Designer service" });
  await service.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
