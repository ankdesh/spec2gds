/** Data-only service interface checks. Metadata cannot change authority. */
import { createHash } from "node:crypto";
export interface ApiAction {
  readonly method: string; readonly path: string;
  readonly parameters: { readonly path: readonly string[]; readonly query: readonly string[]; readonly body: readonly string[] };
  readonly response_kind: string;
}
export function canonical(value: unknown): string {
  return JSON.stringify(value, (_key, item) => item && typeof item === "object" && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : item);
}
export function metadataDigest(value: unknown): string {
  return `sha256:${createHash("sha256").update(canonical(value)).digest("hex")}`;
}
export class ServiceAdapter {
  constructor(readonly kind: "spec" | "circuit", readonly actions: Readonly<Record<string, ApiAction>>) {}
  match(method: string, path: string): string | undefined {
    return Object.entries(this.actions).find(([, action]) => action.method === method
      && new RegExp("^" + action.path.replace(/\{\w+\}/g, "[^/]+") + "$").test(path))?.[0];
  }
  validate(value: Record<string, unknown>): void {
    const { digest, ...content } = value;
    if (value.format_version !== 1 || value.service_kind !== this.kind || value.interface_version !== "1.0.0"
      || value.operation_schema_action !== "operation_schema" || value.capabilities_action !== "capabilities"
      || digest !== metadataDigest(content) || canonical(value.actions) !== canonical(this.actions)) {
      throw new Error(`Incompatible ${this.kind} service integration metadata. Update the selected service; no request was submitted.`);
    }
  }
  requestUrl(base: string, action: string, pathValues: Record<string, string> = {}): string {
    const declaration = this.actions[action];
    if (!declaration) throw new Error("Unknown service action.");
    const path = declaration.path.replace(/\{(\w+)\}/g, (_match, key: string) => {
      if (!pathValues[key] || [".", ".."].includes(pathValues[key]!)) throw new Error("Invalid service action path parameter.");
      return encodeURIComponent(pathValues[key]!);
    });
    return base + path;
  }
}
