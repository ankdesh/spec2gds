import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

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
    proxy: {
      "/api": "http://127.0.0.1:4200",
      "/a2a": "http://127.0.0.1:4200",
      "/.well-known": "http://127.0.0.1:4200",
    },
  },
});
