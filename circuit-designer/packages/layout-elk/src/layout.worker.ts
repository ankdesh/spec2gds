/// <reference lib="webworker" />
import type { CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import { layoutCircuitGraph, type LayoutOptions } from "./index";

self.onmessage = async (event: MessageEvent<{ requestId: number; graph: CircuitGraphSnapshot; options: LayoutOptions }>) => {
  try {
    const result = await layoutCircuitGraph(event.data.graph, event.data.options);
    self.postMessage({ requestId: event.data.requestId, result });
  } catch (error) {
    self.postMessage({ requestId: event.data.requestId, error: error instanceof Error ? error.message : String(error) });
  }
};
