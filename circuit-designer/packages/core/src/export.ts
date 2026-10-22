import type {
  CircuitDocument,
  ComponentDefinition,
  NodeGeometry,
  Point,
  TerminalDefinition,
  TerminalPlacement,
} from "./types.generated";
import { endpointTerminalKey, terminalDefaultPlacement } from "./model";
import { analyzeCircuitTiming, effectiveCircuitTiming, sortedCycleEdges, stageLabel, type TimingPathAnalysis } from "./timing";
import { blueprintSlateTheme, type CircuitThemeDefinition } from "./theme";

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

const genericSvgRenderer: SvgComponentRenderer = ({ geometry, label, component }) => {
  const displayName = component.label || component.id;
  const maxChars = Math.max(4, Math.floor((geometry.width - 26) / 7.2));
  const eyebrow = displayName.length > maxChars ? `${displayName.slice(0, maxChars - 1)}…` : displayName;
  const titleChars = Math.max(4, Math.floor((geometry.width - 44) / 8));
  const shortLabel = compactCircuitInstanceLabel(label, titleChars);
  return [
    `<rect x="${geometry.x}" y="${geometry.y}" width="${geometry.width}" height="${geometry.height}" rx="2" class="component" data-component-id="${escapeXml(component.id)}"/>`,
    ...(displayName === label ? [] : [`<text x="${geometry.x + 13}" y="${geometry.y + 23}" class="component-eyebrow" data-component-id="${escapeXml(component.id)}"><title>${escapeXml(component.id)}</title>${escapeXml(eyebrow)}</text>`]),
    `<text x="${geometry.x + 13}" y="${geometry.y + 49}" class="component-symbol">${component.appearance.renderer_key === "register" ? "▣" : component.appearance.renderer_key === "constant" ? "1" : component.appearance.renderer_key === "not" ? "▷○" : "◈"}</text>`,
    `<text x="${geometry.x + 31}" y="${geometry.y + 49}" class="component-label"><title>${escapeXml(label)}</title>${escapeXml(shortLabel)}</text>`,
  ].join("");
};

export const defaultRendererRegistry = new RendererRegistry();
for (const key of ["generic", "buffer", "not", "and", "nand", "or", "nor", "xor", "xnor", "mux", "register", "constant", "splitter", "combiner"]) {
  defaultRendererRegistry.registerSvg(key, genericSvgRenderer);
}

export interface SvgExportOptions {
  selection?: string[];
  padding?: number;
  registry?: RendererRegistry;
  /** Effective boundary boxes from the same layout pass used by the canvas. */
  boundaryGeometry?: Record<string, NodeGeometry>;
  /** Explicit render profile. Defaults to the Blueprint Slate canvas palette. */
  theme?: CircuitThemeDefinition;
}

type ExportTerminal = {
  key: string;
  definition: Pick<TerminalDefinition, "id" | "label" | "direction" | "width">;
  geometry: NodeGeometry;
  placement: TerminalPlacement;
};

export function circuitTerminalDisplayLabel(terminal: Pick<TerminalDefinition, "label" | "width">): string {
  return typeof terminal.width === "string" ? `${terminal.label} ${terminal.width}` : terminal.width > 1 ? `${terminal.label} · ${terminal.width} bits` : terminal.label;
}

/** Retain the instance number when repeated definitions have long names. */
export function compactCircuitInstanceLabel(label: string, limit: number): string {
  if (label.length <= limit) return label;
  const suffix = label.match(/_\d+$/)?.[0] ?? "";
  return `${label.slice(0, Math.max(1, limit - suffix.length - 1))}…${suffix}`;
}

/** Shorten only the name; numeric and symbolic width information stays intact. */
export function compactCircuitTerminalLabel(terminal: Pick<TerminalDefinition, "label" | "width">, limit: number): string {
  const suffix = typeof terminal.width === "number" && terminal.width > 1
    ? ` · ${terminal.width}b` : circuitTerminalDisplayLabel({ ...terminal, label: "" });
  const available = Math.max(1, limit - suffix.length);
  const name = terminal.label.length > available ? `${terminal.label.slice(0, Math.max(0, available - 1))}…` : terminal.label;
  return name + suffix;
}

