// WCAG 2.x contrast check for the design-token pairs actually used in the UI.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const css = readFileSync(join(fileURLToPath(import.meta.url), "..", "..", "src/styles/index.css"), "utf8");
const root = css.slice(css.indexOf(":root"), css.indexOf("@theme"));
const token = (name) => {
  const m = root.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error("missing token --" + name);
  return m[1];
};

const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

// [foreground, background, minimum, what]
const pairs = [
  ["ink", "ground", 4.5, "body text on page"],
  ["ink", "surface", 4.5, "body text on panels"],
  ["ink-2", "surface", 4.5, "secondary text"],
  ["ink-2", "ground", 4.5, "secondary text on page"],
  ["muted", "surface", 4.5, "muted text"],
  ["muted", "ground", 4.5, "muted text on page"],
  ["muted", "surface-2", 4.5, "muted text on tinted rows"],
  ["accent", "surface", 4.5, "links / accent text"],
  ["accent", "accent-soft", 4.5, "active nav, medium confidence"],
  ["accent-ink", "accent", 4.5, "primary buttons, high confidence"],
  ["ok", "surface", 3, "pass icon"],
  ["warn", "surface", 3, "caveat icon"],
  ["fail", "surface", 4.5, "error text"],
  ["level-yellow-ink", "level-yellow", 4.5, "Jaune badge, test-data banner"],
  ["level-orange-ink", "level-orange", 4.5, "Orange badge"],
  ["level-red-ink", "level-red", 4.5, "Rouge badge"],
  ["line-strong", "surface", 3, "input borders (non-text)"],
  ["series-1", "surface", 3, "chart series 1"],
  ["series-2", "surface", 3, "chart series 2"],
  ["focus", "surface", 3, "focus ring"],
];

let failed = 0;
for (const [fg, bg, min, what] of pairs) {
  const r = ratio(token(fg), token(bg));
  const ok = r >= min;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${r.toFixed(2).padStart(5)} ≥ ${min}  --${fg} on --${bg}  (${what})`);
}
// White on ink (limits block)
const w = ratio("#ffffff", token("ink"));
console.log(`${w >= 4.5 ? "PASS" : "FAIL"}  ${w.toFixed(2).padStart(5)} ≥ 4.5  #fff on --ink  (limits block)`);
if (w < 4.5) failed++;
process.exit(failed ? 1 : 0);
