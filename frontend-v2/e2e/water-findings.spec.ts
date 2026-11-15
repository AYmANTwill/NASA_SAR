import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { CaseStudy, Finding } from "../src/api/contract";
import { formatNumber } from "../src/i18n/format";
import { LANGS, requireBackend, reviewScreen } from "./backend";

const API = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
const RESERVOIR = "bin-el-ouidane-2026";
const HAOUZ = "haouz-flood-2026";
const formatted = (f: Finding, lang: (typeof LANGS)[number]) => `${formatNumber(f.nisar.value, lang)} ± ${formatNumber(f.nisar.uncertainty, lang)}`;
const locales = Object.fromEntries(LANGS.map((lang) => [lang, JSON.parse(readFileSync(join(process.cwd(), `src/i18n/locales/${lang}.json`), "utf8")) as { case: Record<string, string> }]));

test.describe("water evidence semantics", () => {
  test.beforeEach(requireBackend);

  test("the model score is the live heldout_iou in every language and viewport", async ({ page, request }) => {
    test.setTimeout(120_000);
    const study = await (await request.get(`${API}/api/cases/${RESERVOIR}`)).json() as CaseStudy;
    const finding = study.findings.find((f) => f.id === "heldout_iou");
    expect(finding).toBeTruthy();
    for (const lang of LANGS) {
      await page.goto(`/${lang}/cases/${RESERVOIR}`);
      const quality = page.locator('[aria-labelledby="finding-heldout_iou"]');
      await expect(quality.locator(".measure-number")).toHaveText(formatted(finding!, lang));
      await expect(quality.locator(".finding-context")).toHaveText(locales[lang]!.case.heldoutIouContext!);
      await reviewScreen(page, `model-heldout-${lang}`);
    }
  });

  test("a future model score is read from its HTTP response", async ({ page, request }) => {
    const study = await (await request.get(`${API}/api/cases/${RESERVOIR}`)).json() as CaseStudy;
    const heldout = study.findings.find((f) => f.id === "heldout_iou")!;
    const other = study.findings.find((f) => f.id === "orbit_consistency")!;
    heldout.nisar = { ...heldout.nisar, value: other.nisar.value, uncertainty: other.nisar.uncertainty };
    await page.route(`**/api/cases/${RESERVOIR}`, (route) => route.fulfill({ json: study }));
    for (const lang of LANGS) {
      await page.goto(`/${lang}/cases/${RESERVOIR}`);
      await expect(page.locator('[aria-labelledby="finding-heldout_iou"] .measure-number')).toHaveText(formatted(heldout, lang));
    }
  });

  test("Haouz open_water_change stays neutral and is not a flood detection", async ({ page, request }) => {
    test.setTimeout(120_000);
    let study = await (await request.get(`${API}/api/cases/${HAOUZ}`)).json() as CaseStudy;
    const preview = !study.findings.some((f) => f.id === "open_water_change");
    if (preview) {
      // main still serves an empty Haouz draft. This preview is assembled by the backend from its real water package.
      study = (JSON.parse(readFileSync(join(process.cwd(), "src/test/recorded/haouz-open-water-package.json"), "utf8")) as { body: CaseStudy }).body;
      test.info().annotations.push({ type: "data", description: "Backend-assembled water package preview; the live Haouz draft has no findings yet." });
      await page.route(`**/api/cases/${HAOUZ}`, (route) => route.fulfill({ json: study }));
    }
    const finding = study.findings.find((f) => f.id === "open_water_change")!;
    expect(finding.reference).toBeNull();
    expect(finding.agreement).toBe("no_reference");
    for (const lang of LANGS) {
      await page.goto(`/${lang}/cases/${HAOUZ}`);
      const water = page.locator('[aria-labelledby="finding-open_water_change"]');
      await expect(water.locator(".measure-number")).toHaveText(formatted(finding, lang));
      await expect(water.locator(".finding-interpretation")).toHaveText(locales[lang]!.case.openWaterNoClearChange!);
      const badge = water.locator(".agreement-no_reference");
      await expect(badge).toBeVisible();
      const neutral = await water.locator(".finding-context").evaluate((el) => getComputedStyle(el).color);
      await expect(badge).toHaveCSS("color", neutral);
      await expect(water.locator(".agreement-agree, .agreement-partial, .agreement-disagree, svg.strip, .fill")).toHaveCount(0);
      await reviewScreen(page, `haouz-open-water${preview ? "-preview" : ""}-${lang}`);
    }
  });
});