function terminalPoint(terminal: ExportTerminal): Point {
  const { geometry, placement } = terminal;
  const inset = 60 + placement.order * 20;
  if (placement.side === "EAST") return { x: geometry.x + geometry.width, y: geometry.y + Math.min(inset, geometry.height - 20) };
  if (placement.side === "WEST") return { x: geometry.x, y: geometry.y + Math.min(inset, geometry.height - 20) };
  if (placement.side === "NORTH") return { x: geometry.x + Math.min(inset, geometry.width - 20), y: geometry.y };
  return { x: geometry.x + Math.min(inset, geometry.width - 20), y: geometry.y + geometry.height };
}

function materializeInstanceGeometry(document: CircuitDocument): Record<string, NodeGeometry> {
  const result = structuredClone(document.layout.instance_geometry);
  let placementIndex = 0;
  for (const instance of document.design.instances) {
    if (result[instance.id]) continue;
    result[instance.id] = {
      x: 80 + (placementIndex % 5) * 260,
      y: 80 + Math.floor(placementIndex / 5) * 180,
      width: 180,
      height: 100,
      pinned: false,
    };
    placementIndex += 1;
  }
  return result;
}

function materializeBoundaryGeometry(
  document: CircuitDocument,
  instanceGeometry: Record<string, NodeGeometry>,
  supplied: Record<string, NodeGeometry> = {},
): Record<string, NodeGeometry> {
  const result = structuredClone(supplied);
  const boxes = Object.values(instanceGeometry);
  const minX = Math.min(...boxes.map((box) => box.x), 80);
  const minY = Math.min(...boxes.map((box) => box.y), 80);
  const maxX = Math.max(...boxes.map((box) => box.x + box.width), 260);
  const sideOrder = { NORTH: 0, EAST: 0, SOUTH: 0, WEST: 0 };
  for (const terminal of document.design.boundary_terminals) {
    const key = `boundary:${terminal.id}`;
    if (result[key] || result[terminal.id]) continue;
    const placement = document.layout.terminal_placements[key]
      ?? { side: terminal.direction === "input" ? "EAST" : terminal.direction === "output" ? "WEST" : "SOUTH", order: 0 } as TerminalPlacement;
    const order = sideOrder[placement.side]++;
    result[key] = placement.side === "EAST"
      ? { x: minX - 120, y: minY + order * 80, width: 20, height: 40, pinned: false }
      : placement.side === "WEST"
        ? { x: maxX + 100, y: minY + order * 80, width: 20, height: 40, pinned: false }
        : placement.side === "SOUTH"
          ? { x: minX + order * 80, y: minY - 100, width: 40, height: 20, pinned: false }
          : { x: minX + order * 80, y: Math.max(...boxes.map((box) => box.y + box.height), 180) + 80, width: 40, height: 20, pinned: false };
  }
  return result;
}

function exportTerminals(
  document: CircuitDocument,
  instanceGeometry: Record<string, NodeGeometry>,
  boundaryGeometry: Record<string, NodeGeometry>,
): ExportTerminal[] {
  const components = new Map(document.components.map((component) => [component.id, component]));
  const result: ExportTerminal[] = [];
  for (const instance of document.design.instances) {
    const component = components.get(instance.component_id);
    const geometry = instanceGeometry[instance.id];
    if (!component || !geometry) continue;
    for (const [order, definition] of component.terminals.entries()) {
      const key = `${instance.id}:${definition.id}`;
      result.push({
        key,
        definition,
        geometry,
        placement: document.layout.terminal_placements[key] ?? terminalDefaultPlacement(definition.direction, order),
      });
    }
  }
  for (const [order, definition] of document.design.boundary_terminals.entries()) {
    const key = `boundary:${definition.id}`;
    const geometry = boundaryGeometry[key] ?? boundaryGeometry[definition.id];
    if (!geometry) continue;
    result.push({
      key,
      definition,
      geometry,
      placement: document.layout.terminal_placements[key] ?? terminalDefaultPlacement(definition.direction, order),
    });
  }
  return result;
}

