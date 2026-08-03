import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4190",
    headless: true,
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:4190",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
