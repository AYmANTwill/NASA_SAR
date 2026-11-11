/**
 * Runs the real HTTP adapter (production build, VITE_API_MODE=http) against
 * /api answered by Playwright from the fixtures: JSON endpoints, SSE streaming,
 * contract validation and the persisted offline cache.
 */
import { expect, test, type Page, type Route } from "@playwright/test";
import * as fx from "../src/__fixtures__";
import { waitForMap, watchConsole } from "./helpers";

test.use({ serviceWorkers: "block" });

const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function mockApi(page: Page, overrides: { discoveries?: unknown } = {}) {
  const answers = new Map(fx.fixtureAnswers.map((a) => [a.id, a]));
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    if (path === "/demo") return json(route, fx.demoBundle);
    if (path === "/discoveries") return json(route, overrides.discoveries ?? fx.discoveries);
    if (path === "/watches" && route.request().method() === "GET") return json(route, fx.initialWatches);
    if (path === "/watches" && route.request().method() === "POST") {
      const { answer_id } = route.request().postDataJSON() as { answer_id: string };
      const a = answers.get(answer_id)!;
      return json(route, { ...fx.initialWatches[0], id: "w-new", answer_id, location: a.location, question: a.question, level: null, next_pass: a.next_pass ?? "2026-11-20" });
    }
    if (path === "/notifications") return json(route, fx.initialNotifications);
    if (path === "/library") return json(route, fx.library);
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
  await page.goto("/");
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
  expect(Date.now() - start).toBeLessThan(1_000);
  await expect(page.getByText("Hors ligne : réponse rejouée depuis le cache local.")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Hors ligne" }).first()).toBeVisible();
});
