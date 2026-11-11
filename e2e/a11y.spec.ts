import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { waitForMap, watchConsole } from "./helpers";

const ROUTES = ["/", "/investigate", "/investigate/fx-panama-2026-10-09", "/investigate/fx-alwahda-since-june", "/investigate/fx-zone-rif-slope", "/watch", "/library", "/proof"];
const LANGS = ["fr", "ar", "en"] as const;

for (const lang of LANGS) {
  for (const route of ROUTES) {
    test(`axe: ${lang} ${route}`, async ({ page }) => {
      const errors = watchConsole(page);
      await page.goto(`${route}${route.includes("?") ? "&" : "?"}lang=${lang}`);
      await expect(page.locator("main")).toBeVisible();
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await expect(page.locator("html")).toHaveAttribute("dir", lang === "ar" ? "rtl" : "ltr");
      await expect(page.locator("html")).toHaveAttribute("lang", lang);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        // MapLibre draws on a canvas; its DOM controls are checked, the canvas is not text.
        .exclude(".maplibregl-canvas")
        .analyze();
      const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(serious.map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`)).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}

test("keyboard: skip link, navigation, ask, layer controls, language", async ({ page }) => {
  await page.goto("/investigate/fx-panama-2026-10-09");
  await waitForMap(page);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Aller au contenu" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();

  // Every interactive control in the answer and the legend is reachable and shows focus.
  const seen = new Set<string>();
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const style = getComputedStyle(el);
      const visible = style.outlineStyle !== "none" || style.boxShadow !== "none";
      return { name: el.getAttribute("aria-label") ?? el.textContent?.trim().slice(0, 40) ?? el.tagName, visible };
    });
    if (info) {
      seen.add(info.name);
      expect(info.visible, `focus visible on "${info.name}"`).toBe(true);
    }
  }
  expect([...seen].some((n) => n.includes("Veiller sur ce lieu"))).toBe(true);
  expect([...seen].some((n) => n.startsWith("Opacité"))).toBe(true);

  // Language switch without reload.
  const marker = await page.evaluate(() => ((window as unknown as { __m: number }).__m = Math.random()));
  await page.getByRole("button", { name: "العربية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  expect(await page.evaluate(() => (window as unknown as { __m: number }).__m)).toBe(marker);
});
