import { SqliteCircuitDesignerBackend } from "./sqlite";
import { CircuitDesignerService } from "./server";

const databasePath = process.env.CIRCUIT_DESIGNER_DATABASE ?? "circuit-designer.sqlite";
const port = Number(process.env.CIRCUIT_DESIGNER_PORT ?? 4100);
const host = process.env.CIRCUIT_DESIGNER_HOST ?? "127.0.0.1";
const backend = SqliteCircuitDesignerBackend.open(databasePath);
const service = new CircuitDesignerService({ backend });
await service.listen(port, host);
console.log(`Circuit Designer v1 listening on http://${host}:${port}/api/circuit-designer/v1`);

const shutdown = async (): Promise<void> => {
  await service.close();
  backend.close();
};
process.once("SIGINT", () => void shutdown());
process.once("SIGTERM", () => void shutdown());
