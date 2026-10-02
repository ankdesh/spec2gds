/** Presentation metadata never replaces a binding's exact owner identity. */
import { isRecord } from "./types.js";

export function readableName(value: string, fallback = "Specification"): string {
  return value && !/[0-9a-f]{24,}/i.test(value) ? value.replace(/[_-]+/g, " ").trim() || fallback : fallback;
}

export function filenameStem(value: string): string {
  let stem = value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80).replace(/-+$/g, "").toLowerCase() || "document";
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(stem)) stem = `document-${stem}`;
  return stem;
}

export function sourceName(context: Record<string, unknown>, fallback = "Specification"): string {
  const document = isRecord(context.document) ? context.document : {};
  const value = context.target_name || context.name || document.label || context.title;
  return typeof value === "string" && value.trim() ? value.trim() : readableName(fallback);
}
