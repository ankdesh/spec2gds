import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { createRequire } from "node:module";
import type { ServiceConfig } from "../../../runtime/service-config.mjs";

// Keep the shared Node resolver outside Vite's configuration bundle.
const { resolveConfig, endpointUrl } = createRequire(import.meta.url)("../../../runtime/service-config.cjs") as typeof import("../../../runtime/service-config.mjs");

export function configure(config: ServiceConfig = resolveConfig()) {
  const ui = config.circuit_designer.ui;
  const listener = {
    host: ui.host, port: ui.port, strictPort: true, allowedHosts: true as const,
    proxy: { "/api": endpointUrl(config.circuit_designer.service, config.public_host, { local: true, origin: true }) },
  };
  return defineConfig({ base: "./", plugins: [react()], server: listener, preview: listener });
}
export default () => configure();
