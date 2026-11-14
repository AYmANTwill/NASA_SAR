import type { FeatureCollection, MultiLineString } from "geojson";
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
    return {
      land: feature(topo, topo.objects.land) as unknown as FeatureCollection,
      borders: mesh(topo, topo.objects.countries, (a, b) => a !== b),
    };
  });
  return cache;
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
