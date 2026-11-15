import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen } from "./backend";

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
      await reviewScreen(page, `cases-${lang}`, [1440, 1024, 390]);
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
