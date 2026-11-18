import {
  renderCircuitSvg,
  validateCircuitDocument,
  publicFilenameStem,
  getCircuitTheme,
  projectDocument,
  type CircuitDocument,
  type CircuitContainerPresentation,
} from "@spec2gds/circuit-core";
import { layoutCircuitGraph } from "@spec2gds/circuit-layout";
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

export async function renderDesignTopology(document: CircuitDocument, themeId = "blueprint-slate", container?: CircuitContainerPresentation | false): Promise<RenderedDesignTopology> {
  const validation = validateCircuitDocument(document);
  if (!validation.valid) {
    const details = validation.diagnostics.map((diagnostic) => diagnostic.message).join(" ");
    throw new Error(details || "The derived circuit document is invalid.");
  }
  const layout = await layoutCircuitGraph(projectDocument(document), {
    direction: document.layout.direction,
    gridSize: document.layout.grid_size,
    preserveNodeGeometry: "all",
  });
  const renderedDocument = structuredClone(document);
  renderedDocument.layout.instance_geometry = layout.layout.node_geometry;
  renderedDocument.layout.terminal_placements = layout.layout.terminal_placements;
  renderedDocument.layout.net_routes = layout.layout.net_routes;
  const svg = renderCircuitSvg(renderedDocument, { boundaryGeometry: layout.boundary_geometry, containerGeometry: layout.container_geometry, container, theme: getCircuitTheme(themeId) });
  const dimensions = svg.match(/<svg[^>]+width="(\d+)"[^>]+height="(\d+)"/);
  if (!dimensions) throw new Error("The circuit renderer returned an SVG without dimensions.");
  return { svg, width: Number(dimensions[1]), height: Number(dimensions[2]) };
}

export function circuitSvgFilename(documentName: string, entityName: string): string {
  const stem = `${publicFilenameStem(documentName).slice(0, 50)}-${publicFilenameStem(entityName, "design").slice(0, 50)}-circuit`;
  return `${stem}.svg`;
}

/** Fit an interface diagram without enlarging it or changing saved geometry. */
export function componentPreviewSize(width: number, height: number, availableWidth: number) {
  const cardWidth = Math.max(0, Math.min(Math.max(0, availableWidth), Math.min(640, Math.max(320, width + 32))));
  const scale = width > 0 && height > 0 ? Math.max(0, Math.min(1, (cardWidth - 32) / width, 288 / height)) : 0;
  return { cardWidth, imageWidth: width * scale, imageHeight: height * scale,
    viewportHeight: Math.min(320, Math.max(120, height * scale + 32)) };
}
