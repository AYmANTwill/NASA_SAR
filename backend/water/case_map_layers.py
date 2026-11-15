"""Map layers for the bin-el-ouidane-2026 case: before mask, after mask, change (only what the case map needs).

RGBA PNG, north-up, reprojected to EPSG:4326, bounds = [west, south, east, north] of the pixel outer edges,
transparent = no data. Writes outputs/rasters/{water_before,water_after,water_change}.png + outputs/raster_index.json.
Usage: python case_map_layers.py
"""
from __future__ import annotations

import json

import numpy as np
from PIL import Image

from common import BIG_OUT, OUTPUTS
from output_assets import warp

RASTERS = OUTPUTS / "rasters"


def main() -> None:
    pair = json.loads((OUTPUTS / "change_pair.json").read_text())
    RASTERS.mkdir(parents=True, exist_ok=True)
    for old in RASTERS.glob("*.png"):
        old.unlink()
    layers = []
    for src, name, date, colors, legend in (
            ("water_pre.tif", "water_before", {"date": pair["pre"]["date"]}, {1: (38, 132, 255, 170)}, {"water": "#2684ff"}),
            ("water_post.tif", "water_after", {"date": pair["post"]["date"]}, {1: (38, 132, 255, 170)}, {"water": "#2684ff"}),
            ("change.tif", "water_change", {"period": {"start": pair["pre"]["date"], "end": pair["post"]["date"]}},
             {1: (31, 119, 180, 200), 2: (214, 39, 40, 200)}, {"gain": "#1f77b4", "loss": "#d62728"})):
        a, _, bounds = warp(BIG_OUT / src)
        rgba = np.zeros(a.shape + (4,), np.uint8)
        for k, c in colors.items():
            rgba[a == k] = c
        Image.fromarray(rgba, "RGBA").save(RASTERS / f"{name}.png", optimize=True)
        layers.append({"id": name, "file": f"rasters/{name}.png", "url": f"water/outputs/rasters/{name}.png",
                       "bounds": [round(v, 6) for v in bounds], **date, "legend": legend,
                       "source": f"NISAR GCOV, Water U-Net ({pair['method']})"})
    # Same-period optical backgrounds (HLS scene of the matched DSWx map): the web map's own basemap is an old
    # mosaic (drought-time lake) and would make correct water look like it covers land; show these under the water.
    from output_assets import hls_rgb
    for when, key in (("before", "pre"), ("after", "post")):
        h = hls_rgb(pair[key]["tag"])
        if h is None:
            continue
        rgb, hb, label = h
        name = f"optical_{when}"
        alpha = np.where(rgb.sum(2) > 0, 255, 0).astype(np.uint8)
        Image.fromarray(np.dstack([(rgb * 255).astype(np.uint8), alpha]), "RGBA").save(RASTERS / f"{name}.png", optimize=True)
        layers.append({"id": name, "file": f"rasters/{name}.png", "url": f"water/outputs/rasters/{name}.png",
                       "bounds": [round(v, 6) for v in hb], "date": pair[key]["date"], "role": "background",
                       "legend": {}, "source": f"{label} true colour (the acquisition the matched DSWx map was computed "
                                             "from); show it under the water layers instead of the default basemap"})
    (OUTPUTS / "raster_index.json").write_text(json.dumps({
        "case_id": "bin-el-ouidane-2026", "crs": "EPSG:4326", "bounds_order": "[west, south, east, north], pixel outer edges",
        "format": "RGBA PNG, north-up, transparent = no data", "layers": layers}, indent=2), encoding="utf-8")
    print("layers:", [l["id"] for l in layers], "sizes kB:", [round((RASTERS / f"{l['id']}.png").stat().st_size / 1e3) for l in layers])


if __name__ == "__main__":
    main()
