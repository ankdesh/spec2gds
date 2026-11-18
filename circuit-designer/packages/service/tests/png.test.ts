import { inflateSync } from "node:zlib";
import { expect, it } from "vitest";
import { circuitFrameGeometry, circuitTerminalPoint, createEmptyCircuitDocument, effectiveCircuitTerminalPlacements, projectDocument } from "@spec2gds/circuit-core";
import { renderCircuitPngBytes } from "../src/png";

it("renders the frame and boundary pins without clipping negative drawing coordinates", () => {
  const document = createEmptyCircuitDocument("boundary_png");
  document.design.boundary_terminals = [{ id: "input", label: "input", direction: "input", width: 1 }];
  const graph = projectDocument(document), placements = effectiveCircuitTerminalPlacements(graph);
  const frame = circuitFrameGeometry(graph, {}, placements);
  const png = Buffer.from(renderCircuitPngBytes(document));
  const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
  const chunks: Buffer[] = [];
  for (let offset = 8; offset < png.length;) {
    const length = png.readUInt32BE(offset);
    if (png.toString("ascii", offset + 4, offset + 8) === "IDAT") chunks.push(png.subarray(offset + 8, offset + 8 + length));
    offset += length + 12;
  }
  const pixels = inflateSync(Buffer.concat(chunks));
  const minX = frame.container_geometry.x - 40, minY = frame.container_geometry.y - 40;
  const pixel = (x: number, y: number) => {
    const offset = Math.round(y - minY) * (width * 4 + 1) + 1 + Math.round(x - minX) * 4;
    return [...pixels.subarray(offset, offset + 4)];
  };
  const point = circuitTerminalPoint(frame.boundary_geometry["boundary:input"], placements["boundary:input"]);
  expect(width).toBeGreaterThan(frame.container_geometry.width);
  expect(height).toBeGreaterThan(frame.container_geometry.height);
  expect(pixel(frame.container_geometry.x + 100, frame.container_geometry.y)).toEqual([72, 96, 170, 255]);
  expect(pixel(point.x, point.y)).toEqual([72, 96, 170, 255]);
  expect(pixel(point.x + 30, point.y)).toEqual([255, 255, 255, 255]);
});
