import { describe, expect, test } from "vitest";
import { simpleDocumentFixture } from "@spec2gds/circuit-core";
import {
  circuitDocumentFileContents,
  circuitDocumentFilename,
  parseCircuitDocumentJson,
  summarizeFileDiagnostics,
} from "./circuit-files";

describe("portable circuit files", () => {
  test("round-trips a canonical CircuitDocument", () => {
    const document = simpleDocumentFixture();
    const parsed = parseCircuitDocumentJson(circuitDocumentFileContents(document));

    expect(parsed.valid).toBe(true);
    expect(parsed.valid && parsed.document).toEqual(document);
    expect(circuitDocumentFilename(document)).toBe("fixture_simple.circuit.json");
  });

  test("reports malformed JSON without throwing", () => {
    const parsed = parseCircuitDocumentJson("{");

    expect(parsed.valid).toBe(false);
    expect(parsed.diagnostics[0]).toMatchObject({
      severity: "error",
      code: "invalid_json",
    });
  });

  test("rejects schema-invalid and semantically broken documents", () => {
    const schemaInvalid = parseCircuitDocumentJson(JSON.stringify({ protocol_version: "circuit-designer.v1" }));
    expect(schemaInvalid.valid).toBe(false);
    expect(schemaInvalid.diagnostics.some((item) => item.code === "schema_validation")).toBe(true);

    const broken = simpleDocumentFixture();
    broken.design.instances[0].component_id = "missing_component";
    const semanticInvalid = parseCircuitDocumentJson(JSON.stringify(broken));
    expect(semanticInvalid.valid).toBe(false);
    expect(semanticInvalid.diagnostics.some((item) => item.severity === "error")).toBe(true);
  });

  test("keeps diagnostic messages concise", () => {
    const diagnostics = Array.from({ length: 5 }, (_, index) => ({
      severity: "error" as const,
      code: `error_${index}`,
      message: `Failure ${index}`,
    }));

    expect(summarizeFileDiagnostics(diagnostics)).toBe("Failure 0 · Failure 1 · Failure 2 · 2 more");
  });
});
