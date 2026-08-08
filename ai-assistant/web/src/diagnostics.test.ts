import { describe, expect, it } from "vitest";

import { normalizeReviewDiagnostics } from "./diagnostics";

describe("review diagnostics", () => {
  it("preserves Circuit Designer diagnostic details", () => {
    expect(normalizeReviewDiagnostics([{
      severity: "error",
      code: "unknown_component",
      message: "Instance worker_1 references unknown component worker.",
      element_key: "worker_1",
    }])).toEqual([{
      severity: "error",
      code: "unknown_component",
      message: "Instance worker_1 references unknown component worker.",
      element_key: "worker_1",
    }]);
  });

  it("unwraps nested HTTP error diagnostics", () => {
    expect(normalizeReviewDiagnostics({
      code: "invalid_operations",
      message: "The operation batch was rejected.",
      diagnostics: [{
        severity: "error",
        code: "unknown_endpoint",
        message: "Net data endpoint producer_0:missing does not exist.",
        path: "/operations/0/net/endpoints/1",
      }],
    })).toEqual([
      {
        severity: "error",
        code: "invalid_operations",
        message: "The operation batch was rejected.",
      },
      {
        severity: "error",
        code: "unknown_endpoint",
        message: "Net data endpoint producer_0:missing does not exist.",
        path: "/operations/0/net/endpoints/1",
      },
    ]);
  });

  it("converts plain rejection text into a visible diagnostic", () => {
    expect(normalizeReviewDiagnostics("Malformed operation batch.")).toEqual([{
      severity: "error",
      code: "preview_rejected",
      message: "Malformed operation batch.",
    }]);
  });
});
