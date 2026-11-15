"""Step 2: find NISAR GCOV dates over a Moroccan reservoir + matching OPERA DSWx-HLS.

Search only (public CMR + OpenStreetMap Overpass); no Earthdata login and no data downloads.
The only files fetched are public DSWx BROWSE PNGs (a few hundred KB) for the AOI quicklook.

Usage:  python src/nisar_search.py [--reservoir Al_Massira] [--all]
Outputs: outputs/aoi.json, outputs/candidate_scenes.csv, outputs/aoi_dswx_quicklook.png
"""
from __future__ import annotations

import argparse
import io
import json
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

from common import OUTPUTS, RESERVOIRS

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
# Real collection short names, verified in CMR on 2026-11-14 (preference order: V1 > provisional > beta).
GCOV_COLLECTIONS = ["NISAR_L2_GCOV_V1", "NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_BETA_V1"]
DSWX = "OPERA_L3_DSWX-HLS_V1"
NISAR_START = "2025-07-30T00:00:00Z"  # NISAR launch; science products start Oct 2025
BUFFER_DEG = 0.02  # ~2 km buffer around the OSM shoreline extent
UA = {"User-Agent": "space-apps-sar-research"}


# ---------------------------------------------------------------- AOI
def derive_aoi(name: str) -> dict:
    """Largest non-river OSM water body near the approximate centre -> bbox + buffer."""
    lat, lon = RESERVOIRS[name]
    s, w, n, e = lat - 0.3, lon - 0.4, lat + 0.3, lon + 0.4
    q = (f'[out:json][timeout:60];(way["natural"="water"]({s},{w},{n},{e});'
         f'relation["natural"="water"]({s},{w},{n},{e}););out bb tags;')
    cache = OUTPUTS / f"osm_water_{name}.json"
    if cache.exists():
        elements = json.loads(cache.read_text())
    else:
        elements, err = None, None
        for attempt in range(3):
            for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
                try:
                    r = requests.post(url, data={"data": q}, headers=UA, timeout=120)
                    r.raise_for_status()
                    elements = r.json()["elements"]
                    break
                except Exception as e:  # transient 502/504 are common on Overpass
                    err = e
                    time.sleep(5 * (attempt + 1))
            if elements is not None:
                break
        if elements is None:
            raise RuntimeError(f"Overpass failed: {err}")
        # cache only the small bbox/tags records (no geometry)
        elements = [{k: el[k] for k in ("type", "id", "bounds", "tags") if k in el} for el in elements]
        cache.write_text(json.dumps(elements))
    best = None
    for el in elements:
        b, tags = el.get("bounds"), el.get("tags", {})
        if not b or tags.get("water") in ("river", "stream", "canal"):
            continue
        area = (b["maxlat"] - b["minlat"]) * (b["maxlon"] - b["minlon"])
        if best is None or area > best[0]:
            best = (area, el, b, tags)
    if best is None:
        raise RuntimeError(f"No OSM water body found near {name}")
    _, el, b, tags = best
    bbox = [round(b["minlon"] - BUFFER_DEG, 4), round(b["minlat"] - BUFFER_DEG, 4),
            round(b["maxlon"] + BUFFER_DEG, 4), round(b["maxlat"] + BUFFER_DEG, 4)]
    return {"reservoir": name, "osm": f"{el['type']}/{el['id']}", "osm_name": tags.get("name"),
            "osm_bounds": [b["minlon"], b["minlat"], b["maxlon"], b["maxlat"]],
            "buffer_deg": BUFFER_DEG, "bbox": bbox}


# ---------------------------------------------------------------- CMR helpers
def cmr_all(params: dict) -> list[dict]:
    items, headers = [], dict(UA)
    while True:
        r = requests.get(CMR, params={**params, "page_size": 2000}, headers=headers, timeout=120)
        r.raise_for_status()
        batch = r.json()["items"]
        items += batch
        sa = r.headers.get("CMR-Search-After")
        if not batch or not sa:
            return items
        headers["CMR-Search-After"] = sa


