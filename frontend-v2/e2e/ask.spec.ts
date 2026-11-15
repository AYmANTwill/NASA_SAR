import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen, waitForMap } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const LIMITS = { fr: "Ce que le radar ne peut pas dire ici", en: "What the radar cannot tell here", ar: "ما لا يستطيع الرادار قوله هنا" };
const NOT_AVAILABLE = { fr: "Texte non disponible", en: "Text not available", ar: "النص غير متوفّر" };

interface Demo {
  entries: { answer_id: string; questions: { text: string; lang: string }[] }[];
}

test.describe("investigator, live backend", () => {
  test.beforeEach(requireBackend);

  for (const lang of LANGS) {
    test(`${lang}: a demo question streams its steps, then an answer with its limits`, async ({ page, request }) => {
      const demo = (await (await request.get(`${API}/api/demo`)).json()) as Demo;
      const question = demo.entries[0]!.questions.find((q) => q.lang === lang)!.text;
      await page.goto(`/${lang}/ask`);
      await expect(page.getByRole("button", { name: question })).toBeVisible();
      await reviewScreen(page, `ask-form-${lang}`);
      await page.getByRole("button", { name: question }).click();
      const limits = page.getByRole("region", { name: LIMITS[lang] });
      await expect(limits).toBeVisible({ timeout: 60_000 });
      await expect(page.locator(".steps .step").first()).toBeVisible();
      // Every interface template the backend used has a text in this language.
      await expect(page.getByText(NOT_AVAILABLE[lang])).toHaveCount(0);
      await reviewScreen(page, `ask-${lang}`);
    });
  }

  test("a stored answer has its own address", async ({ page, request }) => {
    const demo = (await (await request.get(`${API}/api/demo`)).json()) as Demo;
    const id = demo.entries[0]!.answer_id;
    await page.goto(`/fr/answers/${id}`);
    await expect(page.getByRole("region", { name: LIMITS.fr })).toBeVisible();
    await expect(page.getByRole("link", { name: id })).toBeVisible();
  });

  test("every linked answer in every language on desktop and phone", async ({ page, request }) => {
    test.setTimeout(600_000);
    const demo = (await (await request.get(`${API}/api/demo`)).json()) as Demo;
    const library = await (await request.get(`${API}/api/library`)).json() as { answer_id: string | null }[];
    const cases = await (await request.get(`${API}/api/cases`)).json() as { id: string }[];
    const ids = new Set(demo.entries.map((e) => e.answer_id));
    for (const event of library) if (event.answer_id) ids.add(event.answer_id);
    for (const summary of cases) {
      const study = await (await request.get(`${API}/api/cases/${summary.id}`)).json() as { answer_ids: string[] };
      for (const id of study.answer_ids) ids.add(id);
    }
    for (const endpoint of ["watches", "notifications"]) {
      const entries = await (await request.get(`${API}/api/${endpoint}`)).json() as { answer_id: string | null }[];
      for (const entry of entries) if (entry.answer_id) ids.add(entry.answer_id);
    }
    for (const id of ids) {
      for (const lang of LANGS) {
        await page.goto(`/${lang}/answers/${encodeURIComponent(id)}`);
        await expect(page.getByRole("region", { name: LIMITS[lang] })).toBeVisible();
        await reviewScreen(page, `answer-${id}-${lang}`);
      }
    }
  });

  test("clicking on the map picks a point for the question", async ({ page }) => {
    await page.goto("/en/ask");
    await waitForMap(page);
    await expect(page.getByText("No point chosen")).toBeVisible();
    await page.locator(".maplibregl-canvas").click({ position: { x: 300, y: 200 } });
    await expect(page.getByText("Point chosen:")).toBeVisible();
    await page.getByRole("button", { name: "Remove the point" }).click();
    await expect(page.getByText("No point chosen")).toBeVisible();
  });
});
