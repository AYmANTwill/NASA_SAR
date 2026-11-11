import type { Page } from "@playwright/test";

/** Collects console errors and uncaught exceptions for the whole test. */
export function watchConsole(page: Page) {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  return errors;
}

/** Waits until the map has parsed its style and drawn at least once. */
export async function waitForMap(page: Page) {
  await page.locator(".maplibregl-canvas").first().waitFor({ state: "visible" });
}

export const DEMO = {
  panama: { fr: "Où le sol a-t-il bougé après le séisme du 9 octobre ?" },
  alWahda: { fr: "Le barrage se déforme-t-il depuis juin ?" },
  gharb: { fr: "Mes champs du Gharb sont-ils saturés ?" },
};
