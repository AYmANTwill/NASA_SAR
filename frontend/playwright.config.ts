import { defineConfig, devices } from "@playwright/test";

/**
 * Two production builds are tested:
 * - "demo": fixtures mode (dist-demo), the offline demo path, accessibility and screenshots;
 * - "http": real http adapter (dist) with /api answered by Playwright from the fixtures,
 *   which exercises JSON + SSE parsing, contract validation and the persisted offline cache.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [
    { name: "demo", testIgnore: /http\.spec\.ts/, use: { baseURL: "http://127.0.0.1:4173" } },
    { name: "http", testMatch: /http\.spec\.ts/, use: { baseURL: "http://127.0.0.1:4174" } },
  ],
  webServer: [
    { command: "npm run build:demo && npm run preview:demo", url: "http://127.0.0.1:4173", reuseExistingServer: true, timeout: 240_000 },
    { command: "npm run build && npm run preview", url: "http://127.0.0.1:4174", reuseExistingServer: true, timeout: 240_000 },
  ],
});
