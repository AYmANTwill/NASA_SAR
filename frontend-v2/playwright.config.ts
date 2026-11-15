import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against the Vite dev server, which proxies /api to the
 * real backend on 127.0.0.1:8000 (start it first: see README.md).
 * Uses the installed Chrome (channel "chrome"): no browser download.
 */
export default defineConfig({
  testDir: "e2e",
  testIgnore: ["**/offline.spec.ts"],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL: "http://127.0.0.1:5310",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: { command: "npm run dev", url: "http://127.0.0.1:5310", reuseExistingServer: true, timeout: 120_000 },
});
