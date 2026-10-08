import { defineConfig } from "@playwright/test";

const editorUrl = process.env.SPEC_EDITOR_E2E_UI_URL ?? "http://127.0.0.1:6015";
const isolated = process.env.SPEC2GDS_TEST_ISOLATED === "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  outputDir: process.env.SPEC2GDS_TEST_OUTPUT_DIR ?? "test-results",
  timeout: 30_000,
  use: {
    baseURL: editorUrl,
    headless: true,
    trace: isolated ? "retain-on-failure" : "off",
    screenshot: isolated ? "only-on-failure" : "off",
  },
  webServer: {
    command: isolated ? `npm run dev -- --port ${new URL(editorUrl).port} --strictPort` : "npm run dev",
    url: editorUrl,
    reuseExistingServer: !isolated,
    timeout: 120_000,
  },
});
