/**
 * Reference screenshots for docs/screenshots (FR, AR, EN × 375, 768, 1280, 1920).
 * Opt-in because it is slow:  SCREENSHOTS=1 npx playwright test e2e/screens.spec.ts --project=demo
 */
import { expect, test } from "@playwright/test";

const ROUTES: [string, string][] = [
  ["cases", "/"],
  ["case-panama", "/cases/panama-2026"],
  ["case-haouz", "/cases/haouz-flood-2026"],
  ["discover", "/discover"],
  ["investigate-panama", "/investigate/fx-panama-2026-10-09"],
  ["answer-alwahda", "/investigate/fx-alwahda-since-june"],
  ["answer-zone1", "/investigate/fx-zone-rif-slope"],
  ["answer-alwahda-real", "/investigate/event-al-wahda-surroundings"],
  ["answer-haouz-real", "/investigate/event-haouz-flood-2026-10-10"],
  ["watch", "/watch"],
  ["library", "/library"],
  ["proof", "/proof"],
];
const WIDTHS = [375, 768, 1280, 1920];
const LANGS = ["fr", "ar", "en"];

test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to regenerate docs/screenshots");
// Reference images show the end state of every animation (deterministic).
test.use({ reducedMotion: "reduce" });

for (const width of WIDTHS) {
  for (const lang of LANGS) {
    test(`screens ${lang} ${width}`, async ({ page }) => {
      test.setTimeout(300_000);
      await page.setViewportSize({ width, height: width < 500 ? 820 : width < 1000 ? 1024 : width < 1600 ? 900 : 1080 });
      for (const [name, route] of ROUTES) {
        await page.goto(`${route}?lang=${lang}`);
        await expect(page.locator("main")).toBeVisible();
        await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
        await page.waitForTimeout(900); // map fit animation
        // No horizontal overflow at any width.
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `${name} overflows horizontally by ${overflow}px`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `docs/screenshots/${lang}-${width}-${name}.png`, fullPage: width <= 768 || !name.startsWith("investigate") && !name.startsWith("answer") });
      }
    });
  }
}
