/// <reference types="vite/client" />
import ELK from "elkjs/lib/elk-api.js";
import elkWorkerUrl from "elkjs/lib/elk-worker.min.js?url";
import type { CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import { layoutCircuitGraphWithEngine, type LayoutOptions, type LayoutResult } from "./index";

const browserElk = new ELK({ workerUrl: elkWorkerUrl });

export function layoutCircuitGraphInWorker(graph: CircuitGraphSnapshot, options: LayoutOptions = {}): Promise<LayoutResult> {
  return layoutCircuitGraphWithEngine(graph, browserElk, options);
}
