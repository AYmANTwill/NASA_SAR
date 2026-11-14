import palettes from "@/design/palettes.json";
import type { Palette } from "@/api/contract";

export const PALETTES = palettes as unknown as Record<Palette, string[]>;

/** CSS gradient for a legend bar (always drawn left→right, low→high). */
export function gradient(palette: Palette): string {
  const stops = PALETTES[palette];
  return `linear-gradient(to right, ${stops.map((c, i) => `${c} ${(i / (stops.length - 1)) * 100}%`).join(", ")})`;
}

export const isDiverging = (palette: Palette) => palette.startsWith("diverging");
