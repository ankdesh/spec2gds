import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { readFileSync } from "node:fs";

const serviceConfig = JSON.parse(readFileSync(
  process.env.SPEC2GDS_SERVICE_CONFIG
    ?? fileURLToPath(new URL("../../config/services.json", import.meta.url)),
  "utf8",
));
const assistantService = serviceConfig.ai_assistant.service;
const proxyHost = ["0.0.0.0", "::"].includes(assistantService.host)
  ? "127.0.0.1"
  : assistantService.host;
const assistantOrigin = `${assistantService.scheme}://${proxyHost}:${assistantService.port}`;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: "@spec2gds/document-a2ui-react/styles.css",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/document-a2ui-react/src/styles.css", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/document-a2ui-react",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/document-a2ui-react/src/index.tsx", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/document-core",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/document-core/src/index.ts", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/circuit-react/styles.css",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/react/src/styles.css", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/circuit-react",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/react/src/index.tsx", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/circuit-layout",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/layout/src/index.ts", import.meta.url),
        ),
      },
      {
        find: "@spec2gds/circuit-core",
        replacement: fileURLToPath(
          new URL("../../circuit-designer/packages/core/src/index.ts", import.meta.url),
        ),
      },
    ],
  },
  server: {
    allowedHosts: true,
    proxy: {
      "/api": assistantOrigin,
      "/a2a": assistantOrigin,
      "/.well-known": assistantOrigin,
    },
  },
});
