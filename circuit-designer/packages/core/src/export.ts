import type { CircuitDocument, ComponentDefinition, NodeGeometry, Point } from "./types.generated";
import { endpointTerminalKey } from "./model";

export interface SvgRendererContext {
  component: ComponentDefinition;
  geometry: NodeGeometry;
  label: string;
}

export type SvgComponentRenderer = (context: SvgRendererContext) => string;

export class RendererRegistry {
  private readonly svgRenderers = new Map<string, SvgComponentRenderer>();

  registerSvg(key: string, renderer: SvgComponentRenderer): void {
    this.svgRenderers.set(key, renderer);
  }

  svg(key: string): SvgComponentRenderer {
    return this.svgRenderers.get(key) ?? genericSvgRenderer;
  }
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&apos;");
}

const genericSvgRenderer: SvgComponentRenderer = ({ geometry, label }) => [
  `<rect x="${geometry.x}" y="${geometry.y}" width="${geometry.width}" height="${geometry.height}" rx="8" class="component"/>`,
  `<text x="${geometry.x + geometry.width / 2}" y="${geometry.y + 24}" text-anchor="middle" class="component-label">${escapeXml(label)}</text>`,
].join("");

export const defaultRendererRegistry = new RendererRegistry();
for (const key of ["generic", "buffer", "not", "and", "nand", "or", "nor", "xor", "xnor", "mux", "register", "constant", "splitter", "combiner"]) {
  defaultRendererRegistry.registerSvg(key, genericSvgRenderer);
}

function terminalPoint(document: CircuitDocument, terminalKey: string): Point | undefined {
  if (terminalKey.startsWith("boundary:")) return undefined;
  const separator = terminalKey.indexOf(":");
  const instanceId = terminalKey.slice(0, separator);
  const terminalId = terminalKey.slice(separator + 1);
  const instance = document.design.instances.find((item) => item.id === instanceId);
  const component = document.components.find((item) => item.id === instance?.component_id);
  const geometry = document.layout.instance_geometry[instanceId];
  const terminal = component?.terminals.find((item) => item.id === terminalId);
  if (!geometry || !terminal) return undefined;
  const terminals = component!.terminals.filter((item) => item.direction === terminal.direction);
  const order = Math.max(0, terminals.findIndex((item) => item.id === terminalId));
  const placement = document.layout.terminal_placements[terminalKey];
  const side = placement?.side ?? (terminal.direction === "input" ? "WEST" : "EAST");
  const along = ((placement?.order ?? order) + 1) / (terminals.length + 1);
  if (side === "WEST") return { x: geometry.x, y: geometry.y + geometry.height * along };
  if (side === "EAST") return { x: geometry.x + geometry.width, y: geometry.y + geometry.height * along };
  if (side === "NORTH") return { x: geometry.x + geometry.width * along, y: geometry.y };
  return { x: geometry.x + geometry.width * along, y: geometry.y + geometry.height };
}

function routePath(document: CircuitDocument, netId: string): string[] {
  const route = document.layout.net_routes[netId];
  if (!route) {
    const net = document.design.nets.find((item) => item.id === netId);
    const points = net?.endpoints.flatMap((item) => {
      const point = terminalPoint(document, endpointTerminalKey(item));
      return point ? [point] : [];
    }) ?? [];
    if (points.length < 2) return [];
    const root = points[0];
    return points.slice(1).map((point) =>
      `M ${root.x} ${root.y} L ${(root.x + point.x) / 2} ${root.y} L ${(root.x + point.x) / 2} ${point.y} L ${point.x} ${point.y}`);
  }
  const vertices = new Map(route.vertices.map((item) => [item.id, item]));
  return route.segments.flatMap((segment) => {
    const start = vertices.get(segment.from_vertex)?.point;
    const end = vertices.get(segment.to_vertex)?.point;
    return start && end ? [`M ${start.x} ${start.y} L ${end.x} ${end.y}`] : [];
  });
}

