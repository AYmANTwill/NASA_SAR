/**
 * Motion: always staged by default, and fully removed by prefers-reduced-motion
 * (a precomputed answer then comes out at once, with every raster visible).
 */
import { expect, test } from "@playwright/test";
import { DEMO, STAGE_MAX_MS, waitForMap, watchConsole } from "./helpers";

async function ask(page: import("@playwright/test").Page, question: string) {
  await page.goto("/investigate");
  await waitForMap(page);
  await page.getByLabel("Votre question").fill(question);
  const start = Date.now();
  await page.getByRole("button", { name: "Demander" }).click();
  await expect(page.locator("#verdict")).toBeVisible();
  return Date.now() - start;
}

test("answers are staged: steps arrive one by one, under four seconds", async ({ page }) => {
  const errors = watchConsole(page);
  const ms = await ask(page, DEMO.panama.fr);
  expect(ms).toBeGreaterThan(800);
  expect(ms).toBeLessThan(STAGE_MAX_MS);
  expect(errors).toEqual([]);
});

test.describe("reduced motion", () => {
  test.use({ colorScheme: "light", reducedMotion: "reduce" });
  test("precomputed answer comes out at once, rasters fully drawn", async ({ page }) => {
    const errors = watchConsole(page);
    const ms = await ask(page, DEMO.panama.fr);
    expect(ms).toBeLessThan(1_000);
    await expect(page.getByRole("checkbox", { name: /Déplacement/ })).toBeChecked();
    expect(errors).toEqual([]);
  });
});
