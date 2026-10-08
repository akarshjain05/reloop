import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: the browser calls /api/*, Vite forwards to the FastAPI server (default http://localhost:8000).
// Prod: set VITE_API_BASE_URL to the API Gateway URL at build time (see README).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  build: { chunkSizeWarningLimit: 900 },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], css: false },
});
