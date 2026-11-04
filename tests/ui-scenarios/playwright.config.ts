import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
import { mkdirSync, mkdtempSync } from "node:fs";

process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve("../../circuit-designer/.playwright-browsers");
mkdirSync(resolve("../../temp"), { recursive: true });
const output = process.env.SPEC2GDS_TEST_OUTPUT_DIR ??= mkdtempSync(resolve("../../temp/TEMP_spec2gds-e2e-"));
export default defineConfig({
  testDir: "./e2e",
  outputDir: `${output}/artifacts`,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: `${output}/results.json` }]],
  use: {
    browserName: "chromium",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { args: ["--no-sandbox"] },
  },
  projects: ["spec", "circuit", "assistant", "verification"].map(name => ({
    name, testMatch: `${name}.spec.ts`,
  })),
});
