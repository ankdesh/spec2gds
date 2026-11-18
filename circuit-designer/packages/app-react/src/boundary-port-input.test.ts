import { expect, it } from "vitest";
import { parseBoundaryPortWidth } from "./boundary-port-input";

it("accepts the supported numeric and symbolic wire shapes", () => {
  expect(parseBoundaryPortWidth("16")).toBe(16);
  expect(parseBoundaryPortWidth("7:0")).toBe("[7:0]");
  expect(parseBoundaryPortWidth("[DATA_WIDTH-1:0]")).toBe("[DATA_WIDTH-1:0]");
  expect(parseBoundaryPortWidth("DATA_WIDTH")).toBe("DATA_WIDTH");
});

it("rejects empty, fractional, negative, zero, and unsafe numeric widths", () => {
  for (const value of ["", "0", "-1", "1.5", "9007199254740992"]) expect(() => parseBoundaryPortWidth(value)).toThrow();
});
