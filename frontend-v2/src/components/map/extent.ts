import type { Bounds } from "@/api/contract";
import type { Ring } from "./land";

export interface View {
  west: number;
  south: number;
  east: number;
  north: number;
  width: number;
  height: number;
}

/**
 * The frame of a locator thumbnail: the case's bbox (from the API) widened to
 * show its surroundings and fitted to the thumbnail's aspect ratio.
 * Display geometry only: no value derived here is ever shown as data.
 */
export function locatorView(bbox: Bounds, width: number, height: number, context = 5, minSpanDeg = 6): View {
  const [w, s, e, n] = bbox;
  const cx = (w + e) / 2;
  const cy = (s + n) / 2;
  const kx = Math.cos((cy * Math.PI) / 180) || 1;
  // Work in "ground" degrees (longitude scaled by cos(lat)) so the frame is not stretched.
  let spanX = Math.max((e - w) * kx * context, minSpanDeg);
  let spanY = Math.max((n - s) * context, minSpanDeg * (height / width));
  if (spanX / spanY > width / height) spanY = spanX * (height / width);
  else spanX = spanY * (width / height);
  const halfLon = spanX / kx / 2;
  const halfLat = spanY / 2;
  return {
    west: cx - halfLon,
    east: cx + halfLon,
    south: Math.max(cy - halfLat, -85),
    north: Math.min(cy + halfLat, 85),
    width,
    height,
  };
}

export function project(view: View, lon: number, lat: number): [number, number] {
  const x = ((lon - view.west) / (view.east - view.west)) * view.width;
  const y = ((view.north - lat) / (view.north - view.south)) * view.height;
  return [x, y];
}

function ringIntersects(view: View, ring: Ring): boolean {
  let w = Infinity;
  let e = -Infinity;
  let s = Infinity;
  let n = -Infinity;
  for (const [lon = 0, lat = 0] of ring) {
    if (lon < w) w = lon;
    if (lon > e) e = lon;
    if (lat < s) s = lat;
    if (lat > n) n = lat;
  }
  return !(e < view.west || w > view.east || n < view.south || s > view.north);
}

/** SVG path of the land rings that touch the view (the SVG viewport clips the rest). */
export function landPath(view: View, rings: Ring[]): string {
  const parts: string[] = [];
  for (const ring of rings) {
    if (!ringIntersects(view, ring)) continue;
    let d = "";
    ring.forEach(([lon = 0, lat = 0], i) => {
      const [x, y] = project(view, lon, lat);
      d += `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    parts.push(d + "Z");
  }
  return parts.join("");
}
