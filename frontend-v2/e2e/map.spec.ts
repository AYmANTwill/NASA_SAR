import { expect, test, type APIRequestContext } from "@playwright/test";
import { LANGS, requireBackend, waitForMap } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

/**
 * No case has a radar layer yet (no NISAR data on this machine). For a preview,
 * the backend's own sample layer (legacy POST /ask?mock=true, image
 * cache/layers/mock_disp.png) is turned into a RasterLayer the way
 * backend/api_v2.py:_layers does, and put on Panama as a map figure. The PNG
 * of that sample was not rendered with the canonical palette, so its colours
 * may not match the legend: this preview checks placement, legend and
 * controls, not colours.
 */
async function sampleLayer(request: APIRequestContext) {
  const mock = await (
    await request.post(`${API}/ask?mock=true`, { data: { question: "sample", lat: 34.6, lon: -5.2, lang: "en" } })
  ).json();
  const lay = mock.layers[0] as { url: string; bounds: [[number, number], [number, number]]; vmin: number; vmax: number; title: string };
  const [[s, w], [n, e]] = lay.bounds;
  const hi = Math.max(Math.abs(lay.vmin), Math.abs(lay.vmax));
  return {
    id: "mock_disp",
    kind: "displacement",
    url: `/api${lay.url}`,
    bounds: [w, s, e, n],
    unit: "cm",
    min: -hi,
    max: hi,
    palette: "diverging_displacement",
    sign_convention: "positive_away_from_satellite",
    period: null,
    source: lay.title,
  };
}

test.describe("map, live backend", () => {
  test.beforeEach(requireBackend);

  test("a case without a radar layer still frames its study area on a real map", async ({ page }) => {
    await page.goto("/fr/cases/panama-2026");
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();
    await expect(page.getByText("Pas encore de carte radar pour ce cas")).toBeVisible();
    await expect(page.getByRole("button", { name: "Zoom avant" })).toBeVisible();
  });

  test("keyboard: the map takes focus and zooms with +", async ({ page }) => {
    await page.goto("/en/cases/panama-2026");
    const canvas = page.locator(".maplibregl-canvas");
    await expect(canvas).toBeVisible();
    await canvas.focus();
    await expect(canvas).toBeFocused();
    await page.keyboard.press("+");
  });

  test("preview with the backend's sample layer: raster placed, legend from the layer", async ({ page, request }) => {
    const layer = await sampleLayer(request);
    const study = await (await request.get(`${API}/api/cases/panama-2026`)).json();
    study.location.bbox = layer.bounds;
    study.figures = [
      { id: "sample", kind: "map", title: { fr: "Aperçu (échantillon du serveur)", en: "Preview (server sample)", ar: "معاينة (عيّنة الخادم)" }, url: layer.url, caption: { template: "preview", params: {}, text: { fr: "Aperçu", en: "Preview", ar: "معاينة" } }, layer },
    ];
    await page.route("**/api/cases/panama-2026", (route) => route.fulfill({ json: study }));
    for (const lang of LANGS) {
      const image = page.waitForResponse((r) => r.url().endsWith("/api/layers/mock_disp.png"));
      await page.goto(`/${lang}/cases/panama-2026`);
      expect((await image).status()).toBe(200);
      const legend = page.locator(".legend");
      await expect(legend).toBeVisible();
      await expect(legend.locator(".legend-ends")).toContainText(String(layer.max));
      await waitForMap(page);
      await page.locator(".case-map-column").screenshot({ path: `e2e/__screenshots__/map-preview-${lang}.png` });
    }
  });
});
