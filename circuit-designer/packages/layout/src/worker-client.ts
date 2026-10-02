/** Correlate asynchronous layout jobs with the request that created them.
 * Filter messages by this task's request ID and settle its promise once. The
 * application owns whether a finished result still applies to its current draft;
 * accepted circuit connectivity remains owned by the host operation engine. */
import type { CircuitDocument } from "@spec2gds/circuit-core";
import type { LayoutOptions } from "./index";
import type { LayoutWorkerRequest, LayoutWorkerResponse } from "./worker-protocol";

export interface LayoutTask {
  result: Promise<{ document: CircuitDocument; elapsed_ms: number }>;
  cancel(): void;
}

export interface LayoutTaskOptions {
  layout?: LayoutOptions;
  onProgress?: (phase: "placing" | "routing" | "complete", progress: number) => void;
  workerFactory?: () => Worker;
}

let requestSequence = 0;

/** Start cancellable automatic placement/routing in an isolated Web Worker. */
export function createLayoutTask(
  document: CircuitDocument,
  options: LayoutTaskOptions = {},
): LayoutTask {
  const worker = options.workerFactory?.()
    ?? new Worker(new URL("./worker.ts", import.meta.url), { type: "module", name: "circuit-layout" });
  const requestId = `layout_${++requestSequence}`;
  let settled = false;
  const result = new Promise<{ document: CircuitDocument; elapsed_ms: number }>((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<LayoutWorkerResponse>) => {
      const message = event.data;
      if (message.request_id !== requestId) return;
      if (message.type === "progress") {
        options.onProgress?.(message.phase, message.progress);
        return;
      }
      settled = true;
      worker.terminate();
      if (message.type === "result") resolve({ document: message.document, elapsed_ms: message.elapsed_ms });
      else if (message.type === "cancelled") reject(new DOMException("Circuit layout was cancelled.", "AbortError"));
      else reject(new Error(message.message));
    };
    worker.onerror = (event) => {
      settled = true;
      worker.terminate();
      reject(new Error(event.message));
    };
    const request: LayoutWorkerRequest = {
      type: "layout",
      request_id: requestId,
      document,
      ...(options.layout ? { options: options.layout } : {}),
    };
    worker.postMessage(request);
  });
  return {
    result,
    cancel: () => {
      if (settled) return;
      const request: LayoutWorkerRequest = { type: "cancel", request_id: requestId };
      // Cancellation is a protocol request; the promise settles only when the
      // worker replies. Posting this message does not synchronously stop work.
      worker.postMessage(request);
    },
  };
}
