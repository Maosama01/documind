/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app always calls the API under /api, in development and in Docker:
// Vite's dev server forwards /api to the API on :8000 here, and nginx does
// the same in the image (nginx.conf). The browser only ever talks to one
// origin, so the API needs no CORS for the frontend.
// 127.0.0.1, not localhost: Node may resolve localhost to ::1 while uvicorn
// listens on 127.0.0.1 only.
const API_TARGET = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
