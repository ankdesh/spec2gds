import { defineConfig } from "@playwright/test";

const circuitUiUrl = process.env.CIRCUIT_DESIGNER_E2E_UI_URL ?? "http://127.0.0.1:6012";
const isolated = process.env.SPEC2GDS_TEST_ISOLATED === "1";

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.SPEC2GDS_TEST_OUTPUT_DIR ?? "test-results",
  timeout: 30_000,
  use: {
    baseURL: circuitUiUrl,
    headless: true,
    trace: isolated ? "retain-on-failure" : "off",
    screenshot: isolated ? "only-on-failure" : "off",
  },
  webServer: {
    command: "npm run dev",
    url: circuitUiUrl,
    reuseExistingServer: !isolated,
    timeout: 120_000,
  },
});
