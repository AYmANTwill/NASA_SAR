import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pageScreenshot, waitForMap } from "../e2e/backend";

interface Snapshot {
  responses: Record<string, { status: number; body: unknown }>;
}
const snapshot = JSON.parse(readFileSync(join(process.cwd(), "demo-data", "snapshot.json"), "utf8")) as Snapshot;
const demo = snapshot.responses["/demo"]!.body as { entries: { answer_id: string; questions: { text: string; lang: string }[] }[] };
const cases = snapshot.responses["/cases"]!.body as { id: string; title: Record<string, string> }[];

const LANGS = ["fr", "en", "ar"] as const;
const LIMITS = { fr: "Ce que le radar ne peut pas dire ici", en: "What the radar cannot tell here", ar: "ما لا يستطيع الرادار قوله هنا" };

/** No backend, no internet: anything not served by the demo build itself is refused. */
async function offline(page: Page) {
  const outside: string[] = [];
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.host === "127.0.0.1:4312") return route.continue();
    outside.push(url.href);
    return route.abort("internetdisconnected");
  });
  return outside;
}

for (const lang of LANGS) {
  test(`${lang}: the demo path works offline (cases, a case, a demo question, the library)`, async ({ page }) => {
    const outside = await offline(page);

    await page.goto(`/${lang}/`);
    await expect(page.locator(".shell-demo")).toBeVisible();
    for (const c of cases) await expect(page.getByRole("link", { name: c.title[lang] })).toBeVisible();

    await page.getByRole("link", { name: cases[0]!.title[lang] }).click();
    await expect(page.getByRole("region", { name: LIMITS[lang] })).toBeVisible();
    await waitForMap(page);
    await pageScreenshot(page, `e2e/__screenshots__/demo-case-${lang}.png`);

    const question = demo.entries[0]!.questions.find((q) => q.lang === lang)!.text;
    await page.goto(`/${lang}/ask`);
    await page.getByRole("button", { name: question }).click();
    await expect(page.getByRole("region", { name: LIMITS[lang] })).toBeVisible();
    await expect(page.locator(".steps .step").first()).toBeVisible();

    await page.goto(`/${lang}/library`);
    await expect(page.locator(".library-card").first()).toBeVisible();

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
    expect(outside, "requests that left the demo server").toEqual([]);
  });
}

test("a question outside the demo says so, and watching changes nothing", async ({ page }) => {
  await offline(page);
  await page.goto("/en/ask");
  await page.getByRole("textbox").fill("Is the ground moving under my house?");
  await page.getByRole("button", { name: "Investigate" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Not available in the offline demo" })).toBeVisible();

  await page.goto(`/en/answers/${demo.entries[0]!.answer_id}`);
  await page.getByRole("button", { name: "Watch this place" }).click();
  await expect(page.getByRole("status").filter({ hasText: "The offline demo changes nothing" })).toBeVisible();
  await pageScreenshot(page, "e2e/__screenshots__/demo-answer-en.png");
});
