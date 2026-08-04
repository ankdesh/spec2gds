import { CircuitDesignerService } from "./server";
import { loadServiceRegistry, resolvedServiceDirectory } from "./service-registry";

const configured = loadServiceRegistry().circuit_designer.service;
const port = Number(process.env.CIRCUIT_DESIGNER_PORT ?? configured.port);
const host = process.env.CIRCUIT_DESIGNER_HOST ?? configured.host;
const service = new CircuitDesignerService({ serviceDirectory: resolvedServiceDirectory() });
await service.listen(port, host);
console.log(`Circuit Designer v1 listening on http://${host}:${port}/api/circuit-designer/v1 (ephemeral memory)`);

const shutdown = async (): Promise<void> => {
  await service.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