function terminalMarkup(terminal: ExportTerminal): string {
  const point = terminalPoint(terminal);
  const box = terminal.geometry;
  const fullLabel = circuitTerminalDisplayLabel(terminal.definition);
  const limit = terminal.key.startsWith("boundary:") ? 26 : 13;
  const label = escapeXml(compactCircuitTerminalLabel(terminal.definition, limit));
  const side = terminal.placement.side;
  const labelPosition = side === "WEST" ? { x: box.x + 8, y: point.y + 3, anchor: "start" }
    : side === "EAST" ? { x: box.x + box.width - 8, y: point.y + 3, anchor: "end" }
      : side === "NORTH" ? { x: point.x, y: box.y + 12, anchor: "middle" }
        : { x: point.x, y: box.y + box.height - 5, anchor: "middle" };
  return [
    `<text x="${labelPosition.x}" y="${labelPosition.y}" text-anchor="${labelPosition.anchor}" class="port-label"><title>${escapeXml(fullLabel)}</title>${label}</text>`,
    `<circle cx="${point.x}" cy="${point.y}" r="5" class="port" data-terminal-id="${escapeXml(terminal.key)}"/>`,
  ].join("");
}

function routeMarkup(document: CircuitDocument, terminalPoints: Map<string, Point>, netId: string): string {
  const route = document.layout.net_routes[netId];
  const net = document.design.nets.find((item) => item.id === netId);
  if (!net) return "";
  if (!route) {
    const points = net.endpoints.flatMap((endpoint) => {
      const point = terminalPoints.get(endpointTerminalKey(endpoint));
      return point ? [point] : [];
    });
    if (points.length < 2) return "";
    const root = points[0];
    return points.slice(1).map((point) => {
      const middleX = (root.x + point.x) / 2;
      return `<path d="M ${root.x} ${root.y} L ${middleX} ${root.y} L ${middleX} ${point.y} L ${point.x} ${point.y}" class="net" data-net-id="${escapeXml(netId)}"/>`;
    }).join("");
  }
  const vertices = new Map(route.vertices.map((vertex) => [vertex.id, vertex]));
  const degree = new Map(route.vertices.map((vertex) => [vertex.id, 0]));
  const paths = route.segments.flatMap((segment) => {
    const start = vertices.get(segment.from_vertex)?.point;
    const end = vertices.get(segment.to_vertex)?.point;
    if (!start || !end) return [];
    degree.set(segment.from_vertex, (degree.get(segment.from_vertex) ?? 0) + 1);
    degree.set(segment.to_vertex, (degree.get(segment.to_vertex) ?? 0) + 1);
    return [`<path d="M ${start.x} ${start.y} L ${end.x} ${end.y}" class="net${segment.locked ? " net--locked" : ""}" data-net-id="${escapeXml(netId)}"/>`];
  });
  const junctions = route.vertices
    .filter((vertex) => vertex.kind === "junction" && (degree.get(vertex.id) ?? 0) >= 3)
    .map((vertex) => `<circle cx="${vertex.point.x}" cy="${vertex.point.y}" r="3.5" class="junction"/>`);
  return [...paths, ...junctions].join("");
}

