import { expect, it } from "vitest";
import type { DocumentTable } from "@spec2gds/document-core";
import { portInputFromRow, rowText } from "../src/port-input";

function row(values: Record<string, string | null>): DocumentTable["rows"][number] {
  return { row_id: "saved-row", cells: Object.fromEntries(Object.entries(values).map(([key, value]) => [key, {
    kind: "text", value, presence: value ? "explicit" : "absent", schema_path: "/port", reference_anchor: "",
  }])) } as DocumentTable["rows"][number];
}

it.each(["", "31:0", "WIDTH-1:0", "0:7"])("keeps a wire range intact in a private draft", range => {
  const input = portInputFromRow(row({ name: "IRQ_ID", family: "wire", description: "Saved text", direction: "out", range }));
  expect(input).toEqual({ name: "IRQ_ID", family: "wire", description: "Saved text", direction: "out", range: range || null });
});

it.each(["requires", "provides", "both"])("preserves transactional initiative and symbolic bus width", initiative => {
  expect(portInputFromRow(row({ name: "service", family: "transactional", initiative, transaction_kind: "custom", custom_kind: "svc_type", bus_width: "DATA_WIDTH" }))).toEqual({
    name: "service", family: "transactional", description: "", initiative,
    kind: "custom", custom_kind: "svc_type", bus_width: "DATA_WIDTH",
  });
});

it("normalizes absent optional transactional fields without inventing a kind", () => {
  expect(portInputFromRow(row({ name: "service", family: "transactional", initiative: "provides", transaction_kind: null }))).toMatchObject({ kind: null, custom_kind: null, bus_width: null });
});

it.each(["in", "out", "inout"])("keeps a structured port direction and omits wire-only fields", direction => {
  const input = portInputFromRow(row({ name: "bundle", family: "structured", direction, range: "must_not_leak", bus_width: "must_not_leak" }));
  expect(input).toEqual({ name: "bundle", family: "structured", description: "", direction });
});

it("does not mutate table cells while creating a draft", () => {
  const saved = row({ name: "immutable_id", family: "wire", direction: "in" });
  const before = structuredClone(saved);
  const draft = portInputFromRow(saved);
  draft.description = "Private change";
  expect(saved).toEqual(before);
  expect(rowText(saved, "missing")).toBe("");
});

it("checks delimiters while allowing conditional expressions, scoped names, and bit selections", async () => {
  const { wireRangeError } = await import("../src/port-input");
  for (const range of ["", "4:1", "-1:-4", "(USE ? WIDTH:4)-1:0", "pkg::WIDTH-1:0", "VALUE[3:0]:0", "USE ? WIDTH:4:0", "0:USE ? WIDTH:4", "[15:0]"]) expect(wireRangeError(range)).toBeNull();
  for (const range of ["15-0", "15", "WIDTH-1", "[]", "([WIDTH)]:0", "(31::0):0", "31::0", "31:", ":0", "31:0:1", "(WIDTH-1:0"]) expect(wireRangeError(range)).toContain("left:right expression pair");
});

it("normalizes optional brackets without changing bound expressions", async () => {
  const { normalizeWireRange } = await import("../src/port-input");
  expect(normalizeWireRange(" [15:0] ")).toBe("15:0");
  expect(normalizeWireRange("VALUE[3:0]:0")).toBe("VALUE[3:0]:0");
  expect(normalizeWireRange(" ")).toBeNull();
});
