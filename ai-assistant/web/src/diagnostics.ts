import type { Diagnostic } from "@spec2gds/circuit-core";

const SEVERITIES = new Set<Diagnostic["severity"]>(["info", "warning", "error"]);

/** Normalize service results, HTTP error envelopes, and older stored reviews. */
export function normalizeReviewDiagnostics(value: unknown): Diagnostic[] {
  const result = collectDiagnostics(value);
  const seen = new Set<string>();
  return result.filter((item) => {
    const key = [item.code, item.message, item.element_key, item.path].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectDiagnostics(value: unknown): Diagnostic[] {
  if (value === null || value === undefined) return [];
  if (Array.isArray(value)) return value.flatMap(collectDiagnostics);
  if (typeof value === "string") {
    const message = value.trim();
    return message
      ? [{ severity: "error", code: "preview_rejected", message }]
      : [];
  }
  if (typeof value !== "object") {
    return [{
      severity: "error",
      code: "preview_rejected",
      message: String(value),
    }];
  }

  const record = value as Record<string, unknown>;
  const nested = ["diagnostics", "detail", "errors"].flatMap((key) =>
    key in record ? collectDiagnostics(record[key]) : []
  );
  const message = typeof record.message === "string" ? record.message.trim() : "";
  const current = message
    ? [{
        severity: diagnosticSeverity(record.severity),
        code: diagnosticField(record.code, "preview_rejected"),
        message,
        ...optionalDiagnosticField("element_key", record.element_key),
        ...optionalDiagnosticField("operation_id", record.operation_id),
        ...optionalDiagnosticField("path", record.path),
      } satisfies Diagnostic]
    : [];
  if (current.length || nested.length) return [...current, ...nested];

  return [{
    severity: "error",
    code: "preview_rejected",
    message: safeJson(value),
  }];
}

function diagnosticSeverity(value: unknown): Diagnostic["severity"] {
  return typeof value === "string" && SEVERITIES.has(value as Diagnostic["severity"])
    ? value as Diagnostic["severity"]
    : "error";
}

function diagnosticField(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function optionalDiagnosticField(
  name: "element_key" | "operation_id" | "path",
  value: unknown,
): Partial<Diagnostic> {
  return typeof value === "string" && value.trim() ? { [name]: value } : {};
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value) ?? "Circuit Designer rejected the preview.";
  } catch {
    return "Circuit Designer rejected the preview without readable diagnostics.";
  }
}
