import { deflateSync } from "node:zlib";
import type { CircuitDocument, NetEndpoint, NodeGeometry, Point, TerminalPlacement } from "@spec2gds/circuit-core";
import { endpointTerminalKey, reanchorCircuitFrameRoutes, circuitTerminalPoint, circuitFrameGeometry, effectiveCircuitTerminalPlacements, projectDocument, CIRCUIT_FRAME_HEADER_HEIGHT } from "@spec2gds/circuit-core";

function crc32(data: Uint8Array): number {
  let value = 0xffffffff;
  for (const byte of data) {
    value ^= byte;
    for (let bit = 0; bit < 8; bit += 1) value = (value >>> 1) ^ (0xedb88320 & -(value & 1));
  }
  return (value ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Uint8Array): Buffer {
  const typeBytes = Buffer.from(type, "ascii");
  const result = Buffer.alloc(12 + data.length);
  result.writeUInt32BE(data.length, 0);
  typeBytes.copy(result, 4);
  Buffer.from(data).copy(result, 8);
  result.writeUInt32BE(crc32(Buffer.concat([typeBytes, Buffer.from(data)])), 8 + data.length);
  return result;
}

function materializedGeometry(document: CircuitDocument): Record<string, NodeGeometry> {
  const result = structuredClone(document.layout.instance_geometry);
  let index = 0;
  for (const instance of document.design.instances) {
    if (result[instance.id]) continue;
    result[instance.id] = {
      x: 80 + (index % 5) * 260,
      y: 80 + Math.floor(index / 5) * 180,
      width: 180,
      height: 100,
    };
    index += 1;
  }
  return result;
}

function terminalPoint(geometry: Record<string, NodeGeometry>, boundaryGeometry: Record<string, NodeGeometry>, placements: Record<string, TerminalPlacement>, endpoint: NetEndpoint): Point | undefined {
  const key = endpointTerminalKey(endpoint);
  const box = endpoint.kind === "boundary" ? boundaryGeometry[key] : geometry[endpoint.instance_id];
  const placement = placements[key];
  return box && placement ? circuitTerminalPoint(box, placement) : undefined;
}

/** Minimal deterministic Node rasterizer used by the reference service. */
export function renderCircuitPngBytes(document: CircuitDocument, selection?: string[], showContainer = true): Uint8Array {
  const geometry = materializedGeometry(document);
  const graph = projectDocument(document);
  const placements = effectiveCircuitTerminalPlacements(graph);
  const frame = circuitFrameGeometry(graph, geometry, placements, document.layout.net_routes, document.layout.grid_size);
  const routes = reanchorCircuitFrameRoutes(graph, geometry, frame.boundary_geometry, placements);
  const selected = selection ? new Set(selection) : undefined;
  const boxes = Object.entries(geometry).filter(([id]) => !selected || selected.has(id));
  const visibleBoundaries = graph.terminals.filter(terminal => !terminal.node_id && (!selected || selected.has(terminal.id) || selected.has(terminal.id.slice(9))));
  const terminalPoints = visibleBoundaries.map(terminal => circuitTerminalPoint(frame.boundary_geometry[terminal.id], placements[terminal.id]));
  const allBoxes = [...boxes.map(([, box]) => box), ...(!selected && showContainer ? [frame.container_geometry] : [])];
  const routePoints = Object.values(routes).flatMap(route => route.vertices.map(vertex => vertex.point));
  const points = [...terminalPoints, ...routePoints];
  const minX = Math.min(...allBoxes.map(box => box.x), ...points.map(point => point.x), 0) - 40;
  const minY = Math.min(...allBoxes.map(box => box.y), ...points.map(point => point.y), 0) - 40;
  const width = Math.max(640, Math.ceil(Math.max(...allBoxes.map(box => box.x + box.width), ...points.map(point => point.x), 560) - minX + 40));
  const height = Math.max(480, Math.ceil(Math.max(...allBoxes.map(box => box.y + box.height), ...points.map(point => point.y), 400) - minY + 40));
  const pixels = new Uint8Array(width * height * 4);
  pixels.fill(255);
  const put = (x: number, y: number, color: [number, number, number, number]): void => {
    const px = Math.round(x - minX);
    const py = Math.round(y - minY);
    if (px < 0 || py < 0 || px >= width || py >= height) return;
    pixels.set(color, (py * width + px) * 4);
  };
  const line = (from: Point, to: Point, color: [number, number, number, number]): void => {
    const steps = Math.max(Math.abs(to.x - from.x), Math.abs(to.y - from.y), 1);
    for (let index = 0; index <= steps; index += 1) {
      const ratio = index / steps;
      const x = from.x + (to.x - from.x) * ratio;
      const y = from.y + (to.y - from.y) * ratio;
      put(x, y, color);
      put(x + 1, y, color);
    }
  };
  const border: [number, number, number, number] = [72, 96, 170, 255];
  if (!selected && showContainer) {
    const { x, y, width: w, height: h } = frame.container_geometry;
    line({ x, y }, { x: x + w, y }, border);
    line({ x: x + w, y }, { x: x + w, y: y + h }, border);
    line({ x: x + w, y: y + h }, { x, y: y + h }, border);
    line({ x, y: y + h }, { x, y }, border);
    line({ x, y: y + CIRCUIT_FRAME_HEADER_HEIGHT }, { x: x + w, y: y + CIRCUIT_FRAME_HEADER_HEIGHT }, border);
  }
  const netColor: [number, number, number, number] = [41, 146, 119, 255];
  for (const net of document.design.nets) {
    const route = routes[net.id];
    if (route) {
      const vertices = new Map(route.vertices.map((item) => [item.id, item.point]));
      for (const segment of route.segments) {
        const from = vertices.get(segment.from_vertex);
        const to = vertices.get(segment.to_vertex);
        if (from && to) line(from, to, netColor);
      }
      continue;
    }
    const points = net.endpoints.flatMap((endpoint) => {
      const point = terminalPoint(geometry, frame.boundary_geometry, placements, endpoint);
      return point ? [point] : [];
    });
    const root = points[0];
    for (const point of points.slice(1)) {
      const middle = { x: (root.x + point.x) / 2, y: root.y };
      line(root, middle, netColor);
      line(middle, { x: middle.x, y: point.y }, netColor);
      line({ x: middle.x, y: point.y }, point, netColor);
    }
  }
  const fill: [number, number, number, number] = [16, 27, 50, 255];
  for (const [, box] of boxes) {
    for (let y = Math.floor(box.y); y <= box.y + box.height; y += 1) {
      for (let x = Math.floor(box.x); x <= box.x + box.width; x += 1) {
        const edge = x <= box.x + 2 || x >= box.x + box.width - 2 || y <= box.y + 2 || y >= box.y + box.height - 2;
        put(x, y, edge ? border : fill);
      }
    }
  }
  for (const point of terminalPoints) {
    for (let y = -5; y <= 5; y += 1) for (let x = -5; x <= 5; x += 1) if (x * x + y * y <= 25) put(point.x + x, point.y + y, border);
  }
  const scanlines = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const offset = y * (width * 4 + 1);
    scanlines[offset] = 0;
    Buffer.from(pixels.subarray(y * width * 4, (y + 1) * width * 4)).copy(scanlines, offset + 1);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 6;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(scanlines, { level: 9 })),
    chunk("IEND", new Uint8Array()),
  ]);
}
