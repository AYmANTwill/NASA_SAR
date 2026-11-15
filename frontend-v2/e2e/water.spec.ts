import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen, waitForMap } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const CASE = "bin-el-ouidane-2026";

test.describe("water case, live backend", () => {
  test.beforeEach(requireBackend);

  test("all three images load, stay separate from RasterLayer legends, and retain the four figures", async ({ page, request }) => {
    test.setTimeout(240_000);
    const response = await request.get(`${API}/api/water/raster-index`);
    test.skip(response.status() === 404, "the water image endpoint is optional on older backends");
    expect(response.ok()).toBe(true);
    const index = await response.json() as { layers: { id: string; url: string }[] };
    const study = await (await request.get(`${API}/api/cases/${CASE}`)).json() as { status: string; kind: string; figures: { layer?: unknown }[] };
    expect(study.status).toBe("final");
    expect(study.kind).toBe("method");
    expect(study.figures).toHaveLength(4);
    for (const lang of LANGS) {
      await page.goto(`/${lang}/cases/${CASE}`);
      await expect(page.locator(".layer-choice input")).toHaveCount(index.layers.length);
      await expect(page.locator(".figure-list img")).toHaveCount(study.figures.filter((f) => !f.layer).length);
      for (const [i, image] of index.layers.entries()) {
        const loaded = i === 0 ? page.request.get(image.url) : page.waitForResponse((r) => new URL(r.url()).pathname === image.url);
        await page.locator(".layer-choice input").nth(i).check();
        expect((await loaded).status()).toBe(200);
        await waitForMap(page);
        await expect(page.locator(".legend")).toHaveCount(0);
        await reviewScreen(page, `water-${image.id}-${lang}`);
      }
      const dates = page.locator(".pt-list");
      await dates.focus();
      await dates.press("End");
      await expect(dates.locator("li").last()).toBeInViewport();
    }
  });

  test("an absent optional index leaves the case and its figures usable", async ({ page }) => {
    await page.route("**/api/water/raster-index", (route) => route.fulfill({ status: 404, json: { detail: "Not Found" } }));
    await page.goto(`/en/cases/${CASE}`);
    await expect(page.locator(".figure-list img")).toHaveCount(4);
    await expect(page.locator(".status-final")).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.locator(".layer-choice")).toHaveCount(0);
  });
});
