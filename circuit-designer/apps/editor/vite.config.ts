import { fileURLToPath, URL } from "node:url";
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const serviceConfig = JSON.parse(readFileSync(
  process.env.SPEC2GDS_SERVICE_CONFIG
    ?? fileURLToPath(new URL("../../../config/services.json", import.meta.url)),
  "utf8",
));
const specService = serviceConfig.spec_editor.service;
const specServiceOrigin = `${specService.scheme}://${specService.host}:${specService.port}`;

export default defineConfig({
  base: "/editor-assets/",
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../../../spec2gds/agent_spec/spec_format/editor_dist", import.meta.url)),
    emptyOutDir: true,
  },
  server: {
    port: 4190,
    proxy: {
      "/api": {
        target: specServiceOrigin,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/docs": {
        target: specServiceOrigin,
        changeOrigin: false,
      },
    },
  },
});
