import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

import { pwaOptions } from "./pwa.config";

// The backend runs in the same container (wt serve, port 8000).
const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA(pwaOptions)],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // Listen on all interfaces in wt_dev. wt_dev publishes the port to 127.0.0.1 on the host only.
    host: true,
    port: 5173,
    strictPort: true,
    proxy: { "/api": BACKEND_URL },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/api/schema.d.ts", "src/test/**", "src/**/*.test.{ts,tsx}"],
      thresholds: { lines: 99, branches: 97 },
    },
  },
});
