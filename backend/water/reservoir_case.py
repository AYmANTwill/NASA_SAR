"""Case study bin-el-ouidane-2026 (kind "method"): reservoir monitoring through clouds with NISAR.

Every number is read from outputs/ files written by the pipeline:
  - water_area_change: NISAR (change_pair.json; 1σ = mean |asc - desc| area difference, orbit_consistency.csv)
    vs OPERA DSWx on the same pixels (DSWx GeoTIFFs; 1σ = half the area of the DSWx shoreline band)
  - heldout_iou: IoU vs DSWx on tracks never used for any choice (heldout_eval.json; 1σ = 95% interval / 3.92)
  - orbit_consistency: mean |asc - desc| model area on dates <= 3 days apart (1σ = bootstrap over pairs)
Writes outputs/reservoir_case.json (full CaseStudy). It validates as CaseStudy once the id is in the contract
(CaseId / CASE_KIND); until then backend/tests/test_water.py validates every nested object.
Usage: python reservoir_case.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import binary_dilation, binary_erosion

from common import OUTPUTS, dpath

CASE_ID = "bin-el-ouidane-2026"


def L(en, fr, ar):
    return {"en": en, "fr": fr, "ar": ar}


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from science.case_models import Figure, Finding, Measurement, Source, TemplatedText, agreement

    aoi = json.loads((OUTPUTS / "aoi.json").read_text())
    res = aoi["chosen"]["reservoir"]
    bbox = aoi["aois"][res]["bbox"]
    pair = json.loads((OUTPUTS / "change_pair.json").read_text())
    held = json.loads((OUTPUTS / "heldout_eval.json").read_text())
    oc = pd.read_csv(OUTPUTS / "orbit_consistency.csv")
    scenes = pd.read_csv(OUTPUTS / "nisar_scenes.csv").set_index("tag")
    cand = pd.read_csv(OUTPUTS / "candidate_scenes.csv")
    cand = cand[(cand["reservoir"] == res) & cand["usable"]]
    dswx = Source(name="OPERA DSWx-HLS (NASA/JPL, PO.DAAC)", url="https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/")
    rng = np.random.default_rng(0)

    n = Measurement(value=round(pair["water_post_km2"] - pair["water_pre_km2"], 3),
                    uncertainty=round(float(oc["abs_diff_km2"].mean()), 3), unit="km2")
    with rasterio.open(dpath(scenes.loc[pair["pre"]["tag"]].dswx_tif)) as s:
        d0, px = s.read(1), abs(s.transform.a * s.transform.e) / 1e6
    with rasterio.open(dpath(scenes.loc[pair["post"]["tag"]].dswx_tif)) as s:
        d1 = s.read(1)
    valid = (d0 != 255) & (d1 != 255)
    w0, w1 = (d0 == 1) & valid, (d1 == 1) & valid
    edge = (binary_dilation(w0) ^ binary_erosion(w0)) | (binary_dilation(w1) ^ binary_erosion(w1))
    r = Measurement(value=round(float((w1.sum() - w0.sum()) * px), 3), uncertainty=round(max(float(edge.sum() * px / 2), px), 3), unit="km2")
    f_change = Finding(id="water_area_change", label=L("Water-area change (NISAR vs optical DSWx)",
                       "Variation de la surface en eau (NISAR vs DSWx optique)", "تغير مساحة المياه (NISAR مقابل DSWx البصري)"),
                       nisar=n, reference=r, reference_source=dswx, agreement=agreement(n, r))

    h = held["headline_heldout"]
    lo, hi = h["ci95"]["iou"]
    iou = Measurement(value=round(100 * h["iou"], 2), uncertainty=round(100 * (hi - lo) / 3.92, 2), unit="percent")
    tracks = "/".join(str(t) for t in held["heldout_tracks"])
    f_iou = Finding(id="heldout_iou", label=L(f"Agreement with DSWx on held-out tracks {tracks} (IoU)",
                    f"Accord avec DSWx sur les traces tenues à l'écart {tracks} (IoU)",
                    f"التوافق مع DSWx على المسارات المحجوزة {tracks} (IoU)"),
                    nisar=iou, reference=None, reference_source=None, agreement=agreement(iou, None))

    d = oc["abs_diff_km2"].to_numpy()
    boot = d[rng.integers(0, len(d), size=(1000, len(d)))].mean(1)
    orb = Measurement(value=round(float(d.mean()), 3), uncertainty=round(float(boot.std()), 3), unit="km2")
    f_orb = Finding(id="orbit_consistency", label=L("Ascending vs descending area difference (≤ 3 days apart)",
                    "Écart de surface entre orbites montante et descendante (≤ 3 jours)",
                    "فرق المساحة بين المدارين الصاعد والهابط (≤ 3 أيام)"),
                    nisar=orb, reference=None, reference_source=None, agreement=agreement(orb, None))

    def fig(fid, name, title, cap):
        return Figure(id=fid, kind="image", title=title, url=f"water/outputs/figures/{name}",
                      caption=TemplatedText(template=f"backend.water_{fid}", params={}, text=cap)).model_dump(mode="json")

    pre, post = pair["pre"]["date"], pair["post"]["date"]
    figures = [
        fig("reservoir_hero", "hero.png", L("Before, after and change", "Avant, après et changement", "قبل وبعد والتغير"),
            L(f"NISAR water on {pre} and {post}; blue gain, red loss.", f"Eau NISAR le {pre} et le {post} ; bleu gain, rouge perte.",
              f"مياه NISAR في {pre} و{post}؛ الأزرق زيادة والأحمر نقص.")),
        fig("reservoir_validation", "validation.png", L("Validation against DSWx", "Validation avec DSWx", "التحقق باستخدام DSWx"),
            L("Held-out track, median date: white agreement, red miss, orange false alarm.",
              "Trace tenue à l'écart, date médiane : blanc accord, rouge oubli, orange fausse alarme.",
              "مسار محجوز، التاريخ الوسيط: الأبيض توافق، الأحمر إغفال، البرتقالي إنذار كاذب.")),
        fig("reservoir_timeseries", "timeseries.png", L("Water area over time", "Surface en eau dans le temps", "مساحة المياه عبر الزمن"),
            L("Three NISAR tracks and DSWx; flagged dates are kept and marked.",
              "Trois traces NISAR et DSWx ; les dates signalées sont gardées et marquées.",
              "ثلاثة مسارات NISAR وDSWx؛ التواريخ المعلَّمة محفوظة ومميزة.")),
        fig("reservoir_clouds", "clouds.png", L("Radar sees water through clouds", "Le radar voit l'eau à travers les nuages", "الرادار يرى المياه عبر السحب"),
            L("Same day: DSWx masked by clouds, NISAR water map complete.", "Même jour : DSWx masqué par les nuages, carte NISAR complète.",
              "في اليوم نفسه: DSWx محجوب بالسحب وخريطة NISAR كاملة.")),
    ]
    passes = cand.sort_values("datetime")
    asc = lambda p, a, b: a if p.direction == "ASCENDING" else b
    timeline = [{"label": L(f"NISAR pass, track {int(p.track)} {p.direction.lower()}",
                            f"Passage NISAR, trace {int(p.track)} {asc(p, 'montante', 'descendante')}",
                            f"مرور NISAR، المسار {int(p.track)} {asc(p, 'صاعد', 'هابط')}"),
                 "at": pd.to_datetime(p.datetime).strftime("%Y-%m-%dT%H:%M:%SZ")} for p in passes.itertuples()]
    crids = sorted({g.split("_")[-5] for g in passes["granule"] if "_P" in g})
    cr = ", ".join(crids)
    b = held["area_bias"]["held-out raw"]
    bl, bh = b["ci95_km2"]
    limits = [
        {"template": "backend.water_dswx_reference", "params": {}, "text": L(
            "OPERA DSWx is optical: a weak reference (clouds, shadows, shoreline mixing, a day up to ±5 days apart).",
            "OPERA DSWx est optique : une référence faible (nuages, ombres, mélange au rivage, jour jusqu'à ±5 jours d'écart).",
            "OPERA DSWx بصري: مرجع ضعيف (سحب وظلال واختلاط عند الشاطئ ويوم قد يبعد حتى ±5 أيام).")},
        {"template": "backend.water_provisional", "params": {"crid": crids}, "text": L(
            f"NISAR GCOV products are provisional (CRID {cr}); calibration may change.",
            f"Les produits NISAR GCOV sont provisoires (CRID {cr}) ; l'étalonnage peut changer.",
            f"منتجات NISAR GCOV مؤقتة (CRID {cr})؛ قد تتغير المعايرة.")},
        {"template": "backend.water_transfer", "params": {}, "text": L(
            "Trained on Sentinel-1 C-band VV/VH and applied to NISAR L-band HH/HV (HH↔VV, HV↔VH): an assumption, checked only against DSWx.",
            "Entraîné sur Sentinel-1 bande C VV/VH et appliqué à NISAR bande L HH/HV (HH↔VV, HV↔VH) : une hypothèse, vérifiée seulement avec DSWx.",
            "دُرِّب على Sentinel-1 (النطاق C، VV/VH) وطُبِّق على NISAR (النطاق L، HH/HV): افتراض لم يُتحقق منه إلا مقابل DSWx.")},
        {"template": "backend.water_shoreline_bias", "params": {"bias_km2": round(b["mean_km2"], 2), "ci95_km2": [round(bl, 2), round(bh, 2)]},
         "text": L(f"Area is biased high near shorelines: {b['mean_km2']:+.2f} km² on held-out tracks (95% interval {bl:+.2f} to {bh:+.2f}).",
                   f"La surface est surestimée près des rives : {b['mean_km2']:+.2f} km² sur les traces tenues à l'écart (intervalle 95 % {bl:+.2f} à {bh:+.2f}).",
                   f"المساحة مُقدَّرة بالزيادة قرب الشواطئ: {b['mean_km2']:+.2f} كم² على المسارات المحجوزة (مجال 95% من {bl:+.2f} إلى {bh:+.2f}).")},
    ]
    findings = [f.model_dump(mode="json") for f in (f_change, f_iou, f_orb)]
    status = "final" if all(f["nisar"]["uncertainty"] > 0 for f in findings) else "draft"
    hl = f"NISAR {n.value:+.2f} ± {n.uncertainty:.2f} km², DSWx {r.value:+.2f} ± {r.uncertainty:.2f} km² ({f_change.agreement})"
    case = {
        "id": CASE_ID, "kind": "method", "status": status,
        "title": L("Bin El Ouidane: reservoir monitoring through clouds", "Bin El Ouidane : suivi du barrage à travers les nuages",
                   "بين الويدان: مراقبة السد عبر السحب"),
        "date": f"{post}T00:00:00Z",
        "location": {"lat": round((bbox[1] + bbox[3]) / 2, 4), "lon": round((bbox[0] + bbox[2]) / 2, 4), "bbox": bbox,
                     "place": L("Bin El Ouidane reservoir, Morocco", "Barrage Bin El Ouidane, Maroc", "سد بين الويدان، المغرب")},
        "headline": {"template": "backend.water_area_change",
                     "params": {"nisar": n.model_dump(mode="json"), "reference": r.model_dump(mode="json"), "agreement": f_change.agreement},
                     "text": L(f"Water area {pre} → {post}: {hl}.", f"Surface en eau {pre} → {post} : {hl}.", f"مساحة المياه {pre} ← {post}: {hl}.")},
        "findings": findings, "figures": figures, "exposure": None, "timeline": timeline, "answer_ids": [],
        "limits": limits, "placeholders": []}
    (OUTPUTS / "reservoir_case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{CASE_ID}: status {status}; {hl}; held-out IoU {iou.value:.1f} ± {iou.uncertainty:.1f} %; "
          f"orbit {orb.value:.2f} ± {orb.uncertainty:.2f} km2; {len(timeline)} passes; CRID {crids}")


if __name__ == "__main__":
    main()
