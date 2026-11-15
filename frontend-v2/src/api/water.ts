import { z } from "zod";
import { Bounds } from "./contract";

/** Optional image endpoint, independent of RasterLayer: no palette or scientific legend is inferred. */
export const WaterRasterIndex = z.object({
  case_id: z.literal("bin-el-ouidane-2026"),
  crs: z.literal("EPSG:4326"),
  layers: z.array(z.object({
    id: z.enum(["water_before", "water_after", "water_change"]),
    url: z.string().regex(/^\/api\/water\/rasters\/[A-Za-z0-9_-]+\.png$/),
    bounds: Bounds.refine(([w, s, e, n]) => [w, s, e, n].every(Number.isFinite) && w >= -180 && e <= 180 && s >= -90 && n <= 90 && w < e && s < n,
      "expected [west, south, east, north] bounds"),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
    period: z.object({ start: z.string().regex(/^\d{4}-\d{2}-\d{2}$/), end: z.string().regex(/^\d{4}-\d{2}-\d{2}$/) }).optional(),
    source: z.string().optional(),
  })),
});
export type WaterRasterIndex = z.infer<typeof WaterRasterIndex>;
