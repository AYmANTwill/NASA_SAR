import { defineConfig, devices } from "@playwright/test";

/**
 * The offline demo: the rehearsal build (drafts kept, labelled) of the last
 * snapshot, served with no backend. Run `npm run snapshot` first (backend up),
 * then `npm run e2e:demo`. The tests also block every request that does not go
 * to the demo server itself, so nothing can come from the network.
 */
export default defineConfig({
  testDir: "e2e-demo",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    channel: "chrome",
    baseURL: "http://127.0.0.1:4311",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: { command: "npm run build:rehearsal && npm run preview:demo", url: "http://127.0.0.1:4311", reuseExistingServer: false, timeout: 240_000 },
});
