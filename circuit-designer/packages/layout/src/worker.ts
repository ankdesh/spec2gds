/// <reference lib="webworker" />
import { layoutCircuitDocument } from "./index";
import type { LayoutWorkerRequest, LayoutWorkerResponse } from "./worker-protocol";

const cancelled = new Set<string>();
const send = (message: LayoutWorkerResponse): void => self.postMessage(message);

self.addEventListener("message", (event: MessageEvent<LayoutWorkerRequest>) => {
  const request = event.data;
  if (request.type === "cancel") {
    cancelled.add(request.request_id);
    return;
  }
  void (async () => {
    try {
      send({ type: "progress", request_id: request.request_id, phase: "placing", progress: 0.1 });
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (cancelled.delete(request.request_id)) {
        send({ type: "cancelled", request_id: request.request_id });
        return;
      }
      send({ type: "progress", request_id: request.request_id, phase: "routing", progress: 0.45 });
      const result = await layoutCircuitDocument(request.document, request.options);
      if (cancelled.delete(request.request_id)) {
        send({ type: "cancelled", request_id: request.request_id });
        return;
      }
      send({ type: "progress", request_id: request.request_id, phase: "complete", progress: 1 });
      send({
        type: "result",
        request_id: request.request_id,
        document: result.document,
        elapsed_ms: result.elapsed_ms,
      });
    } catch (reason) {
      send({
        type: "error",
        request_id: request.request_id,
        message: reason instanceof Error ? reason.message : String(reason),
      });
    }
  })();
});
