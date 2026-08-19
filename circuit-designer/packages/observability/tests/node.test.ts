import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { StructuredLogger, loadObservabilityConfig, redact, type ObservabilityConfig } from "../src/node";

function config(file: string, overrides: Partial<ObservabilityConfig> = {}): ObservabilityConfig {
  return {
    enabled: true, level: "debug", file, maxBytes: 1024,
    viewerHost: "127.0.0.1", viewerPort: 6014, ...overrides,
  };
}

describe("StructuredLogger", () => {
  it("writes redacted debug details and keeps newest records in one file", () => {
    const file = join(mkdtempSync(join(tmpdir(), "spec2gds-log-")), "system.jsonl");
    const logger = new StructuredLogger("circuit-designer", config(file));
    for (let index = 0; index < 20; index += 1) {
      logger.event({
        component: "test", event: "write", message: `event-${index}`,
        details: { authorization: "secret", payload: "x".repeat(100) },
      });
    }
    const records = readFileSync(file, "utf8").trim().split("\n").map((line) => JSON.parse(line));
    expect(records.at(-1).message).toBe("event-19");
    expect(records.at(-1).details.authorization).toBe("[REDACTED]");
  });

  it("does not write debug events in info mode", () => {
    const file = join(mkdtempSync(join(tmpdir(), "spec2gds-log-")), "system.jsonl");
    new StructuredLogger("circuit-designer", config(file, { level: "info" })).event({
      component: "test", event: "hidden", message: "Hidden", severity: "debug",
    });
    expect(() => readFileSync(file)).toThrow();
  });
});

describe("loadObservabilityConfig", () => {
  it("allows only enabled and level environment overrides", () => {
    const directory = mkdtempSync(join(tmpdir(), "spec2gds-config-"));
    const path = join(directory, "services.json");
    writeFileSync(path, JSON.stringify({
      schema_version: 2,
      logging: {
        enabled: false, level: "info", file: "configured.jsonl", max_bytes: 4096,
        viewer: { host: "127.0.0.1", port: 6014 },
      },
    }));
    const before = { logging: process.env.SPEC2GDS_LOGGING, level: process.env.SPEC2GDS_LOG_LEVEL, file: process.env.SPEC2GDS_LOG_FILE };
    process.env.SPEC2GDS_LOGGING = "ON"; process.env.SPEC2GDS_LOG_LEVEL = "debug";
    process.env.SPEC2GDS_LOG_FILE = join(directory, "ignored.jsonl");
    try {
      expect(loadObservabilityConfig(path)).toMatchObject({
        enabled: true, level: "debug", file: join(directory, "configured.jsonl"),
      });
    } finally {
      if (before.logging === undefined) delete process.env.SPEC2GDS_LOGGING; else process.env.SPEC2GDS_LOGGING = before.logging;
      if (before.level === undefined) delete process.env.SPEC2GDS_LOG_LEVEL; else process.env.SPEC2GDS_LOG_LEVEL = before.level;
      if (before.file === undefined) delete process.env.SPEC2GDS_LOG_FILE; else process.env.SPEC2GDS_LOG_FILE = before.file;
    }
  });
});

describe("redact", () => {
  it("masks nested secrets and summarizes base64 strings", () => {
    expect(redact({ api_key: "secret", png_base64: "abc" })).toMatchObject({
      api_key: "[REDACTED]", png_base64: { omitted: "base64", characters: 3 },
    });
  });
});
