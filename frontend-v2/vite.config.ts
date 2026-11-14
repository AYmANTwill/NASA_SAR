import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

/** The backend runs on 127.0.0.1:8000; VITE_API_PROXY overrides it. */
const api = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5310, strictPort: true, proxy: { "/api": { target: api, changeOrigin: true } } },
  preview: { proxy: { "/api": { target: api, changeOrigin: true } } },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.tsx"],
  },
});