def attrs(umm: dict) -> dict:
    return {a["Name"]: a["Values"][0] if len(a["Values"]) == 1 else a["Values"]
            for a in umm.get("AdditionalAttributes", [])}


def footprint(umm: dict):
    from shapely.geometry import Polygon, box

    geo = umm["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]
    if "GPolygons" in geo:
        pts = geo["GPolygons"][0]["Boundary"]["Points"]
        return Polygon([(p["Longitude"], p["Latitude"]) for p in pts])
    r = geo["BoundingRectangles"][0]
    return box(r["WestBoundingCoordinate"], r["SouthBoundingCoordinate"],
               r["EastBoundingCoordinate"], r["NorthBoundingCoordinate"])


def url_of(umm: dict, kind: str, suffix: str) -> str | None:
    for u in umm.get("RelatedUrls", []):
        if u["Type"] == kind and u["URL"].startswith("https") and u["URL"].endswith(suffix):
            return u["URL"]
    return None


def size_mb(umm: dict, suffix: str) -> float | None:
    for f in umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", []):
        if f.get("Name", "").endswith(suffix) and f.get("Size") is not None:
            return round(f["Size"] * {"KB": 1e-3, "MB": 1, "GB": 1e3}.get(f.get("SizeUnit", "MB"), 1), 3)
    return None


# ---------------------------------------------------------------- NISAR
def search_nisar(bbox: list[float]) -> pd.DataFrame:
    from shapely.geometry import box

    aoi = box(*bbox)
    rows = []
    for coll in GCOV_COLLECTIONS:
        for it in cmr_all({"short_name": coll, "bounding_box": ",".join(map(str, bbox)),
                           "temporal": f"{NISAR_START},", "sort_key": "start_date"}):
            u = it["umm"]
            a = attrs(u)
            t0 = u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
            pols = a.get("FREQUENCY_A_POLARIZATION", [])
            pols = [pols] if isinstance(pols, str) else pols
            rows.append({
                "collection": coll,
                "granule": u["GranuleUR"],
                "datetime": t0,
                "date": t0[:10],
                "track": int(a.get("TRACK_NUMBER", -1)),
                "frame": int(a.get("FRAME_NUMBER", -1)),
                "direction": a.get("ASCENDING_DESCENDING", ""),
                "stack_id": a.get("STACK_ID", ""),
                "product_version": a.get("PRODUCT_VERSION", ""),
                "freqA_pols": "+".join(pols),
                "has_HH_HV": "HH" in pols and "HV" in pols,
                "aoi_coverage": round(footprint(u).intersection(aoi).area / aoi.area, 3),
                "h5_size_mb": size_mb(u, ".h5"),  # CMR currently has no size for NISAR files
                "h5_url": url_of(u, "GET DATA", ".h5"),
                "browse_url": url_of(u, "GET RELATED VISUALIZATION", "_LATLON.png"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # The same acquisition can appear in several collections (reprocessing): keep the preferred one.
    df["pref"] = df["collection"].map({c: i for i, c in enumerate(GCOV_COLLECTIONS)})
    df = (df.sort_values(["pref", "granule"], ascending=[True, False])
            .drop_duplicates(["datetime", "track", "frame"]).drop(columns="pref"))
    df["usable"] = df["has_HH_HV"] & (df["aoi_coverage"] >= 0.9)
    return df.sort_values("datetime").reset_index(drop=True)


# ---------------------------------------------------------------- DSWx
def search_dswx(bbox: list[float], start: str, end: str) -> pd.DataFrame:
    from shapely.geometry import box

    aoi = box(*bbox)
    rows = []
    for it in cmr_all({"short_name": DSWX, "bounding_box": ",".join(map(str, bbox)),
                       "temporal": f"{start},{end}", "sort_key": "start_date"}):
        u = it["umm"]
        a = attrs(u)
        g = u["GranuleUR"]  # OPERA_L3_DSWx-HLS_T29SPS_<acq>Z_<prod>Z_<sensor>_30_v1.1
        parts = g.split("_")
        rows.append({
            "granule": g, "tile": parts[3], "acq": parts[4], "prod": parts[5], "sensor": parts[6],
            "date": datetime.strptime(parts[4][:8], "%Y%m%d").date(),
            "cloud_pct": float(a.get("CloudCoverage", "nan")),
            "aoi_part": footprint(u).intersection(aoi).area / aoi.area,
            "wtr_size_mb": size_mb(u, "_B01_WTR.tif"),
            "wtr_url": url_of(u, "GET DATA", "_B01_WTR.tif"),
            "browse_url": url_of(u, "GET RELATED VISUALIZATION", "_BROWSE.png"),
            "poly": footprint(u),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # keep latest reprocessing of each (tile, acquisition)
    return df.sort_values("prod").drop_duplicates(["tile", "acq"], keep="last").reset_index(drop=True)


def utm_of(bbox) -> str:
    lon0 = (bbox[0] + bbox[2]) / 2
    return f"EPSG:{32600 + int((lon0 + 180) // 6) + 1}"


def utm_box(bbox, utm, margin: float = 0.0):
    from rasterio.warp import transform as rtransform

    xs, ys = rtransform("EPSG:4326", utm, [bbox[0], bbox[2], bbox[2], bbox[0]], [bbox[1], bbox[1], bbox[3], bbox[3]])
    return min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin


_BROWSE: dict[str, np.ndarray] = {}  # in-memory cache only (nothing written to disk)


def _browse(url: str) -> np.ndarray:
    from PIL import Image

    if url not in _BROWSE:
        for attempt in range(4):
            try:
                r = requests.get(url, headers=UA, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(10 * (attempt + 1))
        _BROWSE[url] = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGBA"))
    return _BROWSE[url]


def sample_browse(urls, polys, utm, xmin, xmax, ymin, ymax, res=100.0) -> np.ndarray:
    """Nearest-neighbour mosaic of DSWx BROWSE PNGs onto a UTM grid (RGBA, alpha 0 = no data).

    HLS/Sentinel-2 MGRS tiles are 109.8 km squares whose upper-left corner sits on the 100 km UTM
    grid. CMR only gives a lat/lon envelope, so it is used just to find the tile centre.
    """
    from rasterio.warp import transform as rtransform

    xs = np.arange(xmin + res / 2, xmax, res)
    ys = np.arange(ymax - res / 2, ymin, -res)
    X, Y = np.meshgrid(xs, ys)
    out = np.zeros(X.shape + (4,), np.uint8)
    for url, poly in zip(urls, polys):
        img = _browse(url)
        c = poly.centroid
        (cx,), (cy,) = rtransform("EPSG:4326", utm, [c.x], [c.y])
        x0, ytop = np.floor(cx / 1e5) * 1e5, np.floor(cy / 1e5) * 1e5 + 1e5
        h, w = img.shape[:2]
        col = ((X - x0) / 109800 * w).astype(int)
        row = ((ytop - Y) / 109800 * h).astype(int)
        inside = (col >= 0) & (col < w) & (row >= 0) & (row < h)
        vals = np.zeros_like(out)
        vals[inside] = img[row[inside], col[inside]]
        take = (vals[..., 3] > 0) & (out[..., 3] == 0)
        out[take] = vals[take]
    return out


# DSWx browse palette (observed): white = not water, (0,0,255) = open water, (180,213,244) = partial
# surface water, transparent = no data / masked. Any other colour is treated as masked.
def browse_classes(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rgb, a = rgba[..., :3].astype(int), rgba[..., 3]
    water = (a > 0) & (np.all(rgb == (0, 0, 255), -1) | np.all(rgb == (180, 213, 244), -1))
    land = (a > 0) & np.all(rgb == (255, 255, 255), -1)
    return water, water | land


def dswx_acquisitions(dswx: pd.DataFrame, bbox, res: float = 100.0) -> pd.DataFrame:
    """Group tiles of one overpass (same date + sensor) and measure, from the public browse PNGs,
    how much of the AOI actually has valid DSWx data (tile envelopes and tile cloud % are not enough:
    Landsat swath edges and clouds leave the reservoir uncovered)."""
    utm = utm_of(bbox)
    xmin, xmax, ymin, ymax = utm_box(bbox, utm)
    out = []
    for (d, sensor), g in dswx.groupby(["date", "sensor"]):
        g = g[g["browse_url"].notna()]
        if g.empty:
            continue
        rgba = sample_browse(list(g["browse_url"]), list(g["poly"]), utm, xmin, xmax, ymin, ymax, res)
        water, valid = browse_classes(rgba)
        out.append({"dswx_date": d, "sensor": sensor, "tiles": "+".join(sorted(g["tile"])),
                    "dswx_cloud_max_pct": g["cloud_pct"].max(),
                    "dswx_aoi_valid_frac": round(float(valid.mean()), 3),
                    "dswx_water_km2_browse": round(float(water.sum()) * res * res / 1e6, 1),
                    "dswx_wtr_size_mb": round(g["wtr_size_mb"].fillna(0).sum(), 3),
                    "dswx_granules": ";".join(g["granule"]), "wtr_urls": ";".join(g["wtr_url"].fillna("")),
                    "browse_urls": ";".join(g["browse_url"]), "polys": list(g["poly"])})
    return pd.DataFrame(out)


def match_dswx(nisar: pd.DataFrame, acq: pd.DataFrame, max_days: int = 5, min_valid: float = 0.9) -> pd.DataFrame:
    cols = ["dswx_date", "dswx_delta_days", "sensor", "tiles", "dswx_aoi_valid_frac", "dswx_water_km2_browse",
            "dswx_cloud_max_pct", "dswx_wtr_size_mb", "dswx_granules", "wtr_urls"]
    matches = []
    for _, r in nisar.iterrows():
        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        c = acq.copy()
        c["dswx_delta_days"] = [(x - d).days for x in c["dswx_date"]]
        c = c[(c["dswx_delta_days"].abs() <= max_days) & (c["dswx_aoi_valid_frac"] >= min_valid)]
        if c.empty:
            matches.append({k: ("none" if k == "dswx_date" else None) for k in cols})
            continue
        # closest in time first, then most valid AOI pixels
        c = c.assign(score=c["dswx_delta_days"].abs() - c["dswx_aoi_valid_frac"])
        matches.append(c.sort_values("score").iloc[0][cols].to_dict())
    return pd.concat([nisar.reset_index(drop=True), pd.DataFrame(matches)], axis=1)


# ---------------------------------------------------------------- quicklook
def quicklook(acq_row: pd.Series, aoi_info: dict, out_png) -> None:
    """DSWx browse (georeferenced on the MGRS grid) around the AOI, with the AOI and OSM boxes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from rasterio.warp import transform as rtransform

    bbox = aoi_info["bbox"]
    utm = utm_of(bbox)
    xmin, xmax, ymin, ymax = utm_box(bbox, utm, margin=8000)
    rgba = sample_browse(acq_row["browse_urls"].split(";"), acq_row["polys"], utm, xmin, xmax, ymin, ymax, 50.0)
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.set_facecolor("#bbbbbb")  # grey = no data / masked in DSWx
    ax.imshow(rgba, extent=[xmin, xmax, ymin, ymax], interpolation="nearest")
    for b, style, lab in [(aoi_info["bbox"], "r-", "AOI bbox (with buffer)"),
                          (aoi_info["osm_bounds"], "y--", "OSM reservoir extent")]:
        bx, by = rtransform("EPSG:4326", utm, [b[0], b[2], b[2], b[0], b[0]], [b[1], b[1], b[3], b[3], b[1]])
        ax.plot(bx, by, style, lw=2, label=lab)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_title(f"{aoi_info['reservoir']}: DSWx-HLS browse {acq_row['dswx_date']} ({acq_row['sensor']}, tiles "
                 f"{acq_row['tiles']}); AOI valid {acq_row['dswx_aoi_valid_frac']:.0%}, "
                 f"water ≈ {acq_row['dswx_water_km2_browse']} km² (coarse browse)\n"
                 "blue = water (DSWx classes 1-2), white = not water, grey = no data/masked", fontsize=8)
    ax.set_xlabel(f"{utm} easting (m)")
    ax.set_ylabel("northing (m)")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------- main
def run(name: str) -> pd.DataFrame:
    from shapely.geometry import box

    aoi_info = derive_aoi(name)
    print(f"[{name}] OSM {aoi_info['osm']} '{aoi_info['osm_name']}' bbox={aoi_info['bbox']}")
    nisar = search_nisar(aoi_info["bbox"])
    print(f"[{name}] NISAR GCOV granules: {len(nisar)}")
    if nisar.empty:
        return nisar.assign(reservoir=name), aoi_info, None
    t0 = (datetime.strptime(nisar["date"].min(), "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%dT00:00:00Z")
    t1 = (datetime.strptime(nisar["date"].max(), "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%dT23:59:59Z")
    dswx = search_dswx(aoi_info["bbox"], t0, t1)
    acq = dswx_acquisitions(dswx, aoi_info["bbox"]) if not dswx.empty else pd.DataFrame()
    nval = int((acq["dswx_aoi_valid_frac"] >= 0.9).sum()) if len(acq) else 0
    print(f"[{name}] DSWx granules: {len(dswx)}, acquisitions: {len(acq)}, with >=90% valid AOI: {nval}")
    if len(acq):
        acq.drop(columns=["polys"]).to_csv(OUTPUTS / f"dswx_acquisitions_{name}.csv", index=False)
    df = match_dswx(nisar, acq) if not acq.empty else nisar.assign(dswx_date="none")
    df.insert(0, "reservoir", name)
    return df, aoi_info, acq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reservoir", default=None, help="one of " + ", ".join(RESERVOIRS))
    ap.add_argument("--all", action="store_true", help="search all three reservoirs")
    args = ap.parse_args()
    names = list(RESERVOIRS) if args.all else [args.reservoir] if args.reservoir else list(RESERVOIRS)

    frames, aois, chosen = [], {}, None
    for name in names:
        df, aoi_info, acq = run(name)
        aois[name] = aoi_info
        frames.append(df)
        if df.empty:
            continue
        u = df[df["usable"]]
        groups = u.groupby(["track", "frame", "direction"]).size().sort_values(ascending=False)
        print(f"[{name}] usable dates per (track, frame, direction):\n{groups.to_string() if len(groups) else '  none'}")
        if chosen is None and len(groups) and groups.iloc[0] >= 2:
            chosen = (name, groups.index[0], acq)
            if not args.all:
                break  # backups only searched when the main target is not usable

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not out.empty:
        out["same_track_group"] = False
        if chosen:
            name, (trk, frm, dirn), _ = chosen
            out.loc[(out["reservoir"] == name) & (out["track"] == trk) & (out["frame"] == frm)
                    & (out["direction"] == dirn) & out["usable"], "same_track_group"] = True
    out.to_csv(OUTPUTS / "candidate_scenes.csv", index=False)
    meta = {"aois": aois, "chosen": None}
    if chosen:
        meta["chosen"] = {"reservoir": chosen[0], "track": int(chosen[1][0]), "frame": int(chosen[1][1]),
                          "direction": chosen[1][2]}
    (OUTPUTS / "aoi.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"wrote {OUTPUTS/'candidate_scenes.csv'} ({len(out)} rows)")

    if not chosen:
        print("STOP: no reservoir has >= 2 usable same-track NISAR dates.")
        return
    name, _, acq = chosen
    # Quicklook from the DSWx acquisition with the most valid AOI pixels (ties: largest water area)
    best = acq.sort_values(["dswx_aoi_valid_frac", "dswx_water_km2_browse"], ascending=False).iloc[0]
    quicklook(best, aois[name], OUTPUTS / "aoi_dswx_quicklook.png")
    print(f"wrote {OUTPUTS/'aoi_dswx_quicklook.png'} (DSWx {best['dswx_date']})")


if __name__ == "__main__":
    main()
