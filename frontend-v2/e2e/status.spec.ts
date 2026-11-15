import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen } from "./backend";

const TEXT = {
  fr: { reachable: "Joignable", discoveries: "Découverte automatique désactivée" },
  en: { reachable: "Reachable", discoveries: "Automatic discovery is off" },
  ar: { reachable: "متاح", discoveries: "الاكتشاف التلقائي معطّل" },
} as const;

test.describe("status page, live backend", () => {
  test.beforeEach(requireBackend);

  for (const lang of LANGS) {
    test(`${lang}: health and information states from the API`, async ({ page }) => {
      await page.goto(`/${lang}/status`);
      await expect(page.getByText(TEXT[lang].reachable)).toBeVisible();
      // 503 discoveries_disabled is information (role=status), not an error (role=alert).
      await expect(page.getByRole("status").filter({ hasText: TEXT[lang].discoveries })).toBeVisible();
      await expect(page.getByRole("alert")).toHaveCount(0);
      await reviewScreen(page, `status-${lang}`);
    });
  }
});

test.describe("errors are explicit", () => {
  test("a response that breaks the contract is rejected and explained", async ({ page }) => {
    await page.route("**/api/health", (route) => route.fulfill({ json: { status: "ok", version: "x", data: "maybe" } }));
    await page.goto("/en/status");
    const alert = page.getByRole("alert").filter({ hasText: "Response rejected" });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("GET /health");
    await expect(alert).toContainText("data");
    await page.screenshot({ path: "e2e/__screenshots__/error-contract-en.png", fullPage: true });
  });

  test("an unreachable server says so, in Arabic too", async ({ page }) => {
    await page.route("**/api/health", (route) => route.abort("connectionrefused"));
    await page.goto("/ar/status");
    await expect(page.getByRole("alert").filter({ hasText: "تعذّر الوصول إلى الخادم" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: "إعادة المحاولة" })).toBeVisible();
    await page.screenshot({ path: "e2e/__screenshots__/error-offline-ar.png", fullPage: true });
  });
});
