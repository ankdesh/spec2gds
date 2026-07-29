import { deflateSync } from "node:zlib";
import type { CircuitDocument, NetEndpoint, NodeGeometry, Point } from "@spec2gds/circuit-core";
import { endpointTerminalKey } from "@spec2gds/circuit-core";

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

function terminalPoint(
  document: CircuitDocument,
  geometry: Record<string, NodeGeometry>,
  endpoint: NetEndpoint,
): Point | undefined {
  if (endpoint.kind === "boundary") return undefined;
  const instance = document.design.instances.find((item) => item.id === endpoint.instance_id);
  const component = document.components.find((item) => item.id === instance?.component_id);
  const terminal = component?.terminals.find((item) => item.id === endpoint.terminal_id);
  const box = geometry[endpoint.instance_id];
  if (!component || !terminal || !box) return undefined;
  const siblings = component.terminals.filter((item) => item.direction === terminal.direction);
  const order = Math.max(0, siblings.findIndex((item) => item.id === terminal.id));
  const key = endpointTerminalKey(endpoint);
  const placement = document.layout.terminal_placements[key];
  const along = ((placement?.order ?? order) + 1) / (siblings.length + 1);
  const side = placement?.side ?? (terminal.direction === "input" ? "WEST" : "EAST");
  if (side === "WEST") return { x: box.x, y: box.y + box.height * along };
  if (side === "EAST") return { x: box.x + box.width, y: box.y + box.height * along };
  if (side === "NORTH") return { x: box.x + box.width * along, y: box.y };
  return { x: box.x + box.width * along, y: box.y + box.height };
}

/** Minimal deterministic Node rasterizer used by the reference service. */
export function renderCircuitPngBytes(document: CircuitDocument, selection?: string[]): Uint8Array {
  const geometry = materializedGeometry(document);
  const selected = selection ? new Set(selection) : undefined;
  const boxes = Object.entries(geometry).filter(([id]) => !selected || selected.has(id));
  const scale = 1;
  const width = Math.max(640, Math.ceil(Math.max(...boxes.map(([, box]) => box.x + box.width), 560) + 80));
  const height = Math.max(480, Math.ceil(Math.max(...boxes.map(([, box]) => box.y + box.height), 400) + 80));
  const pixels = new Uint8Array(width * height * 4);
  pixels.fill(255);
  const put = (x: number, y: number, color: [number, number, number, number]): void => {
    const px = Math.round(x * scale);
    const py = Math.round(y * scale);
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
  const netColor: [number, number, number, number] = [41, 146, 119, 255];
  for (const net of document.design.nets) {
    const route = document.layout.net_routes[net.id];
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
      const point = terminalPoint(document, geometry, endpoint);
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
  const border: [number, number, number, number] = [72, 96, 170, 255];
  const fill: [number, number, number, number] = [16, 27, 50, 255];
  for (const [, box] of boxes) {
    for (let y = Math.floor(box.y); y <= box.y + box.height; y += 1) {
      for (let x = Math.floor(box.x); x <= box.x + box.width; x += 1) {
        const edge = x <= box.x + 2 || x >= box.x + box.width - 2 || y <= box.y + 2 || y >= box.y + box.height - 2;
        put(x, y, edge ? border : fill);
      }
    }
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
