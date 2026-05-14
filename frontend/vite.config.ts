import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Docs: https://vitejs.dev/config/
// Docs: https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/nucleus/workbench/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8765",
    },
  },
});
