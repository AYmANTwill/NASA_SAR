import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { LANGS, requireBackend } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

interface Summary {
  id: string;
  status: "draft" | "final";
  title: Record<(typeof LANGS)[number], string>;
}

test.describe("case list, live backend", () => {
  test.beforeEach(requireBackend);

  for (const lang of LANGS) {
    test(`${lang}: every case of the API, drafts marked`, async ({ page, request }) => {
      const summaries = (await (await request.get(`${API}/api/cases`)).json()) as Summary[];
      await page.goto(`/${lang}/`);
      for (const s of summaries) await expect(page.getByRole("link", { name: s.title[lang] })).toBeVisible();
      await expect(page.locator(".status-draft")).toHaveCount(summaries.filter((s) => s.status === "draft").length);
      // Locator maps are drawn (land loaded offline from the bundle).
      await expect(page.locator(".locator-land").first()).toHaveAttribute("d", /M/);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
      for (const width of [1440, 1024, 390]) {
        await page.setViewportSize({ width, height: 900 });
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `e2e/__screenshots__/cases-${lang}-${width}.png`, fullPage: true });
      }
    });
  }

  test("keyboard: a case opens from the list", async ({ page, request }) => {
    const [first] = (await (await request.get(`${API}/api/cases`)).json()) as Summary[];
    await page.goto("/en/");
    const link = page.getByRole("link", { name: first!.title.en });
    await link.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/en/cases/${first!.id}$`));
  });
});
