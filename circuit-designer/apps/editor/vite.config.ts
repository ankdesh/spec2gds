import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/docs": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
