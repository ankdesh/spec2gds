import { defineConfig } from "@playwright/test";

const circuitUiUrl = process.env.CIRCUIT_DESIGNER_E2E_UI_URL ?? "http://127.0.0.1:6012";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: circuitUiUrl,
    headless: true,
  },
  webServer: {
    command: "npm run dev",
    url: circuitUiUrl,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
