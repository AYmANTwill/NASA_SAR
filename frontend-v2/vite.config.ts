import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

/** The backend runs on 127.0.0.1:8000; VITE_API_PROXY overrides it. */
const api = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  // "demo" and "rehearsal" builds replay demo-data/snapshot.json and serve its images as static files.
  const offline = mode === "demo" || mode === "rehearsal";
  return {
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    plugins: [react()],
    publicDir: offline ? "demo-data/public" : "public",
    // Separate folders: a rehearsal build (drafts kept) can never replace the jury build.
    build: offline ? { outDir: mode === "demo" ? "dist-demo" : "dist-rehearsal", emptyOutDir: true } : undefined,
    server: { host: "127.0.0.1", port: 5310, strictPort: true, proxy: { "/api": { target: api, changeOrigin: true } } },
    preview: offline ? undefined : { proxy: { "/api": { target: api, changeOrigin: true } } },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
      setupFiles: ["src/test/setup.tsx"],
    },
  };
});
