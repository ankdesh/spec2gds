import type { CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import type { LayoutOptions, LayoutResult } from "./index";

let nextRequestId = 0;

export function layoutCircuitGraphInWorker(graph: CircuitGraphSnapshot, options: LayoutOptions = {}): Promise<LayoutResult> {
  const worker = new Worker(new URL("./layout.worker.ts", import.meta.url), { type: "module" });
  const requestId = ++nextRequestId;
  return new Promise((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<{ requestId: number; result?: LayoutResult; error?: string }>) => {
      if (event.data.requestId !== requestId) return;
      worker.terminate();
      if (event.data.error) reject(new Error(event.data.error));
      else resolve(event.data.result!);
    };
    worker.onerror = (event) => { worker.terminate(); reject(event.error ?? new Error(event.message)); };
    worker.postMessage({ requestId, graph, options });
  });
}
