/** Shared Node-side JSONL writer for the Circuit Designer service. */
import {
  closeSync, existsSync, mkdirSync, openSync, readFileSync, renameSync,
  statSync, unlinkSync, writeFileSync, writeSync,
} from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { defaultConfigPath, resolveConfig, type ServiceConfig } from "../../../../runtime/service-config.mjs";
import { randomUUID, createHash } from "node:crypto";

export type LogLevel = "info" | "debug";
export type LogSeverity = "debug" | "info" | "warning" | "error";

export interface ObservabilityConfig {
  enabled: boolean;
  level: LogLevel;
  file: string;
  maxBytes: number;
  viewerHost: string;
  viewerPort: number;
}

export interface LogEventInput {
  component: string;
  event: string;
  message: string;
  severity?: LogSeverity;
  origin?: "backend" | "browser";
  details?: unknown;
  correlationId?: string;
  sessionId?: string;
  durationMs?: number;
  status?: number | string;
  timestamp?: string;
}

export { defaultConfigPath };

export function loadObservabilityConfig(path = defaultConfigPath(), config?: ServiceConfig): ObservabilityConfig {
  const payload = (config ?? resolveConfig(path)) as unknown as Record<string, unknown>;
  const logging = payload.logging as Record<string, unknown> | undefined;
  if (!logging) throw new Error("Service registry logging settings are required.");
  const enabled = process.env.SPEC2GDS_LOGGING === undefined
    ? logging.enabled
    : parseEnabled(process.env.SPEC2GDS_LOGGING);
  if (typeof enabled !== "boolean") throw new Error("logging.enabled must be a boolean.");
  const level = String(process.env.SPEC2GDS_LOG_LEVEL ?? logging.level ?? "info").toLowerCase();
  if (level !== "info" && level !== "debug") throw new Error("SPEC2GDS_LOG_LEVEL must be info or debug.");
  const configuredFile = String(logging.file ?? "");
  if (!configuredFile) throw new Error("logging.file is required.");
  const maxBytes = Number(logging.max_bytes);
  if (!Number.isInteger(maxBytes) || maxBytes < 1024) throw new Error("logging.max_bytes must be at least 1024.");
  const viewer = logging.viewer as Record<string, unknown> | undefined;
  const viewerHost = String(viewer?.host ?? "");
  if (!viewerHost) throw new Error("logging.viewer.host is required.");
  const viewerPort = Number(viewer?.port);
  if (!Number.isInteger(viewerPort) || viewerPort < 1 || viewerPort > 65535) throw new Error("logging.viewer.port is invalid.");
  return {
    enabled, level, file: isAbsolute(configuredFile) ? configuredFile : resolve(dirname(path), configuredFile),
    maxBytes, viewerHost, viewerPort,
  };
}

function parseEnabled(value: unknown): boolean {
  const normalized = String(value).trim().toLowerCase();
  if (normalized === "on") return true;
  if (normalized === "off") return false;
  throw new Error("SPEC2GDS_LOGGING must be ON or OFF.");
}

export function redact(value: unknown, key = ""): unknown {
  const lowered = key.toLowerCase();
  if (["authorization", "cookie", "password", "secret", "api_key", "apikey", "access_token", "refresh_token"].some((item) => lowered.includes(item))) return "[REDACTED]";
  if (typeof value === "string" && (lowered.includes("base64") || (value.startsWith("data:") && value.includes(";base64,")))) {
    return { omitted: "base64", characters: value.length, sha256: createHash("sha256").update(value).digest("hex") };
  }
  if (value instanceof Uint8Array) return { omitted: "binary", bytes: value.byteLength, sha256: createHash("sha256").update(value).digest("hex") };
  if (Array.isArray(value)) return value.map((item) => redact(item));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([itemKey, item]) => [itemKey, redact(item, itemKey)]));
  return value;
}

export class StructuredLogger {
  private reportedFailure = false;
  constructor(readonly application: string, readonly config: ObservabilityConfig) {}

  event(input: LogEventInput): void {
    if (!this.config.enabled || (input.severity === "debug" && this.config.level !== "debug")) return;
    const record: Record<string, unknown> = {
      schema_version: 1, timestamp: input.timestamp ?? new Date().toISOString(),
      severity: input.severity ?? "info", detail_level: this.config.level,
      application: this.application, origin: input.origin ?? "backend",
      component: input.component, event: input.event, message: input.message,
      event_id: randomUUID().replaceAll("-", ""),
    };
    for (const [key, value] of Object.entries({
      correlation_id: input.correlationId, session_id: input.sessionId,
      duration_ms: input.durationMs, status: input.status,
    })) if (value !== undefined) record[key] = value;
    if (this.config.level === "debug" && input.details !== undefined) record.details = redact(input.details);
    try { writeLine(this.config, `${JSON.stringify(record)}\n`); }
    catch (reason) {
      if (!this.reportedFailure) {
        this.reportedFailure = true;
        console.error(`spec2gds logging disabled after write failure: ${String(reason)}`);
      }
    }
  }
}

function writeLine(config: ObservabilityConfig, line: string): void {
  mkdirSync(dirname(config.file), { recursive: true });
  const lock = `${config.file}.lock`;
  acquireLock(lock);
  try {
    const incoming = Buffer.from(line);
    const size = existsSync(config.file) ? statSync(config.file).size : 0;
    if (size + incoming.byteLength > config.maxBytes) compact(config.file, incoming, config.maxBytes);
    else {
      const descriptor = openSync(config.file, "a");
      try { writeSync(descriptor, incoming); } finally { closeSync(descriptor); }
    }
  } finally { if (existsSync(lock)) unlinkSync(lock); }
}

function acquireLock(path: string): void {
  const deadline = Date.now() + 5000;
  while (true) {
    try {
      const descriptor = openSync(path, "wx", 0o600);
      writeSync(descriptor, `${process.pid} ${Date.now()}\n`); closeSync(descriptor); return;
    } catch (reason) {
      if ((reason as NodeJS.ErrnoException).code !== "EEXIST") throw reason;
      if (existsSync(path) && Date.now() - statSync(path).mtimeMs > 30_000) { unlinkSync(path); continue; }
      if (Date.now() >= deadline) throw new Error(`Timed out waiting for log lock ${path}.`);
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10);
    }
  }
}

function compact(path: string, incoming: Buffer, maxBytes: number): void {
  let existing = existsSync(path) ? readFileSync(path) : Buffer.alloc(0);
  // Discard a crash-truncated tail instead of promoting it to a complete JSONL record.
  if (existing.byteLength > 0 && existing.at(-1) !== 10) {
    const lastNewline = existing.lastIndexOf(10);
    existing = lastNewline >= 0 ? existing.subarray(0, lastNewline + 1) : Buffer.alloc(0);
  }
  const lines = existing.toString("utf8").split(/\r?\n/).filter(Boolean).map((line) => Buffer.from(`${line}\n`));
  lines.push(incoming);
  const kept: Buffer[] = []; let total = 0;
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index];
    if (kept.length > 0 && total + line.byteLength > maxBytes) break;
    kept.push(line); total += line.byteLength;
  }
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, Buffer.concat(kept.reverse())); renameSync(temporary, path);
}
