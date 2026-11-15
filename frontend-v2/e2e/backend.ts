import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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
  await expect.poll(() => page.evaluate(() => [...document.images].every((img) => img.complete && img.naturalWidth > 0)), {
    message: `all figures loaded for ${path}`,
  }).toBe(true);
  await page.screenshot({ path });
  await page.setViewportSize(viewport);
}

/** The same live layout, image and accessibility checks on desktop and at the requested phone width. */
export async function reviewScreen(page: Page, name: string, widths = [1440, 390]): Promise<void> {
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => document.fonts.ready);
    if (await page.locator(".radar-map-canvas").count()) await waitForMap(page);
    await expect(page.getByRole("alert")).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${name}: horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
    for (const card of await page.locator(".case-card").all()) {
      const clips = await card.evaluate((element) => {
        const frame = element.getBoundingClientRect();
        return [...element.querySelectorAll(".case-card-body, .case-card-status")].some((child) => {
          const rect = child.getBoundingClientRect();
          return rect.left < frame.left || rect.right > frame.right || rect.bottom > frame.bottom;
        });
      });
      expect(clips, `${name}: case title or status clipped at ${width}px`).toBe(false);
    }
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    expect(results.violations.map((v) => `${name}/${width} ${v.id}: ${v.help} (${v.nodes.map((node) => node.target.join(" ")).join(", ")})`)).toEqual([]);
    await pageScreenshot(page, `e2e/__screenshots__/${name}-${width}.png`);
  }
}
