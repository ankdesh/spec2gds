import { describe, expect, it } from "vitest";
import { formatDocumentSummary } from "../src/index";

describe("Document summary singular/plural inflection (UI-SPEC-012)", () => {
  it("formats singular component count correctly", () => {
    expect(formatDocumentSummary("1 components · 0 designs")).toBe("1 component · 0 designs");
  });

  it("formats singular design count correctly", () => {
    expect(formatDocumentSummary("0 components · 1 designs")).toBe("0 components · 1 design");
  });

  it("formats both singular counts correctly", () => {
    expect(formatDocumentSummary("1 components · 1 designs")).toBe("1 component · 1 design");
  });

  it("preserves plural counts when greater than 1 or zero", () => {
    expect(formatDocumentSummary("3 components · 2 designs")).toBe("3 components · 2 designs");
    expect(formatDocumentSummary("0 components · 0 designs")).toBe("0 components · 0 designs");
  });

  it("handles empty or custom summary strings gracefully", () => {
    expect(formatDocumentSummary("")).toBe("");
    expect(formatDocumentSummary("Custom system architecture summary")).toBe("Custom system architecture summary");
  });
});
