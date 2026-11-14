import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { LANGS, requireBackend } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const LIMITS = { fr: "Ce que le radar ne peut pas dire ici", en: "What the radar cannot tell here", ar: "ما لا يستطيع الرادار قوله هنا" };
const DRAFT = { fr: "Brouillon", en: "Draft", ar: "مسودة" };

type L = (typeof LANGS)[number];
interface Study {
  id: string;
  status: "draft" | "final";
  title: Record<L, string>;
  limits: { text?: Partial<Record<L, string>> }[];
  findings: { nisar: unknown; reference: unknown; agreement: string }[];
}

test.describe("case view, live backend", () => {
  test.beforeEach(requireBackend);

  test("every case in every language: title, draft band, limits, accessibility", async ({ page, request }) => {
    test.setTimeout(240_000);
    const ids = ((await (await request.get(`${API}/api/cases`)).json()) as { id: string }[]).map((c) => c.id);
    for (const id of ids) {
      const study = (await (await request.get(`${API}/api/cases/${id}`)).json()) as Study;
      for (const lang of LANGS) {
        await page.goto(`/${lang}/cases/${id}`);
        await expect(page.getByRole("heading", { level: 1 })).toHaveText(study.title[lang]);
        await expect(page.getByRole("note")).toHaveCount(study.status === "draft" ? 1 : 0);
        if (study.status === "draft") await expect(page.getByRole("note")).toContainText(DRAFT[lang]);
        const limits = page.getByRole("region", { name: LIMITS[lang] });
        await expect(limits).toBeVisible();
        for (const l of study.limits) if (l.text?.[lang]) await expect(limits).toContainText(l.text[lang]!);
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
        expect(results.violations.map((v) => `${id}/${lang} ${v.id}: ${v.help}`)).toEqual([]);
        if (id === ids[0]) {
          for (const width of [1440, 1024, 390]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
            expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(0);
            await page.screenshot({ path: `e2e/__screenshots__/case-${id}-${lang}-${width}.png`, fullPage: true });
          }
          await page.setViewportSize({ width: 1440, height: 900 });
        }
      }
    }
  });

  test("a draft never shows its placeholder as a number or as a disagreement", async ({ page, request }) => {
    const study = (await (await request.get(`${API}/api/cases/panama-2026`)).json()) as Study;
    test.skip(study.status !== "draft", "Panama is final now: this check is for drafts");
    await page.goto("/en/cases/panama-2026");
    await expect(page.getByText("not measured yet").first()).toBeVisible();
    await expect(page.getByText(/^Disagrees/)).toHaveCount(0);
  });
});

test("preview of a final case: the comparison strip (API values, NISAR set to the reference by the test)", async ({ page, request }) => {
  await requireBackend();
  const study = (await (await request.get(`${API}/api/cases/panama-2026`)).json()) as Study;
  study.status = "final";
  study.findings = study.findings.filter((f) => f.reference).map((f) => ({ ...f, nisar: f.reference, agreement: "agree" }));
  await page.route("**/api/cases/panama-2026", (route) => route.fulfill({ json: study }));
  for (const lang of LANGS) {
    await page.goto(`/${lang}/cases/panama-2026`);
    await expect(page.locator("svg.strip").first()).toBeVisible();
    await page.locator(".ledger").screenshot({ path: `e2e/__screenshots__/case-final-preview-${lang}.png` });
  }
});
