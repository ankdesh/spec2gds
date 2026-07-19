import { afterEach, describe, expect, test, vi } from "vitest";
import { simpleFixture } from "@spec2gds/circuit-core";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("browser ELK entry", () => {
  test("constructs the native worker asset instead of the bundled fake worker", async () => {
    const workerUrls: unknown[] = [];
    class WorkerStub {
      onmessage?: (event: MessageEvent) => void;

      constructor(url: unknown) {
        workerUrls.push(url);
      }

      postMessage(message: { id: number; cmd: string; graph?: object }) {
        const data = message.cmd === "layout" ? message.graph : {};
        queueMicrotask(() => this.onmessage?.({ data: { id: message.id, data } } as MessageEvent));
      }

      terminate() {}
    }
    vi.stubGlobal("Worker", WorkerStub);

    const { layoutCircuitGraphInWorker } = await import("../src/browser");
    const result = await layoutCircuitGraphInWorker(simpleFixture());

    expect(workerUrls).toHaveLength(1);
    expect(String(workerUrls[0])).toContain("elk-worker.min.js");
    expect(Object.keys(result.layout.node_geometry ?? {})).toHaveLength(2);
  });
});