export interface SvgExportOptions {
  selection?: string[];
  padding?: number;
  registry?: RendererRegistry;
}

/** Deterministic SVG export directly from canonical logical geometry. */
export function renderCircuitSvg(document: CircuitDocument, options: SvgExportOptions = {}): string {
  const renderDocument = structuredClone(document);
  let placementIndex = 0;
  for (const instance of renderDocument.design.instances) {
    if (renderDocument.layout.instance_geometry[instance.id]) continue;
    const column = placementIndex % 5;
    const row = Math.floor(placementIndex / 5);
    renderDocument.layout.instance_geometry[instance.id] = {
      x: 80 + column * 260,
      y: 80 + row * 180,
      width: 180,
      height: 100,
      pinned: false,
    };
    placementIndex += 1;
  }
  const selected = options.selection ? new Set(options.selection) : undefined;
  const instances = renderDocument.design.instances.filter((item) => !selected || selected.has(item.id));
  const geometry = instances.flatMap((item) => {
    const value = renderDocument.layout.instance_geometry[item.id];
    return value ? [value] : [];
  });
  const padding = options.padding ?? 40;
  const minX = Math.min(0, ...geometry.map((item) => item.x)) - padding;
  const minY = Math.min(0, ...geometry.map((item) => item.y)) - padding;
  const maxX = Math.max(400, ...geometry.map((item) => item.x + item.width)) + padding;
  const maxY = Math.max(300, ...geometry.map((item) => item.y + item.height)) + padding;
  const registry = options.registry ?? defaultRendererRegistry;
  const components = new Map(renderDocument.components.map((item) => [item.id, item]));
  const visibleInstances = new Set(instances.map((item) => item.id));
  const nets = renderDocument.design.nets.filter((net) =>
    !selected || net.endpoints.some((item) => item.kind === "instance" && visibleInstances.has(item.instance_id)));
  const netMarkup = nets.flatMap((net) => routePath(renderDocument, net.id)
    .map((path) => `<path d="${path}" class="net" data-net-id="${escapeXml(net.id)}"/>`)).join("");
  const instanceMarkup = instances.flatMap((instance) => {
    const component = components.get(instance.component_id);
    const box = renderDocument.layout.instance_geometry[instance.id];
    if (!component || !box) return [];
    return [`<g data-instance-id="${escapeXml(instance.id)}">${registry.svg(component.appearance.renderer_key)({
      component,
      geometry: box,
      label: instance.label,
    })}</g>`];
  }).join("");
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${maxX - minX} ${maxY - minY}" role="img" aria-label="${escapeXml(document.label)}">`,
    "<style>.component{fill:#101b32;stroke:#6f8cff;stroke-width:2}.component-label{fill:#f4f7ff;font:14px sans-serif}.net{fill:none;stroke:#4cc9a4;stroke-width:2}</style>",
    `<g class="nets">${netMarkup}</g><g class="instances">${instanceMarkup}</g>`,
    "</svg>",
  ].join("");
}

export function exportCircuitJson(document: CircuitDocument): string {
  return `${JSON.stringify(document, null, 2)}\n`;
}

/** Browser PNG derivation; the Node service may supply its own SVG rasterizer. */
export async function renderCircuitPng(document: CircuitDocument, options: SvgExportOptions = {}): Promise<Blob> {
  if (typeof document === "undefined" || typeof Image === "undefined") {
    throw new Error("PNG rasterization requires a browser canvas implementation.");
  }
  const svg = renderCircuitSvg(document, options);
  const image = new Image();
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Unable to decode generated SVG."));
      image.src = url;
    });
    const canvas = globalThis.document.createElement("canvas");
    canvas.width = image.naturalWidth || 1200;
    canvas.height = image.naturalHeight || 800;
    canvas.getContext("2d")?.drawImage(image, 0, 0);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Unable to encode PNG.")), "image/png"));
  } finally {
    URL.revokeObjectURL(url);
  }
}
