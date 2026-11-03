import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { createRequire } from "node:module";
import type { ServiceConfig } from "../../../runtime/service-config.mjs";

// Keep the shared Node resolver outside Vite's configuration bundle.
const { resolveConfig, endpointUrl } = createRequire(import.meta.url)("../../../runtime/service-config.cjs") as typeof import("../../../runtime/service-config.mjs");

export function configure(config: ServiceConfig = resolveConfig()) {
  const specServiceOrigin = endpointUrl(config.spec_editor.service, config.public_host, { local: true, origin: true });
  const listener = {
      host: config.spec_editor.dev_ui.host, port: config.spec_editor.dev_ui.port,
      strictPort: true, allowedHosts: true as const,
      proxy: {
        "/api": { target: specServiceOrigin, changeOrigin: false, rewrite: (path: string) => path.replace(/^\/api/, "") },
        "/docs": { target: specServiceOrigin, changeOrigin: false },
      },
  };
  return defineConfig({
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
    server: listener,
    preview: listener,
  });
}
export default () => configure();
