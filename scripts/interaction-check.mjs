import { chromium, expect } from "@playwright/test";
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
await page.clock.install();
await page.getByRole("button", { name: /Take a guided tour/ }).click();
const names = [
  "Coastal earthquakes",
  "Water under pressure",
  "A river beyond its banks",
  "The changing forest edge",
  "A city slowly sinking",
];
for (let i = 0; i < 5; i++) {
  await expect(
    page.getByRole("heading", { name: names[i], exact: true }),
  ).toBeVisible();
  await page.clock.fastForward(15001);
}
await expect(page.getByRole("button", { name: /End tour/ })).toHaveCount(0);
await page.locator("body").click({ position: { x: 500, y: 700 } });
await page.keyboard.press("1");
await expect(
  page.getByRole("heading", { name: names[0], exact: true }),
).toBeVisible();
await page.keyboard.press("ArrowLeft");
await expect(
  page.getByRole("slider", { name: "Acquisition date" }),
).toHaveValue("6");
await page.keyboard.press("c");
await expect(
  page.getByRole("slider", { name: "Before after divider" }),
).toBeVisible();
await page.keyboard.press("c");
await page.keyboard.press("l");
await expect(page.getByRole("complementary", { name: "Layers" })).toBeHidden();
await page.keyboard.press("l");
await expect(page.getByRole("complementary", { name: "Layers" })).toBeVisible();
await page.keyboard.press("?");
await expect(page.getByRole("dialog")).toBeVisible();
await page.keyboard.press("Escape");
await page.goto("http://127.0.0.1:5173/?case=bihar&date=2");
await expect(
  page.getByRole("heading", { name: names[2], exact: true }),
).toBeVisible();
await expect(
  page.getByRole("slider", { name: "Acquisition date" }),
).toHaveValue("2");
await browser.close();
console.log(
  "PASS: all five guided tour stops, tour completion, keyboard shortcuts, and shared view restoration.",
);
