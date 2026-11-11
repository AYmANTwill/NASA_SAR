/**
 * Replays the 3-minute jury demo end to end and times it.
 * Run before going on stage:  npm run e2e:demo
 */
import { expect, test } from "@playwright/test";
import { DEMO, waitForMap, watchConsole } from "./helpers";

test("demo path: Panama → discoveries → Al Wahda → watch → L/C proof → live SME2", async ({ page }, info) => {
  const errors = watchConsole(page);
  const nav = page.getByRole("navigation", { name: "Navigation principale" });
  const timings: Record<string, number> = {};
  const t0 = Date.now();
  const lap = (name: string, start: number) => (timings[name] = Date.now() - start);

  async function ask(question: string) {
    const box = page.getByRole("textbox", { name: "Votre question" });
    await box.fill(question);
    const start = Date.now();
    await page.getByRole("button", { name: "Demander" }).click();
    await expect(page.locator("#verdict")).toBeVisible({ timeout: 15_000 });
    return Date.now() - start;
  }

  await test.step("1. Panama: agent steps, then displacement, coherence loss, USGS", async () => {
    await page.goto("/investigate");
    await waitForMap(page);
    const box = page.getByRole("textbox", { name: "Votre question" });
    await box.fill(DEMO.panama.fr);
    const start = Date.now();
    await page.getByRole("button", { name: "Demander" }).click();
    // Steps appear while running, before the verdict.
    await expect(page.getByRole("heading", { name: /Étapes de l'agent/ })).toBeVisible();
    await expect(page.locator("#steps-list li").first()).toBeVisible();
    await expect(page.locator("#verdict")).toBeVisible();
    timings["panama_answer_ms"] = Date.now() - start;
    expect(timings["panama_answer_ms"], "precomputed answer must come out in under a second").toBeLessThan(1_000);
    await expect(page.getByRole("checkbox", { name: /Déplacement/ })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: /Perte de cohérence/ })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: /Séismes USGS/ })).toBeChecked();
    await expect(page.getByText("Ce que le radar ne peut pas dire ici")).toBeVisible();
  });

  await test.step("2. Discoveries: first zone → vertical + east-west, curve, verdict", async () => {
    const start = Date.now();
    await nav.getByRole("link", { name: "Découvertes", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: /Ce que NISAR a trouvé/ })).toBeVisible();
    await page.getByRole("list", { name: "Zones classées" }).getByRole("link").first().click();
    await expect(page.locator("#verdict")).toBeVisible();
    lap("zone_open_ms", start);
    await expect(page.getByRole("heading", { name: "Vertical et est-ouest" })).toBeVisible();
    await expect(page.locator("figure").filter({ hasText: "Vertical" }).first()).toBeVisible();
    await expect(page.locator("figure").filter({ hasText: "Est-ouest" }).first()).toBeVisible();
    await expect(page.getByText("Indication de fenêtre de rupture")).toBeVisible();
  });

  await test.step("3. Al Wahda: instant cached answer with uncertainty band", async () => {
    await nav.getByRole("link", { name: "Enquête", exact: true }).click();
    const ms = await ask(DEMO.alWahda.fr);
    timings["alwahda_answer_ms"] = ms;
    expect(ms, "precomputed answer must come out in under a second").toBeLessThan(1_000);
    await expect(page.getByText("Stable dans le bruit").first()).toBeVisible();
    await expect(page.getByText(/Incertitude \(±/).first()).toBeVisible();
  });

  await test.step("4. Watch: next pass and FR + AR notification", async () => {
    const start = Date.now();
    await page.getByRole("button", { name: "Veiller sur ce lieu" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Veille active" }).getByText(/Prochain passage NISAR le/).first()).toBeVisible();
    await expect(page.locator('blockquote[lang="fr"]')).toContainText("Veille activée");
    await expect(page.locator('blockquote[lang="ar"]')).toContainText("المراقبة مفعلة");
    lap("watch_ms", start);
  });

  await test.step("5. L-band versus C-band figure", async () => {
    const start = Date.now();
    await nav.getByRole("link", { name: "Bande L / bande C", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Bande L contre bande C" })).toBeVisible();
    await expect(page.locator("figcaption", { hasText: "Cohérence selon le couvert forestier" })).toBeVisible();
    lap("proof_ms", start);
  });

  await test.step("6. Live question on a light product (SME2, Gharb)", async () => {
    await nav.getByRole("link", { name: "Enquête", exact: true }).click();
    timings["gharb_answer_ms"] = await ask(DEMO.gharb.fr);
    await expect(page.locator("dt", { hasText: "Humidité du sol" }).first()).toBeVisible();
  });

  timings["total_ms"] = Date.now() - t0;
  await info.attach("demo-timings.json", { body: JSON.stringify(timings, null, 2), contentType: "application/json" });
  console.log("Demo timings (ms):", JSON.stringify(timings));
  expect(timings["total_ms"], "the automated path must leave ample room in 3 minutes").toBeLessThan(60_000);
  expect(errors, "no console error during the demo").toEqual([]);
});
