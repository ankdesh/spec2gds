import {
  exportCircuitJson,
  validateCircuitDocument,
  type CircuitDocument,
  type Diagnostic,
} from "@spec2gds/circuit-core";

export type CircuitFileParseResult =
  | { valid: true; document: CircuitDocument; diagnostics: Diagnostic[] }
  | { valid: false; diagnostics: Diagnostic[] };

/** Parse and validate a portable CircuitDocument without changing a live session. */
export function parseCircuitDocumentJson(text: string): CircuitFileParseResult {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (reason) {
    return {
      valid: false,
      diagnostics: [{
        severity: "error",
        code: "invalid_json",
        message: reason instanceof SyntaxError ? reason.message : "The selected file is not valid JSON.",
      }],
    };
  }

  const checked = validateCircuitDocument(value);
  if (!checked.valid) return { valid: false, diagnostics: checked.diagnostics };
  return {
    valid: true,
    document: value as CircuitDocument,
    diagnostics: checked.diagnostics,
  };
}

export function circuitDocumentFilename(document: CircuitDocument): string {
  return `${document.document_id}.circuit.json`;
}

export function circuitDocumentFileContents(document: CircuitDocument): string {
  return exportCircuitJson(document);
}

export function summarizeFileDiagnostics(diagnostics: Diagnostic[], limit = 3): string {
  const messages = diagnostics.slice(0, limit).map((item) => item.message);
  const remainder = diagnostics.length - messages.length;
  return `${messages.join(" · ")}${remainder > 0 ? ` · ${remainder} more` : ""}`;
}