/** Deterministic SVG export using the same effective geometry and visual language as the React canvas. */
export function renderCircuitSvg(document: CircuitDocument, options: SvgExportOptions = {}): string {
  const instanceGeometry = materializeInstanceGeometry(document);
  const boundaryGeometry = materializeBoundaryGeometry(document, instanceGeometry, options.boundaryGeometry);
  const selected = options.selection ? new Set(options.selection) : undefined;
  const instances = document.design.instances.filter((instance) => !selected || selected.has(instance.id));
  const boundaries = document.design.boundary_terminals.filter((terminal) => !selected || selected.has(terminal.id) || selected.has(`boundary:${terminal.id}`));
  const visibleKeys = new Set([
    ...instances.map((instance) => instance.id),
    ...boundaries.map((terminal) => `boundary:${terminal.id}`),
  ]);
  const boxes = [
    ...instances.flatMap((instance) => instanceGeometry[instance.id] ? [instanceGeometry[instance.id]] : []),
    ...boundaries.flatMap((terminal) => boundaryGeometry[`boundary:${terminal.id}`] ?? boundaryGeometry[terminal.id]
      ? [boundaryGeometry[`boundary:${terminal.id}`] ?? boundaryGeometry[terminal.id]]
      : []),
  ];
  const terminals = exportTerminals(document, instanceGeometry, boundaryGeometry)
    .filter((terminal) => terminal.key.startsWith("boundary:")
      ? visibleKeys.has(terminal.key)
      : visibleKeys.has(terminal.key.slice(0, terminal.key.indexOf(":"))));
  const terminalPoints = new Map(terminals.map((terminal) => [terminal.key, terminalPoint(terminal)]));
  const nets = document.design.nets.filter((net) => !selected || selected.has(net.id) || net.endpoints.some((endpoint) => {
    const key = endpointTerminalKey(endpoint);
    return key.startsWith("boundary:") ? visibleKeys.has(key) : visibleKeys.has(key.slice(0, key.indexOf(":")));
  }));
  const routePoints = nets.flatMap((net) => document.layout.net_routes[net.id]?.vertices.map((vertex) => vertex.point) ?? []);
  const timing = effectiveCircuitTiming(document);
  const cycleEdges = document.timing ? sortedCycleEdges(timing) : [];
  const padding = options.padding ?? 40;
  const boundaryLabelExtents = terminals.filter(terminal => terminal.key.startsWith("boundary:")).flatMap(terminal => [terminal.geometry.x - 156, terminal.geometry.x + terminal.geometry.width + 156]);
  const xs = [...boxes.flatMap((box) => [box.x, box.x + box.width]), ...boundaryLabelExtents, ...routePoints.map((point) => point.x), ...cycleEdges.map((edge) => edge.x)];
  const ys = [...boxes.flatMap((box) => [box.y, box.y + box.height]), ...routePoints.map((point) => point.y)];
  const minX = (xs.length ? Math.min(...xs) : 0) - padding;
  const minY = (ys.length ? Math.min(...ys) : 0) - padding;
  const width = Math.max(1, (xs.length ? Math.max(...xs) : 400) - minX + padding);
  const height = Math.max(1, (ys.length ? Math.max(...ys) : 300) - minY + padding);
  const registry = options.registry ?? defaultRendererRegistry;
  const theme = options.theme ?? blueprintSlateTheme;
  const color = theme.colors;
  const components = new Map(document.components.map((component) => [component.id, component]));
  const netMarkup = nets.map((net) => routeMarkup(document, terminalPoints, net.id)).join("");
  const instanceMarkup = instances.flatMap((instance) => {
    const component = components.get(instance.component_id);
    const geometry = instanceGeometry[instance.id];
    if (!component || !geometry) return [];
    return [`<g data-instance-id="${escapeXml(instance.id)}">${registry.svg(component.appearance.renderer_key)({ component, geometry, label: instance.label })}</g>`];
  }).join("");
  const boundaryMarkup = boundaries.flatMap((terminal) => {
    const geometry = boundaryGeometry[`boundary:${terminal.id}`] ?? boundaryGeometry[terminal.id];
    if (!geometry) return [];
    return [`<g data-boundary-id="${escapeXml(terminal.id)}"><rect x="${geometry.x}" y="${geometry.y}" width="${geometry.width}" height="${geometry.height}" rx="2" class="component"/></g>`];
  }).join("");
  const portMarkup = terminals.map(terminalMarkup).join("");
  const cycleEdgeMarkup = [
    ...(cycleEdges.length
      ? [`<text x="${minX + 8}" y="${minY + 31}" class="stage-label">${escapeXml(stageLabel(timing, 0).toUpperCase())}</text>`]
      : []),
    ...cycleEdges.map((edge, index) => [
      `<line x1="${edge.x}" y1="${minY}" x2="${edge.x}" y2="${minY + height}" class="cycle-edge${edge.locked ? " cycle-edge--locked" : ""}"/>`,
      `<text x="${edge.x + 6}" y="${minY + 16}" class="cycle-edge-label">${escapeXml(edge.label ?? `CYCLE EDGE ${index + 1}`)}</text>`,
      `<text x="${edge.x + 6}" y="${minY + 31}" class="stage-label">${escapeXml(stageLabel(timing, index + 1).toUpperCase())}</text>`,
    ].join("")),
  ].join("");
  const timingAnalysis = analyzeCircuitTiming(document, boundaryGeometry);
  const pathLabels = new Map<string, { text: string; status: TimingPathAnalysis["status"] }>();
  for (const path of timingAnalysis.paths) {
    const current = pathLabels.get(path.net_id);
    if (path.status === "cdc") {
      pathLabels.set(path.net_id, { text: "CDC", status: path.status });
    } else if (path.status === "ready" && (path.cycles ?? 0) > 0 && current?.status !== "cdc") {
      const previousCycles = current?.status === "ready" ? Number(current.text.match(/\d+/)?.[0] ?? 0) : 0;
      const cycles = Math.max(previousCycles, path.cycles ?? 0);
      pathLabels.set(path.net_id, { text: `+${cycles} cycle${cycles === 1 ? "" : "s"}`, status: path.status });
    } else if (!current && path.status !== "ready") {
      pathLabels.set(path.net_id, { text: "TIMING ?", status: path.status });
    }
  }
  const latencyMarkup = nets.flatMap((net) => {
    const label = pathLabels.get(net.id);
    if (!label) return [];
    const points = document.layout.net_routes[net.id]?.vertices.map((vertex) => vertex.point)
      ?? net.endpoints.flatMap((endpoint) => terminalPoints.get(endpointTerminalKey(endpoint)) ?? []);
    if (!points.length) return [];
    const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
    const y = Math.min(...points.map((point) => point.y)) - 9;
    const labelWidth = Math.max(50, label.text.length * 6 + 12);
    return [`<g class="latency-label latency-label--${label.status}"><rect x="${x - labelWidth / 2}" y="${y - 11}" width="${labelWidth}" height="16" rx="4"/><text x="${x}" y="${y}" text-anchor="middle">${escapeXml(label.text)}</text></g>`];
  }).join("");
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.ceil(width)}" height="${Math.ceil(height)}" viewBox="${minX} ${minY} ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${escapeXml(document.label)}">`,
    `<defs><pattern id="canvas-grid" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="${color.grid}"/></pattern><filter id="component-shadow" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="${color.chrome}" flood-opacity="0.12"/></filter></defs>`,
    `<style>.canvas-background{fill:${color.canvas}}.component{fill:${color.surface};stroke:${color.border_strong};stroke-width:1.5;filter:url(#component-shadow)}.component-eyebrow{fill:${color.text_muted};font:11px ui-monospace,SFMono-Regular,Consolas,monospace}.component-label{fill:${color.text};font:600 16px Inter,system-ui,sans-serif}.component-symbol{fill:${color.primary};font:12px ui-monospace,monospace}.net{fill:none;stroke:${color.net};stroke-width:1.8}.net--locked{stroke:${color.net};stroke-width:2;stroke-dasharray:7 3}.junction{fill:${color.net}}.port{fill:${color.primary};stroke:${color.surface};stroke-width:2}.port-label{fill:${color.text_muted};font:10px ui-monospace,monospace}.cycle-edge{stroke:${color.net};stroke-width:2;stroke-dasharray:8 7}.cycle-edge--locked{stroke:${color.net};stroke-width:2.5}.cycle-edge-label{fill:${color.net};font:600 10px Inter,system-ui,sans-serif}.stage-label{fill:${color.text_muted};font:600 10px Inter,system-ui,sans-serif}.latency-label rect{fill:${color.surface};stroke:${color.border_strong}}.latency-label text{fill:${color.text};font:600 10px Inter,system-ui,sans-serif}.latency-label--cdc rect,.latency-label--backward rect,.latency-label--unavailable rect{fill:${color.warning_surface};stroke:${color.warning}}.latency-label--cdc text,.latency-label--backward text,.latency-label--unavailable text{fill:${color.warning}}</style>`,
    `<rect x="${minX}" y="${minY}" width="${width}" height="${height}" class="canvas-background"/>`,
    `<rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="url(#canvas-grid)"/>`,
    `<g class="cycle-edges">${cycleEdgeMarkup}</g><g class="nets">${netMarkup}</g><g class="instances">${instanceMarkup}${boundaryMarkup}</g><g class="ports">${portMarkup}</g><g class="latencies">${latencyMarkup}</g>`,
    "</svg>",
  ].join("");
}

export function exportCircuitJson(document: CircuitDocument): string {
  return `${JSON.stringify(document, null, 2)}\n`;
}

/** Browser PNG derivation from the exact SVG export. */
export async function renderCircuitPng(document: CircuitDocument, options: SvgExportOptions = {}): Promise<Blob> {
  if (typeof globalThis.document === "undefined" || typeof Image === "undefined") {
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
    canvas.width = Math.max(1, image.naturalWidth);
    canvas.height = Math.max(1, image.naturalHeight);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Unable to create a PNG drawing context.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Unable to encode PNG.")), "image/png"));
  } finally {
    URL.revokeObjectURL(url);
  }
}
