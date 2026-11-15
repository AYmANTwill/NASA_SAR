import type { Palette } from "@/api/contract";
import palettes from "@/design/palettes.json";

/**
 * The canonical palettes (backend/palettes.json, copied verbatim and checked by
 * contract.sync.test.ts). The backend renders every raster PNG with these stops,
 * linearly from min to max, so the legend drawn from them matches the pixels.
 */
export function paletteStops(palette: Palette): string[] {
  const stops = (palettes as Record<string, unknown>)[palette];
  if (!Array.isArray(stops) || stops.length < 2) throw new Error(`palette ${palette} missing from palettes.json`);
  return stops as string[];
}

/** CSS gradient of a palette, left (min) to right (max). */
export function paletteGradient(palette: Palette): string {
  return `linear-gradient(to right, ${paletteStops(palette).join(", ")})`;
}
