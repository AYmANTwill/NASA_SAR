/**
 * Runs the real HTTP adapter (production build, VITE_API_MODE=http) against
 * /api answered by Playwright from the fixtures: JSON endpoints, SSE streaming,
 * contract validation and the persisted offline cache.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";
import * as fx from "../src/__fixtures__";
import { STAGE_MAX_MS, waitForMap, watchConsole } from "./helpers";

test.use({ serviceWorkers: "block" });

const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

type Override = { status: number; body: unknown };
async function mockApi(page: Page, overrides: { discoveries?: unknown; discoveriesError?: Override; proofError?: Override; cases?: unknown; studies?: { id: string }[] } = {}) {
  const answers = new Map(fx.fixtureAnswers.map((a) => [a.id, a]));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    if (path === "/demo") return json(route, fx.demoBundle);
    if (path === "/discoveries" && overrides.discoveriesError) return json(route, overrides.discoveriesError.body, overrides.discoveriesError.status);
    if (path === "/discoveries") return json(route, overrides.discoveries ?? fx.discoveries);
    if (path === "/watches" && route.request().method() === "GET") return json(route, fx.initialWatches);
    if (path === "/watches" && route.request().method() === "POST") {
      const { answer_id } = route.request().postDataJSON() as { answer_id: string };
      const a = answers.get(answer_id)!;
      return json(route, { ...fx.initialWatches[0], id: "w-new", answer_id, location: a.location, question: a.question, level: null, next_pass: a.next_pass ?? "2026-11-20" });
    }
    if (path === "/notifications") return json(route, fx.initialNotifications);
    if (path === "/library") return json(route, fx.library);
    if (path === "/cases") return json(route, overrides.cases ?? fx.caseSummaries);
    if (path.startsWith("/cases/")) {
      const id = decodeURIComponent(path.slice("/cases/".length));
      const c = overrides.studies?.find((x) => x.id === id) ?? fx.caseStudies.find((x) => x.id === id);
      return c ? json(route, c) : json(route, { code: "not_found", message: { template: "error.not_found", params: {} } }, 404);
    }
    if (path === "/proofs/lband-vs-cband" && overrides.proofError) return json(route, overrides.proofError.body, overrides.proofError.status);
    if (path === "/proofs/lband-vs-cband") return json(route, fx.lbandProof);
    if (path.startsWith("/answers/")) {
      const a = answers.get(decodeURIComponent(path.slice("/answers/".length)));
      return a ? json(route, a) : json(route, { code: "not_found", message: { template: "error.not_found", params: {} } }, 404);
    }
    if (path === "/ask") {
      const { question } = route.request().postDataJSON() as { question: string };
      const a = fx.fixtureAnswers.find((x) => fx.demoBundle.entries.some((e) => e.answer_id === x.id && e.questions.some((q) => q.text === question)));
      if (!a) return route.fulfill({ status: 200, contentType: "text/event-stream", body: `event: error\ndata: ${JSON.stringify({ code: "no_coverage", message: { template: "error.no_coverage", params: {} } })}\n\n` });
      const events = a.steps.map((s) => `event: step\ndata: ${JSON.stringify(s)}\n\n`).join("") + `event: answer\ndata: ${JSON.stringify(a)}\n\n`;
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: events });
    }
    return route.fulfill({ status: 404, body: "" });
  });
}

test("ask over SSE renders steps, verdict and limits", async ({ page }) => {
  const errors = watchConsole(page);
  await mockApi(page);
  await page.goto("/investigate");
  await expect(page.getByText("Données de test")).toHaveCount(0); // no fixture banner in http mode
  await page.getByRole("textbox", { name: "Votre question" }).fill(fx.fixtureAnswers[0].question);
  await page.getByRole("button", { name: "Demander" }).click();
  await expect(page.locator("#verdict")).toContainText(/46 ± 3\W* cm/);
  await expect(page.getByRole("button", { name: /Étapes de l'agent/ })).toContainText("7");
  await expect(page.getByText("Ce que le radar ne peut pas dire ici")).toBeVisible();
  expect(errors).toEqual([]);
});

test("backend error body is shown in the user's language", async ({ page }) => {
  await mockApi(page);
  await page.goto("/investigate?lang=en");
  await page.getByRole("textbox", { name: "Your question" }).fill("Is my roof moving?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("alert")).toContainText("No NISAR scene covers this place");
});

test("contract violation shows an explicit error, never a guessed value", async ({ page }) => {
  const broken = structuredClone(fx.discoveries) as unknown as { zones: { velocity: Record<string, unknown> }[] };
  delete broken.zones[0].velocity.uncertainty;
  await mockApi(page, { discoveries: broken });
  await page.goto("/discover");
  await expect(page.getByRole("alert")).toContainText("contrat d'API");
  await expect(page.getByText("Versant de Taounate")).toHaveCount(0);
});

test("offline: precomputed answers replay from the persisted cache", async ({ page, context }) => {
  await mockApi(page);
  await page.goto("/");
  // useDemoPrefetch downloads the bundle and each precomputed answer.
  await expect.poll(() => page.evaluate(() => localStorage.getItem("nisar-pulse-cache-v2")?.includes("fx-alwahda-since-june") ?? false), { timeout: 15_000 }).toBe(true);
  await page.goto("/investigate");
  await waitForMap(page); // let lazy chunks finish before the cut (no service worker here)
  await context.setOffline(true);
  await page.getByRole("textbox", { name: "Votre question" }).fill("Le barrage se déforme-t-il depuis juin ?");
  const start = Date.now();
  await page.getByRole("button", { name: "Demander" }).click();
  await expect(page.locator("#verdict")).toBeVisible();
  expect(Date.now() - start).toBeLessThan(STAGE_MAX_MS);
  await expect(page.getByText("Hors ligne : réponse rejouée depuis le cache local.")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Hors ligne" }).first()).toBeVisible();
});

// Bodies exactly as the team's backend returns them (feat/frontend-adapter, 14/11).
const backendMessage = (code: string, fr: string) => ({ code, message: { template: `backend.error.${code}`, params: {}, text: { fr, en: fr, ar: fr } } });

test("discoveries switched off (503) is an information state, not an error", async ({ page }) => {
  await mockApi(page, { discoveriesError: { status: 503, body: backendMessage("discoveries_disabled", "Découverte automatique désactivée.") } });
  await page.goto("/discover");
  await expect(page.getByRole("heading", { level: 1, name: "Ce que NISAR a regardé" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "La détection automatique est désactivée" })).toBeVisible();
  await expect(page.getByText("Découverte automatique désactivée.")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Réessayer" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Panama/ }).first()).toBeVisible();
});

test("L/C comparison not computed (404) is labelled, with the physics explainer", async ({ page }) => {
  await mockApi(page, { proofError: { status: 404, body: backendMessage("not_available", "Pas encore calculée.") } });
  await page.goto("/proof");
  await expect(page.getByRole("status").filter({ hasText: "Comparaison pas encore calculée" })).toBeVisible();
  await expect(page.getByRole("img", { name: /Sentinel-1/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Bande L \/ bande C/ })).toContainText("bientôt");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("case studies: first page, draft banner, findings with agreement and limits", async ({ page }) => {
  const errors = watchConsole(page);
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Études de cas" })).toBeVisible();
  await page.getByRole("link", { name: /Séisme du Panama/ }).click();
  await expect(page.getByRole("note").filter({ hasText: "BROUILLON" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Pas de référence");
  await expect(page.getByRole("heading", { name: "Ce que le radar ne peut pas dire ici" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ouvrir dans l’enquêteur" })).toHaveAttribute("href", /\/investigate\//);
  expect(errors).toEqual([]);
});

test("a fifth case served by the API gets its own card", async ({ page }) => {
  const errors = watchConsole(page);
  // Test-only summary: same shape as the API's, title marked as a test.
  const fifth = { ...fx.caseSummaries[0], id: "bin-el-ouidane-2026", title: { fr: "Cas de test 5", en: "Test case 5", ar: "Test case 5" } };
  await mockApi(page, { cases: [...fx.caseSummaries, fifth] });
  await page.goto("/");
  const cards = page.getByRole("list", { name: "Études de cas", exact: true }).getByRole("listitem");
  await expect(cards).toHaveCount(fx.caseSummaries.length + 1);
  await expect(page.getByRole("link", { name: "Cas de test 5" })).toHaveAttribute("href", "/cases/bin-el-ouidane-2026");
  expect(errors).toEqual([]);
});

// Test-only case, labelled as such: shape of the coming Haouz case (negative verdict, no strong number,
// several long limits) and of the dam case (image figures). Checks layout and tone, not values.
const longLimit = (n: number) => ({
  template: `test.limit${n}`,
  params: {},
  text: {
    fr: `Limite de test ${n} : texte long pour vérifier la lecture, produits provisoires, signe non vérifié, magnitude non estimée, à ne pas lire comme une mesure.`,
    en: `Test limit ${n}: long text to check reading, provisional products, sign not verified, magnitude not estimated, not to be read as a measurement.`,
    ar: `حدّ اختباري ${n}: نص طويل للتحقق من القراءة، منتجات مؤقتة، إشارة غير متحقق منها، شدة غير مقدّرة، لا يُقرأ كقياس.`,
  },
});
const negativeCase = {
  ...fx.caseStudies.find((c) => c.id === "haouz-flood-2026")!,
  status: "final",
  title: { fr: "Cas de test : aucun changement net", en: "Test case: no net change", ar: "حالة اختبار: لا تغيّر صافٍ" },
  headline: { template: "test.headline", params: {}, text: { fr: "Test : aucun changement net au-dessus de la dispersion de référence.", en: "Test: no net change above the reference spread.", ar: "اختبار: لا تغيّر صافٍ فوق التشتت المرجعي." } },
  findings: [
    {
      id: "test-baseline",
      label: { fr: "Test comparé à la ligne de base sans événement", en: "Test compared with the no-event baseline", ar: "اختبار مقارنة بخط الأساس دون حدث" },
      nisar: { value: 0.1, uncertainty: 0.2, unit: "km2", sigma: 1 },
      reference: { value: 0, uncertainty: 0.3, unit: "km2", sigma: 1 },
      reference_source: { name: "Test no-event baseline", url: "https://example.org/" },
      agreement: "agree",
    },
  ],
  exposure: null,
  figures: [
    { id: "before-after", kind: "image", title: { fr: "Test avant / après", en: "Test before / after", ar: "اختبار قبل / بعد" }, url: "/__fixtures__/rasters/alwahda-velocity.png", caption: { template: "test.cap", params: {}, text: { fr: "Légende de test.", en: "Test caption.", ar: "تعليق اختباري." } } },
    { id: "clouds", kind: "image", title: { fr: "Test nuages contre radar", en: "Test clouds vs radar", ar: "اختبار السحب مقابل الرادار" }, url: "/__fixtures__/rasters/gharb-soil-moisture.png", caption: { template: "test.cap", params: {}, text: { fr: "Légende de test.", en: "Test caption.", ar: "تعليق اختباري." } } },
    { id: "missing", kind: "image", title: { fr: "Test image absente", en: "Test missing image", ar: "اختبار صورة مفقودة" }, url: "/__fixtures__/rasters/does-not-exist.png", caption: { template: "test.cap", params: {}, text: { fr: "Légende de test.", en: "Test caption.", ar: "تعليق اختباري." } } },
  ],
  limits: [1, 2, 3, 4, 5].map(longLimit),
};

for (const width of [390, 1280]) {
  test(`negative verdict, long limits and image figures stay calm and readable (ar, ${width}px)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" }); // contrast is measured on the settled page, not mid-fade (motion has its own spec)
    const errors = watchConsole(page);
    await mockApi(page, { studies: [negativeCase] });
    await page.goto("/cases/haouz-flood-2026?lang=ar");
    await expect(page.getByRole("heading", { level: 1, name: "حالة اختبار: لا تغيّر صافٍ" })).toBeVisible();
    // Never suggests a detection: no alert, no failure colour, no draft banner on a final case.
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.locator(".text-fail, .border-fail, .bg-fail")).toHaveCount(0);
    await expect(page.getByRole("note")).toHaveCount(0);
    // Against the no-event baseline, "agree" is explained as "not different from no change".
    await expect(page.getByRole("table")).toContainText("هنا، «اتفاق» يعني «لا يختلف عن غياب التغيّر».");
    // Every limit is visible and nothing overflows, in RTL, on a phone too.
    const limits = page.getByRole("region", { name: "ما لا يستطيع الرادار قوله هنا" }).getByRole("listitem");
    await expect(limits).toHaveCount(5);
    for (const li of await limits.all()) await expect(li).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    // Image figures: whole, captioned, a missing one is said, and each opens full screen.
    await expect(page.getByText("الصورة غير متاحة حالياً.")).toBeVisible();
    await page.getByRole("button", { name: /اختبار قبل \/ بعد/ }).click();
    const dialog = page.getByRole("dialog", { name: "اختبار قبل / بعد" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("img")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.locator('[data-slot="dialog-overlay"]')).toHaveCount(0); // axe runs once the overlay is gone
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).exclude(".maplibregl-canvas").analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
    expect(errors.filter((e) => !e.includes("does-not-exist"))).toEqual([]);
  });
}
