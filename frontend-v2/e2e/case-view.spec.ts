import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const LIMITS = { fr: "Ce que le radar ne peut pas dire ici", en: "What the radar cannot tell here", ar: "ما لا يستطيع الرادار قوله هنا" };
const DRAFT = { fr: "Brouillon", en: "Draft", ar: "مسودة" };

type L = (typeof LANGS)[number];
interface Study {
  id: string;
  status: "draft" | "final";
  title: Record<L, string>;
  limits: { text?: Partial<Record<L, string>> }[];
  findings: { nisar: { uncertainty: number }; reference: { uncertainty: number } | null; agreement: string }[];
}

test.describe("case view, live backend", () => {
  test.beforeEach(requireBackend);

  test("every case in every language: title, draft band, limits, accessibility", async ({ page, request }) => {
    test.setTimeout(600_000);
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
        await reviewScreen(page, `case-${id}-${lang}`);
        await page.setViewportSize({ width: 1440, height: 900 });
      }
    }
  });

  test("a draft never shows its placeholder as a number or as a disagreement", async ({ page, request }) => {
    const study = (await (await request.get(`${API}/api/cases/panama-2026`)).json()) as Study;
    test.skip(study.status !== "draft", "Panama is final now: this check is for drafts");
    test.skip(!study.findings.some((f) => f.nisar.uncertainty === 0), "this live case has no placeholder measurement");
    await page.goto("/en/cases/panama-2026");
    await expect(page.getByText("not measured yet").first()).toBeVisible();
    await expect(page.getByText(/^Disagrees/)).toHaveCount(0);
  });
});

test("a measured case shows comparison strips from the live API", async ({ page, request }) => {
  await requireBackend();
  const summaries = await (await request.get(`${API}/api/cases`)).json() as { id: string }[];
  let measured: Study | undefined;
  for (const summary of summaries) {
    const study = await (await request.get(`${API}/api/cases/${summary.id}`)).json() as Study;
    if (study.findings.some((f) => f.reference && f.nisar.uncertainty > 0)) { measured = study; break; }
  }
  test.skip(!measured, "the live API has no measured finding with a reference yet");
  for (const lang of LANGS) {
    await page.goto(`/${lang}/cases/${measured!.id}`);
    await expect(page.locator("svg.strip").first()).toBeVisible();
  }
});
