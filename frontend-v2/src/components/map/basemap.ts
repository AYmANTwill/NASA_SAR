import type { FeatureCollection, Geometry, MultiLineString } from "geojson";
import type { StyleSpecification } from "maplibre-gl";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

export interface Basemap {
  land: FeatureCollection;
  borders: MultiLineString;
}

let cache: Promise<Basemap> | null = null;

/** Natural Earth 1:50m land and country borders (world-atlas), bundled: the map works offline. */
export function loadBasemap(): Promise<Basemap> {
  cache ??= import("world-atlas/countries-50m.json").then((module) => {
    const topo = (module.default ?? module) as unknown as Topology<{ countries: GeometryCollection; land: GeometryCollection }>;
    const land = feature(topo, topo.objects.land) as unknown as FeatureCollection;
    const borders = mesh(topo, topo.objects.countries, (a, b) => a !== b);
    for (const f of land.features) unwrapGeometry(f.geometry);
    borders.coordinates.forEach(unwrapLine);
    return { land, borders };
  });
  return cache;
}

/**
 * Rings that cross the antimeridian jump from +180 to -180; drawn as is, they
 * paint a band across the whole map. Making each line continuous (longitudes
 * beyond ±180) lets MapLibre's world copies draw them correctly.
 */
function unwrapLine(line: number[][]): void {
  let offset = 0;
  for (let i = 1; i < line.length; i++) {
    const point = line[i]!;
    const previous = line[i - 1]!;
    const jump = point[0]! + offset - previous[0]!;
    if (jump > 180) offset -= 360;
    else if (jump < -180) offset += 360;
    point[0] = point[0]! + offset;
  }
}

function unwrapGeometry(geometry: Geometry): void {
  if (geometry.type === "Polygon") geometry.coordinates.forEach(unwrapLine);
  else if (geometry.type === "MultiPolygon") geometry.coordinates.forEach((polygon) => polygon.forEach(unwrapLine));
}

/** Colours read from the design tokens, so the basemap stays in the hue-less chrome. */
function token(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** A grey, label-free basemap: the radar raster is the only colour on the map. */
export function basemapStyle(basemap: Basemap): StyleSpecification {
  return {
    version: 8,
    sources: {
      land: { type: "geojson", data: basemap.land, attribution: "Natural Earth" },
      borders: { type: "geojson", data: { type: "Feature", properties: {}, geometry: basemap.borders } },
    },
    layers: [
      { id: "sea", type: "background", paint: { "background-color": token("--sea", "#e9ecee") } },
      { id: "land", type: "fill", source: "land", paint: { "fill-color": token("--land", "#fbfbfb") } },
      { id: "coast", type: "line", source: "land", paint: { "line-color": token("--coast", "#a9b2b8"), "line-width": 0.8 } },
      {
        id: "borders",
        type: "line",
        source: "borders",
        paint: { "line-color": token("--coast", "#a9b2b8"), "line-width": 0.8, "line-dasharray": [3, 2] },
      },
    ],
  };
}
