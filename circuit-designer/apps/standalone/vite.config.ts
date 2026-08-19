import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { loadServiceRegistry } from "../../packages/service/src/service-registry";

const services = loadServiceRegistry();
const circuitService = services.circuit_designer.service;
const circuitUi = services.circuit_designer.ui;

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: circuitUi.host,
    port: circuitUi.port,
    allowedHosts: true,
    proxy: {
      "/api": `${circuitService.scheme}://${circuitService.host}:${circuitService.port}`,
    },
  },
  preview: { host: circuitUi.host, port: circuitUi.port, allowedHosts: true },
});
