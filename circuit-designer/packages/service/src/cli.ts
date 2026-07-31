import { CircuitDesignerService } from "./server";

const port = Number(process.env.CIRCUIT_DESIGNER_PORT ?? 4100);
const host = process.env.CIRCUIT_DESIGNER_HOST ?? "127.0.0.1";
const service = new CircuitDesignerService();
await service.listen(port, host);
console.log(`Circuit Designer v1 listening on http://${host}:${port}/api/circuit-designer/v1 (ephemeral memory)`);

const shutdown = async (): Promise<void> => {
  await service.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
