import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const LANGS = [
  { lang: "fr", dir: "ltr", cases: "Études de cas" },
  { lang: "en", dir: "ltr", cases: "Case studies" },
  { lang: "ar", dir: "rtl", cases: "دراسات الحالة" },
] as const;

for (const { lang, dir, cases } of LANGS) {
  test.describe(`shell in ${lang}`, () => {
    test("language, direction and title", async ({ page }) => {
      await page.goto(`/${lang}/`);
      await expect(page.locator("html")).toHaveAttribute("lang", lang);
      await expect(page.locator("html")).toHaveAttribute("dir", dir);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(cases);
      await expect(page).toHaveTitle(new RegExp(cases));
    });

    test("no accessibility violations", async ({ page }) => {
      await page.goto(`/${lang}/`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
    });

    test("screenshots at three widths, no horizontal scroll", async ({ page }) => {
      for (const width of [1440, 1024, 390]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(`/${lang}/`);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `e2e/__screenshots__/shell-${lang}-${width}.png`, fullPage: true });
      }
    });
  });
}

test("keyboard: skip link first, then the language switch keeps the page", async ({ page }) => {
  await page.goto("/fr/library");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Aller au contenu" })).toBeFocused();
  await page.getByRole("link", { name: "العربية" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ar\/library$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});
