import type { CircuitGraphView } from "@spec2gds/circuit-core";
import type { LayoutResult } from "@spec2gds/circuit-layout";

export interface KeyedLayoutResult {
  graphKey: string;
  result: LayoutResult;
}

/** Identify the exact projected revision for which an asynchronous layout is valid. */
export function graphLayoutKey(graph: CircuitGraphView): string {
  return `${graph.document_id}\u0000${graph.design.id}\u0000${graph.revision}`;
}

export function matchingLayout(
  graph: CircuitGraphView | undefined,
  layout: KeyedLayoutResult | undefined,
): LayoutResult | undefined {
  if (!graph || !layout || layout.graphKey !== graphLayoutKey(graph)) return undefined;
  return layout.result;
}
