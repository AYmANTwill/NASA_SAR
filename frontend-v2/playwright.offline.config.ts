import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

/** Run npm run build first. This checks the normal production app, separately from the frozen jury demo. */
export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: "**/offline.spec.ts",
  outputDir: "playwright-report/offline-results",
  use: { ...base.use, baseURL: "http://127.0.0.1:4310" },
  webServer: { command: "npm run preview", url: "http://127.0.0.1:4310", reuseExistingServer: true },
});
