import {
  renderCircuitSvg,
  validateCircuitDocument,
  type CircuitDocument,
} from "@spec2gds/circuit-core";
import { layoutCircuitDocument } from "@spec2gds/circuit-layout";
import type { DesignTopologyLiveViewOptionsV1 } from "@spec2gds/document-core";

export interface RenderedDesignTopology {
  svg: string;
  width: number;
  height: number;
}

export function readDesignTopologyOptions(value: Record<string, unknown>): DesignTopologyLiveViewOptionsV1 | undefined {
  if (value.schema_version !== 1) return undefined;
  if (value.status !== "ready" && value.status !== "empty" && value.status !== "unavailable") return undefined;
  if (!Array.isArray(value.omitted_bus_items) || !value.omitted_bus_items.every((item) => typeof item === "string")) return undefined;
  if (!Array.isArray(value.omitted_ports) || !value.omitted_ports.every((item) => typeof item === "string")) return undefined;
  if (value.message !== undefined && typeof value.message !== "string") return undefined;
  if (value.status === "ready" && !value.circuit_document) return undefined;
  return value as unknown as DesignTopologyLiveViewOptionsV1;
}

export async function renderDesignTopology(document: CircuitDocument): Promise<RenderedDesignTopology> {
  const validation = validateCircuitDocument(document);
  if (!validation.valid) {
    const details = validation.diagnostics.map((diagnostic) => diagnostic.message).join(" ");
    throw new Error(details || "The derived circuit document is invalid.");
  }
  const layout = await layoutCircuitDocument(document, {
    direction: "RIGHT",
    gridSize: 20,
    preserveNodeGeometry: "none",
  });
  const svg = renderCircuitSvg(layout.document, { boundaryGeometry: layout.boundary_geometry });
  const dimensions = svg.match(/<svg[^>]+width="(\d+)"[^>]+height="(\d+)"/);
  if (!dimensions) throw new Error("The circuit renderer returned an SVG without dimensions.");
  return { svg, width: Number(dimensions[1]), height: Number(dimensions[2]) };
}

export function circuitSvgFilename(documentId: string, entityId: string): string {
  const stem = `${documentId}-${entityId}-circuit`
    .normalize("NFKD")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120) || "circuit";
  return `${stem}.svg`;
}
