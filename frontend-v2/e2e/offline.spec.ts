import { expect, test } from "@playwright/test";
import { requireBackend, waitForMap } from "./backend";

test.beforeEach(requireBackend);
test("production app reloads a visited case, its images and a prepared answer without a network", async ({ page, context, request }) => {
  const index = await (await request.get("/api/water/raster-index")).json() as { layers: unknown[] };
  await page.goto("/en/cases/bin-el-ouidane-2026");
  await waitForMap(page);
  await expect(page.locator(".figure-open")).toHaveCount(4);
  await page.locator(".figure-open").last().scrollIntoViewIfNeeded();
  await expect.poll(() => page.locator(".figure-open img").evaluateAll((images) => images.every((image) => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage).filter((key) => key.includes("/ask/")).length)).toBeGreaterThan(0);
  // First visit: images are warmed after the initial worker takes control, without a forced reload.
  await expect.poll(() => page.evaluate(async () => {
    const cache = await caches.open((await caches.keys()).find((key) => key.startsWith("nisar-v2-shell-"))!);
    const requests = await cache.keys();
    return { figures: requests.filter((request) => request.url.includes("/api/water/figures/")).length,
      rasters: requests.filter((request) => request.url.includes("/api/water/rasters/")).length };
  })).toEqual({ figures: 4, rasters: index.layers.length });
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bin El Ouidane");
  await waitForMap(page);
  await expect(page.locator(".shell-offline")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  for (const layer of await page.locator(".layer-choice input[type=radio]").all()) {
    await layer.check();
    await waitForMap(page);
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  await page.locator(".figure-open").last().scrollIntoViewIfNeeded();
  await expect.poll(() => page.locator(".figure-open img").evaluateAll((images) => images.every((image) => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.goto("/ar/cases/bin-el-ouidane-2026");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator(".finding").first()).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.screenshot({ path: "e2e/__screenshots__/production-offline-ar-1440.png", fullPage: true });
  await page.goto("/en/ask");
  await expect(page.locator(".suggestion").first()).toBeVisible();
  await page.locator(".suggestion").first().click();
  await expect(page.locator(".answer-head")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
