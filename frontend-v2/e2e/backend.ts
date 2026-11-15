import { expect, test, type Page } from "@playwright/test";

const BACKEND = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

/** Live tests need the real backend; without it they are skipped with the reason, never faked. */
export async function requireBackend(): Promise<void> {
  let up = false;
  try {
    up = (await fetch(`${BACKEND}/api/health`, { signal: AbortSignal.timeout(3000) })).ok;
  } catch {
    up = false;
  }
  test.skip(!up, `backend not running on ${BACKEND} (start it: see frontend-v2/README.md)`);
}

export const LANGS = ["fr", "en", "ar"] as const;

/** Waits until MapLibre has drawn everything (RadarMap sets data-idle on its "idle" event). */
export async function waitForMap(page: Page): Promise<void> {
  await expect(page.locator('.radar-map-canvas[data-idle="true"]').first()).toBeVisible({ timeout: 20_000 });
  // Every map on the page, not just the first one.
  await expect(page.locator('.radar-map-canvas:not([data-idle="true"])')).toHaveCount(0, { timeout: 20_000 });
}

/**
 * A full-page screenshot that is safe with a live map: Playwright's fullPage
 * capture resizes the viewport mid-capture, which makes MapLibre redraw. Here
 * the viewport is grown to the page height first, the map is let to settle,
 * then a plain screenshot is taken.
 */
export async function pageScreenshot(page: Page, path: string): Promise<void> {
  const viewport = page.viewportSize() ?? { width: 1440, height: 900 };
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: viewport.width, height });
  if (await page.locator(".radar-map-canvas").count()) {
    await page.waitForTimeout(100);
    await waitForMap(page);
  }
  await page.screenshot({ path });
  await page.setViewportSize(viewport);
}
