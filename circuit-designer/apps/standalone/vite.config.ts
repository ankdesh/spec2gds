import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const circuitServicePort = Number(process.env.CIRCUIT_DESIGNER_PORT ?? 6011);
const circuitUiPort = Number(process.env.CIRCUIT_DESIGNER_UI_PORT ?? 6012);
const circuitUiHost = process.env.CIRCUIT_DESIGNER_UI_HOST ?? "0.0.0.0";
const circuitServiceOrigin = process.env.CIRCUIT_DESIGNER_SERVICE_ORIGIN ?? `http://127.0.0.1:${circuitServicePort}`;

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: circuitUiHost,
    port: circuitUiPort,
    allowedHosts: true,
    proxy: {
      "/api": circuitServiceOrigin,
    },
  },
  preview: {
    host: circuitUiHost,
    port: circuitUiPort,
    allowedHosts: true,
    proxy: {
      "/api": circuitServiceOrigin,
    },
  },
});
