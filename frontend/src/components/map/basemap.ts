import type { StyleSpecification, ExpressionSpecification } from "maplibre-gl";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import countriesTopo from "world-atlas/countries-50m.json";
import type { Lang } from "@/api/contract";

const topo = countriesTopo as unknown as Topology<{ countries: GeometryCollection; land: GeometryCollection }>;
const land = feature(topo, topo.objects.land);
const borders = mesh(topo, topo.objects.countries, (a, b) => a !== b);

const OPENFREEMAP = "https://tiles.openfreemap.org/planet";
const GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";

export const COLORS = {
  ocean: "#d9e3e9",
  land: "#f5f6f3",
  coast: "#aebbc3",
  border: "#7d8b95",
  water: "#d9e3e9",
  road: "#ffffff",
  roadCase: "#cfd6db",
  label: "#3c4a56",
  halo: "#f5f6f3",
};

/** Map labels: Latin-script names (Arabic shaping needs a plugin that is not bundled). */
function labelField(lang: Lang): ExpressionSpecification {
  const order = lang === "en" ? ["name:en", "name:latin", "name:fr", "name"] : ["name:fr", "name:latin", "name:en", "name"];
  return ["coalesce", ...order.map((k) => ["get", k] as ExpressionSpecification)] as ExpressionSpecification;
}

/**
 * Local land and borders (world-atlas, bundled) always render, so the map
 * works offline. OpenFreeMap vector detail is added only when online.
 */
export function buildStyle(lang: Lang, online: boolean): StyleSpecification {
  const style: StyleSpecification = {
    version: 8,
    sources: {
      land: { type: "geojson", data: land, attribution: "Natural Earth" },
      borders: { type: "geojson", data: borders },
    },
    layers: [
      { id: "ocean", type: "background", paint: { "background-color": COLORS.ocean } },
      { id: "land", type: "fill", source: "land", paint: { "fill-color": COLORS.land } },
      { id: "coast", type: "line", source: "land", paint: { "line-color": COLORS.coast, "line-width": 0.6 } },
    ],
  };

  if (online) {
    style.glyphs = GLYPHS;
    style.sources.omt = {
      type: "vector",
      url: OPENFREEMAP,
      attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    };
    style.layers.push(
      { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": COLORS.water } },
      { id: "waterway", type: "line", source: "omt", "source-layer": "waterway", minzoom: 7, paint: { "line-color": COLORS.water, "line-width": 1 } },
      {
        id: "roads-case", type: "line", source: "omt", "source-layer": "transportation", minzoom: 6,
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]],
        paint: { "line-color": COLORS.roadCase, "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1, 12, 4] },
      },
      {
        id: "roads", type: "line", source: "omt", "source-layer": "transportation", minzoom: 6,
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]],
        paint: { "line-color": COLORS.road, "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.5, 12, 2.5] },
      },
    );
  }

  style.layers.push({ id: "borders", type: "line", source: "borders", paint: { "line-color": COLORS.border, "line-width": 0.8, "line-dasharray": [3, 2] } });

  if (online) {
    style.layers.push({
      id: "places", type: "symbol", source: "omt", "source-layer": "place", minzoom: 5,
      filter: ["in", ["get", "class"], ["literal", ["city", "town", "village"]]],
      layout: {
        "text-field": labelField(lang),
        "text-font": ["Noto Sans Regular"],
        "text-size": ["match", ["get", "class"], "city", 13, "town", 12, 11],
      },
      paint: { "text-color": COLORS.label, "text-halo-color": COLORS.halo, "text-halo-width": 1.4 },
    });
  }
  return style;
}

/** Ids of layers that carry place labels, re-localized on language change. */
export const LABEL_LAYERS = ["places"];
export { labelField };
