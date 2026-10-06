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
const proxyHost = ["0.0.0.0", "::"].includes(specService.host) ? "127.0.0.1" : specService.host;
const specServiceOrigin = `${specService.scheme}://${proxyHost}:${specService.port}`;

export default defineConfig({
  base: "/editor-assets/",
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../../../spec2gds/spec/spec_format/editor_dist", import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  worker: {
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name].js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  server: {
    port: 6015,
    allowedHosts: true,
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
