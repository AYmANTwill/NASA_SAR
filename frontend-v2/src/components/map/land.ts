import type { MultiPolygon, Polygon, Position } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

export type Ring = Position[];

let cache: Promise<Ring[]> | null = null;

/**
 * Natural Earth land (1:50m, from world-atlas), bundled so the map works
 * offline. Loaded on first use, from the same chunk as the map's basemap.
 */
export function loadLand(): Promise<Ring[]> {
  cache ??= import("world-atlas/countries-50m.json").then((module) => {
    const topo = (module.default ?? module) as unknown as Topology<{ land: GeometryCollection }>;
    const land = feature(topo, topo.objects.land);
    const rings: Ring[] = [];
    for (const f of land.features) {
      const g = f.geometry as Polygon | MultiPolygon;
      const polygons = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
      for (const polygon of polygons) rings.push(...polygon);
    }
    return rings;
  });
  return cache;
}
