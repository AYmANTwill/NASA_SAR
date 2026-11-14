import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** WCAG 2.x contrast of the token pairs actually used for text and marks. Vitest runs from frontend-v2/. */
const css = readFileSync(join(process.cwd(), "src/styles/tokens.css"), "utf8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!match?.[1]) throw new Error(`token --${name} is not a 6-digit hex colour`);
  return match[1];
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

describe("token contrast (WCAG AA)", () => {
  it.each([
    ["ink", "paper", 4.5],
    ["ink", "sheet", 4.5],
    ["ink-2", "paper", 4.5],
    ["ink-2", "sheet", 4.5],
    ["sheet", "ink", 4.5],
  ])("%s on %s ≥ %s:1", (fg, bg, min) => {
    expect(contrast(token(fg), token(bg))).toBeGreaterThanOrEqual(min);
  });

  it("the focus ring (ink) stands out from both grounds as a non-text mark (≥ 3:1)", () => {
    expect(contrast(token("ink"), token("paper"))).toBeGreaterThanOrEqual(3);
  });
});
