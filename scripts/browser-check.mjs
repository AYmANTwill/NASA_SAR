/* global document, innerWidth */
import { chromium } from "@playwright/test";
import fs from "node:fs";
fs.mkdirSync("artifacts", { recursive: true });
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--enable-webgl", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 960 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (msg) => {
  if (msg.type() === "error")
    errors.push(msg.text() + " " + msg.location().url);
});
await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);
await page.screenshot({ path: "artifacts/desktop-intro.png" });
await page.getByRole("button", { name: "Explore the planet" }).click();
await page
  .getByRole("heading", { name: "Coastal earthquakes", exact: true })
  .waitFor();
await page.waitForTimeout(3500);
await page.screenshot({ path: "artifacts/desktop-dashboard.png" });
await page.getByRole("button", { name: "Compare", exact: true }).click();
await page.getByRole("slider", { name: "Before after divider" }).fill("35");
await page.waitForTimeout(1500);
await page.screenshot({ path: "artifacts/desktop-compare.png" });
await page.getByRole("button", { name: "Close comparison" }).click();
for (const name of ["Souss-Massa", "Bihar", "Amazon", "Mexico City"]) {
  await page.getByRole("button", { name, exact: true }).click();
  await page.waitForTimeout(250);
}
await page.getByRole("button", { name: "Open 10 alerts" }).click();
await page.getByRole("dialog").waitFor();
await page
  .getByRole("button", { name: /Coastal earthquakes detected/ })
  .click();
await page.getByText("LOCATION INSPECTOR", { exact: true }).waitFor();
await page.getByRole("button", { name: "About the observatory" }).click();
await page.getByRole("dialog").waitFor();
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "Export", exact: true }).click();
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(500);
await page.screenshot({ path: "artifacts/mobile-dashboard.png" });
await page.getByRole("button", { name: "Layers", exact: true }).click();
await page.getByRole("switch", { name: "Backscatter change" }).click();
await page.screenshot({ path: "artifacts/mobile-layers.png" });
await page.getByRole("button", { name: "Close layers" }).click();
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth > innerWidth,
);
await page.getByRole("button", { name: "NISAR Pulse home" }).click();
await page.waitForTimeout(4500);
await page.screenshot({ path: "artifacts/mobile-intro.png" });
await browser.close();
fs.writeFileSync(
  "artifacts/browser-results.json",
  JSON.stringify({ errors, overflow }, null, 2),
);
console.log(JSON.stringify({ errors, overflow }));
if (errors.length || overflow) process.exitCode = 1;
