import type { StyleSpecification } from "maplibre-gl";
export const mapStyle: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    earth: {
      type: "vector",
      url: "https://tiles.openfreemap.org/planet",
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · <a href="https://openfreemap.org">OpenFreeMap</a>',
    },
  },
  layers: [
    {
      id: "land",
      type: "background",
      paint: {
        "background-color": [
          "interpolate",
          ["linear"],
          ["zoom"],
          0,
          "#26443e",
          4,
          "#1a2b2b",
          8,
          "#142025",
        ],
      },
    },
    {
      id: "water",
      type: "fill",
      source: "earth",
      "source-layer": "water",
      paint: { "fill-color": "#08131e", "fill-antialias": true },
    },
    {
      id: "forest",
      type: "fill",
      source: "earth",
      "source-layer": "landcover",
      minzoom: 5,
      filter: ["==", "class", "wood"],
      paint: { "fill-color": "#1e3b32", "fill-opacity": 0.4 },
    },
    {
      id: "waterways",
      type: "line",
      source: "earth",
      "source-layer": "waterway",
      minzoom: 6,
      paint: { "line-color": "#274756", "line-width": 0.7 },
    },
    {
      id: "boundaries",
      type: "line",
      source: "earth",
      "source-layer": "boundary",
      filter: ["<=", "admin_level", 2],
      paint: {
        "line-color": "#779488",
        "line-width": 0.6,
        "line-opacity": 0.4,
      },
    },
    {
      id: "roads",
      type: "line",
      source: "earth",
      "source-layer": "transportation",
      minzoom: 7,
      paint: {
        "line-color": "#53605f",
        "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.3, 14, 1.5],
        "line-opacity": 0.35,
      },
    },
    {
      id: "labels",
      type: "symbol",
      source: "earth",
      "source-layer": "place",
      layout: {
        "text-field": ["coalesce", ["get", "name:en"], ["get", "name"]],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 1, 10, 8, 12],
        "text-transform": "uppercase",
        "text-letter-spacing": 0.15,
      },
      paint: {
        "text-color": "#9eb2b0",
        "text-halo-color": "#08131e",
        "text-halo-width": 2,
        "text-opacity": 0.7,
      },
    },
  ],
};
