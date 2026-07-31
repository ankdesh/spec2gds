import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    port: 4180,
    proxy: {
      "/api": "http://127.0.0.1:4100",
    },
  },
  preview: { port: 4180 },
});
