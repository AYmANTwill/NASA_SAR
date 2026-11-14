/**
 * Network cut: the demo path must still work from the service worker cache,
 * with the discreet offline indicator and no console error.
 */
import { expect, test } from "@playwright/test";
import { DEMO, waitForMap, watchConsole } from "./helpers";

test("demo path replays offline from cache", async ({ page, context }) => {
  // 1. Online visit installs the service worker and precaches the app.
  await page.goto("/");
  await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) await new Promise((r) => navigator.serviceWorker.addEventListener("controllerchange", r, { once: true }));
    return !!reg.active;
  });
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  // 2. Cut the network.
  await context.setOffline(true);
  const errors = watchConsole(page);
  await page.reload();
  const nav = page.getByRole("navigation", { name: "Navigation principale" });
  await expect(page.getByRole("status").filter({ hasText: "Hors ligne" })).toBeVisible();
  // The home page is now the case studies (cached offline).
  await expect(page.getByRole("heading", { level: 1, name: "Études de cas" })).toBeVisible();

  // 3. Replay the demo.
  await nav.getByRole("link", { name: "Enquête", exact: true }).click();
  await expect(page.getByText("Fond de carte simplifié (hors ligne)")).toBeVisible();
  await waitForMap(page);
  for (const q of [DEMO.panama.fr, DEMO.alWahda.fr]) {
    await page.getByRole("textbox", { name: "Votre question" }).fill(q);
    await page.getByRole("button", { name: "Demander" }).click();
    await expect(page.locator("#verdict")).toBeVisible();
    await expect(page.getByText("Ce que le radar ne peut pas dire ici")).toBeVisible();
    await nav.getByRole("link", { name: "Enquête", exact: true }).click();
  }
  await nav.getByRole("link", { name: "Découvertes", exact: true }).click();
  await page.getByRole("list", { name: "Zones classées" }).getByRole("link").first().click();
  await expect(page.locator("#verdict")).toBeVisible();
  // This zone is already watched in the fixtures: the watch card (FR + AR) shows instead of the button.
  const watchButton = page.getByRole("button", { name: "Veiller sur ce lieu" });
  if (await watchButton.isVisible()) await watchButton.click();
  await expect(page.locator('blockquote[lang="ar"]')).toBeVisible();
  await nav.getByRole("link", { name: "Bande L / bande C", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Bande L contre bande C" })).toBeVisible();

  expect(errors).toEqual([]);
});
