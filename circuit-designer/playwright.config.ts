import { defineConfig } from "@playwright/test";

import { resolveConfig, endpointUrl } from "../runtime/service-config.mjs";
const configPath = process.env.SPEC2GDS_TEST_SERVICE_CONFIG;
const config = resolveConfig(configPath);
const circuitUiUrl = endpointUrl(config.circuit_designer.ui, config.public_host, { local: true });
const launchOptions = configPath ? ` -- --service-config ${JSON.stringify(configPath)}` : "";

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
    command: `npm run dev${launchOptions}`,
    url: circuitUiUrl,
    reuseExistingServer: !isolated,
    timeout: 120_000,
  },
});
