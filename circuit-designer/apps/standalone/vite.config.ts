import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { loadServiceRegistry } from "../../packages/service/src/service-registry";

const services = loadServiceRegistry();
const circuitService = services.circuit_designer.service;
const circuitUi = services.circuit_designer.ui;
const circuitServicePort = Number(process.env.CIRCUIT_DESIGNER_PORT ?? circuitService.port);
const circuitUiPort = Number(process.env.CIRCUIT_DESIGNER_UI_PORT ?? circuitUi.port);

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: circuitUi.host,
    port: circuitUiPort,
    allowedHosts: true,
    proxy: {
      "/api": `${circuitService.scheme}://${circuitService.host}:${circuitServicePort}`,
    },
  },
  preview: { host: circuitUi.host, port: circuitUiPort, allowedHosts: true },
});
