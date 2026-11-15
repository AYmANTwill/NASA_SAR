import { expect, test } from "@playwright/test";
import { LANGS, requireBackend, reviewScreen, waitForMap } from "./backend";
import { discoveryScenario, proofScenario } from "../src/test/parity-scenarios";

test.beforeEach(requireBackend);

for (const lang of LANGS) {
  test(`${lang}: available discovery and proof branches (synthetic UI fixtures only)`, async ({ page }) => {
    await page.route("**/api/discoveries?region=MA", (route) => route.fulfill({ json: discoveryScenario }));
    await page.route("**/api/proofs/lband-vs-cband", (route) => route.fulfill({ json: proofScenario }));
    await page.route("**/__fixtures__/rasters/*", (route) => route.fulfill({ path: `../frontend/public/__fixtures__/rasters/${new URL(route.request().url()).pathname.split("/").pop()}` }));
    await page.goto(`/${lang}/discover`);
    await expect(page.locator(".evidence-row")).toHaveCount(discoveryScenario.zones.length);
    await reviewScreen(page, `discover-synthetic-${lang}`);
    await page.goto(`/${lang}/proof`);
    await expect(page.locator(".forest-bin")).toHaveCount(proofScenario.bins.length);
    await expect(page.locator(".sensor-labels")).toHaveAttribute("dir", "ltr");
    await reviewScreen(page, `proof-synthetic-${lang}`);
  });

  test(`${lang}: exploration and radar comparison, live availability, desktop and phone`, async ({ page }) => {
    await page.goto(`/${lang}/discover`);
    await expect(page.locator(".evidence-listing")).toBeVisible();
    await expect(page.locator(".map-location-marker").first()).toBeAttached();
    await reviewScreen(page, `discover-${lang}`);
    await page.goto(`/${lang}/proof`);
    await expect(page.locator(".band-explainer")).toBeVisible();
    await expect(page.locator(".loading")).toHaveCount(0);
    await reviewScreen(page, `proof-${lang}`);
    await page.setViewportSize({ width: 390, height: 900 });
    await page.locator(".menu-toggle").click();
    await expect(page.locator(".shell-nav")).toBeVisible();
    await expect(page.locator(".shell-nav a")).toHaveCount(7);
    await page.locator(`.shell-nav a[href='/${lang}/discover']`).click();
    await expect(page).toHaveURL(new RegExp(`/${lang}/discover$`));
    await expect(page.locator(".shell-nav")).toBeHidden();
  });
}

test("figures, map opacity, JSON export and presentation retain API values", async ({ page, request }) => {
  const study = await (await request.get("/api/cases/bin-el-ouidane-2026")).json();
  await page.goto("/en/cases/bin-el-ouidane-2026");
  await waitForMap(page);
  const opener = page.locator(".figure-open").first();
  await opener.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").locator("img")).toHaveAttribute("src", study.figures[0].url);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(opener).toBeFocused();
  await page.getByRole("slider").fill("0.35");
  await expect(page.getByRole("slider")).toHaveValue("0.35");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export data" }).click()]);
  expect(download.suggestedFilename()).toBe("bin-el-ouidane-2026.json");
  await page.keyboard.press("p");
  await expect(page.locator(".app-workspace")).toHaveClass(/is-presenting/);
  await page.getByRole("button", { name: "Exit presentation" }).click();
  await expect(page.locator(".app-workspace")).not.toHaveClass(/is-presenting/);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".shell-header")).toBeHidden();
  await expect(page.locator(".limits").first()).toBeVisible();
});

test("exploration starts a question once and permits cancellation", async ({ page }) => {
  const requests: unknown[] = [];
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/ask", async (route) => {
    requests.push(route.request().postDataJSON());
    await pending;
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: "" }).catch(() => {});
  });
  try {
    await page.goto("/en/discover");
    await page.locator(".quick-ask input").fill("Investigate this place");
    await page.locator(".quick-ask button").click();
    await expect(page).toHaveURL(/\/en\/ask\?q=Investigate/);
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("button", { name: "Cancel" })).toHaveCount(0);
    expect(requests).toEqual([{ question: "Investigate this place", lang: "en", location: null }]);
  } finally { release(); }
});
