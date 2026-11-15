import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { LANGS, pageScreenshot, requireBackend } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

interface LibraryEvent {
  id: string;
  answer_id: string | null;
  location: { name: string | null; name_i18n?: Partial<Record<(typeof LANGS)[number], string>> };
}
interface Watch {
  id: string;
  answer_id: string | null;
}

async function axe(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id}: ${v.help}`);
}

test.describe("library, live backend", () => {
  test.beforeEach(requireBackend);

  for (const lang of LANGS) {
    test(`${lang}: every library event, linked to its answer`, async ({ page, request }) => {
      const events = (await (await request.get(`${API}/api/library`)).json()) as LibraryEvent[];
      await page.goto(`/${lang}/library`);
      for (const e of events) {
        const name = e.location.name_i18n?.[lang] ?? e.location.name ?? e.id;
        const title = page.getByRole("heading", { name });
        await expect(title).toBeVisible();
        if (e.answer_id) await expect(title.getByRole("link")).toHaveAttribute("href", `/${lang}/answers/${e.answer_id}`);
      }
      expect(await axe(page)).toEqual([]);
      await pageScreenshot(page, `e2e/__screenshots__/library-${lang}-1440.png`);
    });
  }
});

test.describe("watches, live backend", () => {
  test.beforeEach(requireBackend);

  test("watch an answer, see it listed, stop watching it", async ({ page, request }) => {
    const events = (await (await request.get(`${API}/api/library`)).json()) as LibraryEvent[];
    const answerId = events.find((e) => e.answer_id)!.answer_id!;
    const before = ((await (await request.get(`${API}/api/watches`)).json()) as Watch[]).some((w) => w.answer_id === answerId);

    await page.goto(`/en/answers/${answerId}`);
    await page.getByRole("button", { name: "Watch this place" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Watch active" })).toBeVisible();
    await page.getByRole("link", { name: "See the watches" }).click();
    await expect(page).toHaveURL(/\/en\/watches$/);
    const card = page.locator(".watch-card").filter({ has: page.locator(`a[href="/en/answers/${answerId}"]`) });
    await expect(card).toBeVisible();
    expect(await axe(page)).toEqual([]);

    // The demo simulation calls the backend's demo route; its response body has no schema and is never shown.
    let simulated = "";
    await page.route("**/api/watches/*/simulate*", (route) => {
      simulated = route.request().url();
      return route.fulfill({ json: {} });
    });
    await card.getByText("Demonstration: simulate an alert").click();
    await card.getByRole("button", { name: "Simulate" }).click();
    await expect.poll(() => simulated).toMatch(/level=orange$/);

    await pageScreenshot(page, "e2e/__screenshots__/watches-en-1440.png");
    if (!before) {
      await card.getByRole("button", { name: "Stop watching" }).click();
      await expect(card).toHaveCount(0);
    }
  });

  for (const lang of LANGS) {
    test(`${lang}: watches page renders and passes axe`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 900 });
      await page.goto(`/${lang}/watches`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.locator(".loading")).toHaveCount(0);
      expect(await axe(page)).toEqual([]);
      await pageScreenshot(page, `e2e/__screenshots__/watches-${lang}-390.png`);
    });
  }
});
