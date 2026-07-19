import type { CircuitGraphSnapshot } from "@spec2gds/circuit-core";
import type { LayoutResult } from "@spec2gds/circuit-layout-elk";

export interface KeyedLayoutResult {
  graphKey: string;
  result: LayoutResult;
}

/** Identify the exact graph revision for which an asynchronous layout is valid. */
export function graphLayoutKey(graph: CircuitGraphSnapshot): string {
  return `${graph.document_id}\u0000${graph.design.id}\u0000${graph.source_revision_hash}`;
}

export function matchingLayout(graph: CircuitGraphSnapshot | undefined, layout: KeyedLayoutResult | undefined): LayoutResult | undefined {
  if (!graph || !layout || layout.graphKey !== graphLayoutKey(graph)) return undefined;
  return layout.result;
}
