"""Build the Haouz open-water finding from same-track NISAR GCOV pairs.

The flood occurred on 2026-10-10.  For T023/F073 descending and T044/F017
ascending, this runner selects the final acquisition before and first after the
event, reads only the site-union window, and measures persistent new open water.
It also writes the input expected by ``science.cases``.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from adabn import load_scene, norm_scene, predict_scene
from common import BIG_OUT, DATA, MODELS, OUTPUTS, retry, dpath, rel
from data_s1 import load_stats
from evaluate import METHODS, method_threshold
from model import load_model
from nisar_prep import lee_filter, login, read_subset, to_db, write_tif
from nisar_search import dswx_acquisitions, search_dswx, search_nisar

EVENT = pd.Timestamp("2026-10-10")
CASE_BBOX = [-8.2, 31.05, -7.75, 31.45]
# Union of Imlil, Asni and Moulay Brahim plus ~5 km margin.
READ_BBOX = [-8.04, 31.085, -7.865, 31.34]
GEOMETRIES = {(23, 73): "DESCENDING", (44, 17): "ASCENDING"}
GRID = "/science/LSAR/GCOV/grids/frequencyA"
HAOUZ_DIR = DATA / "nisar" / "haouz"
HAOUZ_BIG = BIG_OUT / "haouz"


def select_pairs() -> pd.DataFrame:
    d = search_nisar(READ_BBOX)
    keep = np.zeros(len(d), dtype=bool)
    for (track, frame), direction in GEOMETRIES.items():
        keep |= (d.track == track) & (d.frame == frame) & (d.direction == direction)
    d = d[keep & d.has_HH_HV & (d.aoi_coverage >= 0.9)].copy()
    # Multiple products can share a date. Prefer the one with greatest AOI coverage.
    d = (d.sort_values(["date", "aoi_coverage"], ascending=[True, False])
           .drop_duplicates(["date", "track", "frame"]))
    chosen = []
    for (track, frame), direction in GEOMETRIES.items():
        g = d[(d.track == track) & (d.frame == frame) & (d.direction == direction)].copy()
        dates = pd.to_datetime(g.date)
        pre = g.loc[dates[dates < EVENT].idxmax()] if (dates < EVENT).any() else None
        post = g.loc[dates[dates > EVENT].idxmin()] if (dates > EVENT).any() else None
        if pre is None or post is None:
            continue
        for period, row in (("pre", pre), ("post", post)):
            r = row.to_dict()
            r["period"] = period
            chosen.append(r)
    out = pd.DataFrame(chosen).sort_values(["track", "period"])
    out.to_csv(OUTPUTS / "haouz_scenes.csv", index=False)
    return out


def prepare(scenes: pd.DataFrame) -> pd.DataFrame:
    import earthaccess
    import rasterio

    from common import https_fs
    fs = https_fs()
    HAOUZ_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for _, r in scenes.iterrows():
        tag = f"Haouz_T{int(r.track):03d}{r.direction[0]}_{r.period}_{r.date}"
        out = HAOUZ_DIR / f"{tag}.tif"
        if not out.exists():
            def _read():
                with fs.open(r.h5_url, "rb", block_size=8 * 1024**2, cache_type="blockcache") as f:
                    return read_subset(f, READ_BBOX)
            s = retry(_read, what=tag)
            hh, hv = lee_filter(s["hh"]), lee_filter(s["hv"])
            tmp = out.with_suffix(".part.tif")
            write_tif(tmp, np.stack([to_db(hh), to_db(hv)]), s["epsg"], s["transform"], np.nan,
                      "float32", ["HH_dB", "HV_dB"])
            tmp.replace(out)
        with rasterio.open(out) as src:
            paths.append({"tag": tag, "nisar_tif": rel(out), "epsg": src.crs.to_epsg(),
                          "width": src.width, "height": src.height})
        _catalog_vrts(r.granule, out)
    return scenes.reset_index(drop=True).join(pd.DataFrame(paths))


def _catalog_vrts(granule: str, source: Path) -> None:
    """Expose tiny VRT views to the existing catalog; the large raster stays in NASA_DATA."""
    import rasterio
    from xml.sax.saxutils import escape

    repo = Path(__file__).resolve().parents[2]
    folder = repo / "data" / "GCOV" / granule
    folder.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source) as src:
        gt = ", ".join(map(str, src.transform.to_gdal()))
        srs = escape(src.crs.to_wkt())
        dtype = "Float32"
        for suffix, band in (("HHHH.tif", 1), ("HVHV.tif", 2)):
            xml = (f'<VRTDataset rasterXSize="{src.width}" rasterYSize="{src.height}">'
                   f'<SRS>{srs}</SRS><GeoTransform>{gt}</GeoTransform>'
                   f'<VRTRasterBand dataType="{dtype}" band="1"><NoDataValue>nan</NoDataValue>'
                   f'<SimpleSource><SourceFilename relativeToVRT="0">{escape(str(source))}</SourceFilename>'
                   f'<SourceBand>{band}</SourceBand><SourceProperties RasterXSize="{src.width}" '
                   f'RasterYSize="{src.height}" DataType="{dtype}" BlockXSize="512" BlockYSize="512"/>'
                   f'<SrcRect xOff="0" yOff="0" xSize="{src.width}" ySize="{src.height}"/>'
                   f'<DstRect xOff="0" yOff="0" xSize="{src.width}" ySize="{src.height}"/>'
                   f'</SimpleSource></VRTRasterBand></VRTDataset>')
            (folder / f"freqA_{suffix}").write_text(xml, encoding="utf-8")
    (folder / "_DONE").write_text("water_unet_window_vrt\n", encoding="utf-8")


def method_and_model(device):
    # Reuse the reservoir-selected transfer variant only when its checkpoint exists.
    from timeseries import best_method
    method = best_method()  # the operational variant (chosen on the selection track, heldout_eval.json)
    ck, mode = METHODS[method]
    if not (MODELS / ck).exists():
        method, (ck, mode) = "U-Net source-only", METHODS["U-Net source-only"]
    return method, mode, load_model(MODELS / ck, device)


def infer(scenes: pd.DataFrame, mc: int) -> tuple[list[dict], dict]:
    import rasterio

    from common import gpu_start
    device = gpu_start(__file__)
    method, mode, model = method_and_model(device)
    stats = load_stats()
    pthr = method_threshold(method)
    HAOUZ_BIG.mkdir(parents=True, exist_ok=True)
    track_rows, main = [], {}
    for (track, direction), g in scenes.groupby(["track", "direction"]):
        g = g.set_index("period")
        arrays = {}
        for period in ("pre", "post"):
            x, prof = load_scene(g.loc[period, "nisar_tif"])
            valid = np.all(np.isfinite(x), axis=0)
            xn, _ = norm_scene(x, mode, stats, src=g.loc[period, "nisar_tif"])
            prob, std = predict_scene(model, xn, device, mc=0)
            arrays[period] = (x, prof, valid, xn, prob, std)
        pre, post = arrays["pre"], arrays["post"]
        same = pre[2] & post[2]
        gain = same & (post[4] > pthr) & ~(pre[4] > pthr)
        px = abs(pre[1]["transform"].a * pre[1]["transform"].e) / 1e6
        samples = []
        for _ in range(mc):
            pp, _ = predict_scene(model, pre[3], device, mc=1)
            qp, _ = predict_scene(model, post[3], device, mc=1)
            samples.append(float((same & (qp > pthr) & ~(pp > pthr)).sum() * px))
        area = float(gain.sum() * px)
        sigma = float(np.std(samples, ddof=1)) if len(samples) > 1 else px
        sigma = max(sigma, px)
        out_mask = np.full(gain.shape, 255, np.uint8)
        out_mask[same] = gain[same].astype(np.uint8)
        mask_path = HAOUZ_BIG / f"flood_mask_T{int(track):03d}{direction[0]}.tif"
        write_tif(mask_path, out_mask, pre[1]["crs"].to_epsg(), pre[1]["transform"], 255, "uint8",
                  ["persistent new open water"])
        track_rows.append({"track": int(track), "direction": direction,
                           "pre_date": g.loc["pre", "date"], "post_date": g.loc["post", "date"],
                           "area_km2": area, "mc_area_std_km2": sigma, "mask": str(mask_path)})
        if direction == "DESCENDING":
            dhh = post[0][0] - pre[0][0]
            dhh[~same] = np.nan
            change_path = HAOUZ_BIG / "backscatter_change_T023D.tif"
            write_tif(change_path, dhh, pre[1]["crs"].to_epsg(), pre[1]["transform"], np.nan, "float32",
                      ["post minus pre HH dB"])
            main = {"mask": mask_path, "backscatter_change": change_path,
                    "pre": pre, "post": post, "gain": gain}
    vals = np.array([r["area_km2"] for r in track_rows])
    mc_sigmas = np.array([r["mc_area_std_km2"] for r in track_rows])
    value = float(vals.mean())
    mc_sigma = float(np.sqrt(np.square(mc_sigmas).sum()) / len(mc_sigmas))
    directions = {r["direction"] for r in track_rows}
    orbit_sigma = float(np.ptp(vals) / 2) if {"ASCENDING", "DESCENDING"} <= directions else 0.0
    uncertainty = max(math.hypot(mc_sigma, orbit_sigma), 1e-4)
    summary = {"method": method, "probability_threshold": pthr, "tracks": track_rows,
               "value_km2": value, "mc_sigma_km2": mc_sigma, "orbit_sigma_km2": orbit_sigma,
               "uncertainty_km2": uncertainty,
               "uncertainty_formula": "sqrt(mc_sigma_of_track_mean^2 + half_asc_desc_range^2)"}
    return track_rows, {**summary, **main}


def reference_dswx(profile) -> dict | None:
    """Clear DSWx pre/event new-water area on the supplied NISAR grid."""
    from scipy.ndimage import binary_dilation, binary_erosion
    from nisar_prep import dswx_reference

    d = search_dswx(READ_BBOX, "2026-09-20T00:00:00Z", "2026-10-20T23:59:59Z")
    a = dswx_acquisitions(d, READ_BBOX)
    a = a[a.dswx_aoi_valid_frac >= 0.95].copy()
    dates = pd.to_datetime(a.dswx_date)
    pre = a.loc[dates[dates < EVENT].idxmax()] if (dates < EVENT).any() else None
    post = a.loc[dates[dates >= EVENT].idxmin()] if (dates >= EVENT).any() else None
    if pre is None or post is None:
        return None
    shape = (profile["height"], profile["width"])
    from common import https_fs
    fs = https_fs()
    r0 = dswx_reference([fs.open(u, "rb") for u in pre.wtr_urls.split(";") if u],
                        profile["crs"].to_epsg(), profile["transform"], shape)
    r1 = dswx_reference([fs.open(u, "rb") for u in post.wtr_urls.split(";") if u],
                        profile["crs"].to_epsg(), profile["transform"], shape)
    valid = (r0 != 255) & (r1 != 255)
    gain = valid & (r1 == 1) & (r0 == 0)
    px = abs(profile["transform"].a * profile["transform"].e) / 1e6
    area = float(gain.sum() * px)
    edge = float((binary_dilation(gain) ^ binary_erosion(gain)).sum() * px / 2)
    return {"value": area, "uncertainty": max(edge, px), "unit": "km2", "sigma": 1,
            "pre_date": str(pre.dswx_date), "post_date": str(post.dswx_date)}


HAOUZ_LIMITS = [
    {"fr": "Revisite de 12 jours par trace : les passages utilisés sont le 1er/3 octobre (avant) et le 13/15 octobre "
           "(après), soit 3 à 5 jours après la crue éclair du 10 octobre. Une crue éclair se retire en quelques heures; "
           "ce résultat mesure uniquement l'eau ouverte encore présente au passage, pas l'emprise maximale.",
     "en": "12-day revisit per track: the passes used are 1/3 October (before) and 13/15 October (after), 3 to 5 days "
           "after the 10 October flash flood. Flash floods recede within hours; this result measures only open water "
           "still present at the pass, not the peak extent.",
     "ar": "إعادة الزيارة كل 12 يوماً لكل مسار: المرورات المستخدمة 1/3 أكتوبر (قبل) و13/15 أكتوبر (بعد)، أي بعد 3 إلى 5 أيام "
           "من السيل المفاجئ في 10 أكتوبر. تنحسر السيول المفاجئة خلال ساعات؛ تقيس النتيجة المياه المفتوحة الباقية وقت المرور فقط."},
    {"fr": "Vallées étroites : les lits d'oued du Haouz (Imlil, Asni, Moulay Brahim) font quelques dizaines de mètres de large, "
           "comparables aux pixels GCOV de 10 à 20 m après filtre de Lee 5x5 (environ 50 à 100 m effectifs); une eau "
           "résiduelle dans ces lits est en grande partie sous la résolution effective.",
     "en": "Narrow valleys: the Haouz wadi beds (Imlil, Asni, Moulay Brahim) are a few tens of metres wide, comparable to the "
           "10-20 m GCOV pixels after the 5x5 Lee filter (about 50-100 m effective); residual water in these beds is "
           "largely below the effective resolution.",
     "ar": "أودية ضيقة: مجاري الأودية في الحوز (إمليل، أسني، مولاي إبراهيم) بعرض بضع عشرات من الأمتار، وهو ما يقارب بكسلات GCOV "
           "من 10 إلى 20 م بعد مرشح لي 5x5 (حوالي 50 إلى 100 م فعلياً)؛ المياه المتبقية في هذه المجاري أدنى غالباً من الدقة الفعلية."},
    {"fr": "Repliement et ombre radar : sur les versants raides du Haut Atlas, le repliement mélange le fond de vallée avec le "
           "versant face au radar, et l'ombre produit une rétrodiffusion faible qui ressemble à de l'eau; les deux traces "
           "(23 descendante, 44 ascendante) voient des versants différents, d'où l'écart entre elles.",
     "en": "Radar layover and shadow: on steep High Atlas slopes, layover mixes the valley floor with the radar-facing slope, "
           "and shadow produces low backscatter that resembles water; the two tracks (23 descending, 44 ascending) see "
           "different slopes, which is why they disagree.",
     "ar": "التراكب والظل الراداري: على منحدرات الأطلس الكبير الشديدة يخلط التراكب قاع الوادي بالمنحدر المواجه للرادار، "
           "ويُنتج الظل تشتتاً خلفياً ضعيفاً يشبه الماء؛ يرى المساران (23 الهابط و44 الصاعد) منحدرات مختلفة، ولذلك يختلفان."},
    {"fr": "Aucune paire DSWx claire avant/après n'existe; la valeur n'a donc pas de référence et l'accord n'est pas évalué.",
     "en": "No clear DSWx pre/post pair exists, so the value has no reference and agreement is not evaluated.",
     "ar": "لا يوجد زوج DSWx واضح قبل/بعد، لذلك لا مرجع للقيمة ولا يُقيَّم التوافق."}]


def portable(obj):
    """Replace absolute data-root paths in diagnostics with '$NASA_DATA/...'."""
    if isinstance(obj, dict):
        return {k: portable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [portable(v) for v in obj]
    if isinstance(obj, str) and ("nasa_data" in obj or obj.startswith(str(DATA))):
        return rel(obj)
    return obj


def build_payload(result: dict, ref: dict | None, scenes: pd.DataFrame) -> dict:
    backend = Path(__file__).resolve().parents[1]
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from science.case_models import Measurement, agreement

    nisar = Measurement(value=round(result["value_km2"], 4),
                        uncertainty=round(result["uncertainty_km2"], 4), unit="km2", sigma=1)
    reference = None if ref is None else Measurement(**{k: ref[k] for k in ("value", "uncertainty", "unit", "sigma")})
    finding = {"id": "flooded_area",
               "label": {"fr": "Surface d'eau nouvelle persistante", "en": "Persistent new open-water area",
                         "ar": "مساحة المياه المفتوحة الجديدة المستمرة"},
               "nisar": nisar.model_dump(mode="json"),
               "reference": None if reference is None else reference.model_dump(mode="json"),
               "reference_source": None if reference is None else {
                   "name": "OPERA DSWx-HLS (NASA/JPL)",
                   "url": "https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/"},
               "agreement": agreement(nisar, reference)}
    detectable = nisar.value > 2 * nisar.one_sigma
    limits = HAOUZ_LIMITS
    products = [f"GCOV_T{int(r.track):03d}_F{int(r.frame):03d}_{r.date.replace('-', '')}_{r.date.replace('-', '')}"
                for _, r in scenes.iterrows()]
    map_figure = {"id": "haouz_backscatter_change",
                  "title": {"fr": "Changement de rétrodiffusion NISAR", "en": "NISAR backscatter change",
                            "ar": "تغير التشتت الخلفي لـ NISAR"},
                  "caption": {"template": "backend.water_haouz_map", "params": {},
                              "text": {"fr": "HH après moins avant sur la trace descendante 23.",
                                       "en": "Post-minus-pre HH on descending track 23.",
                                       "ar": "فرق HH بعد الحدث وقبله على المسار الهابط 23."}},
                  "raster": "backscatter_change_T023D.tif",
                  "layer": {"kind": "backscatter_change", "unit": "dB",
                            "palette": "diverging_displacement", "min": -8, "max": 8,
                            "period": {"start": "2026-10-01", "end": "2026-10-13"},
                            "source": "NISAR GCOV T023/F073", "sign_convention": None}}
    payload = {"date": "2026-10-10T00:00:00Z", "bbox": CASE_BBOX, "products": products,
               "findings": [finding], "figures": [map_figure], "limits": limits,
               "interpretation": "detectable persistent open water" if detectable else "no detectable persistent flood extent",
               "diagnostics": portable({k: v for k, v in result.items() if k not in ("pre", "post", "gain", "mask")})}
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=20)
    ap.add_argument("--search-only", action="store_true")
    a = ap.parse_args()
    scenes = select_pairs()
    print(scenes[["date", "track", "frame", "direction", "period", "aoi_coverage"]].to_string(index=False))
    if a.search_only:
        return
    scenes = prepare(scenes)
    tracks, result = infer(scenes, a.mc)
    ref = reference_dswx(result["pre"][1])
    payload = build_payload(result, ref, scenes)
    out = OUTPUTS / "haouz_flooded_area.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    case_dir = Path(__file__).resolve().parents[2] / "results" / "haouz-flood-2026"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "findings.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    shutil.copyfile(dpath(result["mask"]), case_dir / "flood_mask.tif")
    shutil.copyfile(dpath(result["backscatter_change"]), case_dir / "backscatter_change_T023D.tif")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

