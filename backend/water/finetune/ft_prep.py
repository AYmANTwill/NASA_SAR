"""Fine-tuning step 2: read NISAR windows + DSWx labels for the training sites (parallel, cached once).

- one authenticated HTTPS session per worker PROCESS (h5py serialises threads), 16 MB fsspec blocks
  with blockcache, so each window needs few transatlantic range requests
- per-read guard: <= 500 MB per window, data root <= 14 GB, >= 8 GB free (common.check_budget)
- NISAR: same processing as the case (Lee 5x5 in linear power, 10*log10, HH/HV GeoTIFF)
- labels: DSWx WTR reprojected (nearest) onto the NISAR grid; 1 water (classes 1-2), 0 not water, 255 ignore
- every subset is cached under NASA_DATA/finetune/; read times go to outputs/finetune/read_log.csv
Usage: python finetune/ft_prep.py [--workers 5] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import DATA, OUTPUTS, dir_size, rel  # noqa: E402

FT_OUT = OUTPUTS / "finetune"
FT_DATA = DATA / "finetune"
BLOCK = 16 * 2**20


def _job(row: dict, bbox: list) -> dict:
    import rasterio

    from nisar_prep import dswx_reference, lee_filter, read_subset, to_db, write_tif

    tag = f"{row['site']}_T{int(row['track']):03d}{row['direction'][0]}_{row['date']}"
    nis, lab = FT_DATA / "nisar" / f"{tag}.tif", FT_DATA / "labels" / f"{tag}_dswx.tif"
    rec = {"tag": tag, "site": row["site"], "track": int(row["track"]), "date": row["date"], "cached": nis.exists() and lab.exists()}
    if rec["cached"]:
        return {**rec, "nisar_tif": rel(nis), "label_tif": rel(lab)}
    from common import https_fs

    fs = https_fs()
    try:
        if not nis.exists():
            t0 = time.perf_counter()
            with fs.open(row["h5_url"], "rb", block_size=BLOCK, cache_type="blockcache") as f:
                s = read_subset(f, bbox)
            rec["nisar_read_s"] = round(time.perf_counter() - t0, 1)
            rec["nisar_payload_mb"] = round((s["hh"].nbytes + s["hv"].nbytes) / 1e6, 1)
            nis.parent.mkdir(parents=True, exist_ok=True)
            tmp = nis.with_suffix(".part.tif")
            write_tif(tmp, np.stack([to_db(lee_filter(s["hh"])), to_db(lee_filter(s["hv"]))]), s["epsg"], s["transform"],
                      np.nan, "float32", ["HH_dB", "HV_dB"])
            tmp.replace(nis)
        with rasterio.open(nis) as src:
            epsg, tr, shape = src.crs.to_epsg(), src.transform, (src.height, src.width)
        t0 = time.perf_counter()
        urls = [u for u in str(row["wtr_urls"]).split(";") if u]
        ref = dswx_reference([fs.open(u, "rb", block_size=BLOCK, cache_type="blockcache") for u in urls], epsg, tr, shape)
        rec["dswx_read_s"] = round(time.perf_counter() - t0, 1)
        lab.parent.mkdir(parents=True, exist_ok=True)
        write_tif(lab, ref, epsg, tr, 255, "uint8", ["water(1)/not(0)/ignore(255)"])
        rec["label_valid_frac"] = round(float((ref != 255).mean()), 3)
        rec["label_water_frac"] = round(float((ref == 1).mean()), 4)
        return {**rec, "nisar_tif": rel(nis), "label_tif": rel(lab)}
    except Exception as e:
        return {**rec, "error": f"{type(e).__name__}: {str(e)[:160]}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    sites = json.loads((FT_OUT / "sites.json").read_text())["sites"]
    cand = pd.read_csv(FT_OUT / "candidates.csv")
    if a.limit:
        cand = cand.groupby("site").head(max(1, a.limit // max(1, cand["site"].nunique())))
    print(f"{len(cand)} site-dates; data root {dir_size()/1e9:.2f} GB", flush=True)
    t_all = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_job, r.to_dict(), sites[r["site"]]["bbox"]) for _, r in cand.iterrows()]
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            r = rows[-1]
            print(f"[{i}/{len(futs)}] {r['tag']} " + ("cached" if r.get("cached") else
                  r.get("error") or f"NISAR {r.get('nisar_read_s')} s / {r.get('nisar_payload_mb')} MB, DSWx {r.get('dswx_read_s')} s"),
                  flush=True)
    log = pd.DataFrame(rows)
    old = FT_OUT / "read_log.csv"
    if old.exists():
        log = pd.concat([pd.read_csv(old), log], ignore_index=True).drop_duplicates("tag", keep="last")
    log.to_csv(old, index=False)
    ok = log[log.get("error", pd.Series(index=log.index, dtype=object)).isna()]
    ok[["tag", "site", "track", "date", "nisar_tif", "label_tif"]].to_csv(FT_OUT / "dataset.csv", index=False)
    new = log[log["cached"] == False] if "cached" in log else log  # noqa: E712
    if "nisar_read_s" in new and new["nisar_read_s"].notna().any():
        print(f"NISAR reads: median {new['nisar_read_s'].median():.1f} s, "
              f"{new['nisar_payload_mb'].sum() / max(new['nisar_read_s'].sum(), 1e-9):.2f} MB/s per worker (payload); "
              f"wall {time.perf_counter() - t_all:.0f} s with {a.workers} workers")
    print(f"dataset: {len(ok)} site-dates; data root {dir_size()/1e9:.2f} GB")


if __name__ == "__main__":
    main()
