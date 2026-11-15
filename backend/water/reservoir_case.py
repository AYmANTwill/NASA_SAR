"""Case study bin-el-ouidane-2026 (kind "method"): reservoir monitoring through clouds with NISAR.

Every number is read from outputs/ files written by the pipeline:
  - water_area_change: mean over tracks of the per-track change between the passes nearest the case dates
    (change_multitrack.json; 1σ = standard error over tracks), NISAR vs OPERA DSWx on the same pixels
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
WIN = 5  # days: passes of the other tracks paired with the case dates


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

    # Multi-track change (2026-11-15): for every track with a clean pass within +-WIN days of BOTH case dates, the
    # change post - pre on that track (a constant per-track bias cancels); value = mean over tracks, 1σ = standard
    # error over tracks. DSWx: the same passes' DSWx water areas (each track pairs with its own optical acquisition).
    ts = pd.read_csv(OUTPUTS / "water_area_timeseries.csv")
    ts = ts[ts["flag"].isna() & ts["dswx_water_km2"].notna()].assign(date=lambda d: pd.to_datetime(d["date"]))
    pre_d, post_d = pd.Timestamp(pair["pre"]["date"]), pd.Timestamp(pair["post"]["date"])
    per_track = []
    for trk, g in ts.groupby("track"):
        a = g.loc[(g["date"] - pre_d).abs() <= pd.Timedelta(days=WIN)]
        b = g.loc[(g["date"] - post_d).abs() <= pd.Timedelta(days=WIN)]
        if len(a) and len(b):
            a = a.loc[(a["date"] - pre_d).abs().idxmin()]
            b = b.loc[(b["date"] - post_d).abs().idxmin()]
            per_track.append({"track": int(trk), "pre": a["date"].strftime("%Y-%m-%d"), "post": b["date"].strftime("%Y-%m-%d"),
                              "nisar_km2": float(b["model_water_on_dswx_valid_km2"] - a["model_water_on_dswx_valid_km2"]),
                              "dswx_km2": float(b["dswx_water_km2"] - a["dswx_water_km2"])})
    pt = pd.DataFrame(per_track)
    assert len(pt) >= 2, "multi-track change needs at least 2 tracks"
    se = lambda v: float(v.std(ddof=1) / np.sqrt(len(v)))
    n = Measurement(value=round(float(pt["nisar_km2"].mean()), 3), uncertainty=round(max(se(pt["nisar_km2"]), 0.01), 3), unit="km2")
    r = Measurement(value=round(float(pt["dswx_km2"].mean()), 3), uncertainty=round(max(se(pt["dswx_km2"]), 0.01), 3), unit="km2")
    (OUTPUTS / "change_multitrack.json").write_text(json.dumps({
        "rule": f"per track: change between the clean passes nearest each case date (within ±{WIN} d); mean over tracks; "
                "1σ = standard error over tracks; model and DSWx areas on the same DSWx-valid pixels",
        "case_dates": [pair["pre"]["date"], pair["post"]["date"]], "method": pair.get("method"),
        "per_track": per_track, "nisar": n.model_dump(mode="json"), "dswx": r.model_dump(mode="json")}, indent=2))
    ntr = len(pt)
    f_change = Finding(id="water_area_change", label=L(f"Water-area change, {ntr} tracks (NISAR vs optical DSWx)",
                       f"Variation de la surface en eau, {ntr} traces (NISAR vs DSWx optique)",
                       f"تغير مساحة المياه، {ntr} مسارات (NISAR مقابل DSWx البصري)"),
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

    # Headline (team decision 2026-11-15): IoU on a reservoir never used for training or any choice (fine-tune eval)
    f_unseen = None
    ev_path, ac = OUTPUTS / "finetune" / "v3" / "eval.json", OUTPUTS / "finetune" / "active_run.txt"
    if ev_path.exists() and ac.exists() and held["variant_selected_on_selection_track"] == "U-Net + AdaBN + NISAR fine-tune":
        ev = json.loads(ev_path.read_text())
        test_key = next((k for k in ev["sets"] if k.startswith("test:")), None)
        run = ac.read_text().strip()
        mk = next((k for k in ev["sets"].get(test_key, {}) if k.startswith(run + "_")), None) if test_key else None
        if mk:
            r_ = ev["sets"][test_key][mk]
            lo_, hi_ = r_["ci95"]["iou"]
            site = test_key.split(":", 1)[1].replace("_", " ")
            un = Measurement(value=round(100 * r_["iou"], 2), uncertainty=round(100 * (hi_ - lo_) / 3.92, 2), unit="percent")
            f_unseen = Finding(id="unseen_reservoir_iou", label=L(
                f"Agreement with DSWx on a reservoir never used for training ({site}, {r_['n_dates']} dates, IoU)",
                f"Accord avec DSWx sur un barrage jamais utilisé à l'entraînement ({site}, {r_['n_dates']} dates, IoU)",
                f"التوافق مع DSWx على سد لم يُستخدم في التدريب ({site}، {r_['n_dates']} تاريخًا، IoU)"),
                nisar=un, reference=None, reference_source=None, agreement=agreement(un, None))

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
    figures = figures[-1:] + figures[:-1]  # clouds first: the strongest message (team request, 2026-11-15)
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
    nft, inc_en, inc_fr, inc_ar, site_after = 0, "", "", "", None
    if held["variant_selected_on_selection_track"] == "U-Net + AdaBN + NISAR fine-tune":
        from evaluate import METHODS, _ft_choice
        ch = _ft_choice()
        site_after = ch.get("case_dates_in_training_after")
        nft = len([s for s in ch["train_sites"] if s != res]) + 1  # other reservoirs (+ the validation reservoir)
        if METHODS["U-Net + AdaBN + NISAR fine-tune"][1] == "s1inc":
            inc_en, inc_fr, inc_ar = " and the radar incidence angle", " et l'angle d'incidence radar", " وزاوية سقوط الرادار"
    limits = [
        {"template": "backend.water_dswx_reference", "params": {}, "text": L(
            "OPERA DSWx is optical: a weak reference (clouds, shadows, shoreline mixing, a day up to ±5 days apart).",
            "OPERA DSWx est optique : une référence faible (nuages, ombres, mélange au rivage, jour jusqu'à ±5 jours d'écart).",
            "OPERA DSWx بصري: مرجع ضعيف (سحب وظلال واختلاط عند الشاطئ ويوم قد يبعد حتى ±5 أيام).")},
        {"template": "backend.water_provisional", "params": {"crid": cr}, "text": L(
            f"NISAR GCOV products are provisional (CRID {cr}); calibration may change.",
            f"Les produits NISAR GCOV sont provisoires (CRID {cr}) ; l'étalonnage peut changer.",
            f"منتجات NISAR GCOV مؤقتة (CRID {cr})؛ قد تتغير المعايرة.")},
        ({"template": "backend.water_transfer_finetuned", "params": {"n_reservoirs": nft}, "text": L(
            f"Pre-trained on Sentinel-1 C-band VV/VH, then fine-tuned on NISAR L-band HH/HV{inc_en} with OPERA DSWx labels of {nft} other "
            + (f"Moroccan reservoirs and of this reservoir's passes after {site_after} only (marked 'in training'; no date of the "
               "June–September case period, and none of the reported numbers, uses them); checked only against DSWx, itself optical."
               if site_after else "Moroccan reservoirs (never this one); checked only against DSWx, itself optical."),
            f"Pré-entraîné sur Sentinel-1 bande C VV/VH, puis affiné sur NISAR bande L HH/HV{inc_fr} avec les étiquettes OPERA DSWx de {nft} autres "
            + (f"barrages marocains et des seuls passages de ce barrage après le {site_after} (marqués « entraînement » ; aucune date de "
               "la période du cas juin–septembre, et aucun chiffre affiché, ne les utilise) ; vérifié seulement avec DSWx, lui-même optique."
               if site_after else "barrages marocains (jamais celui-ci) ; vérifié seulement avec DSWx, lui-même optique."),
            f"دُرِّب أولاً على Sentinel-1 (النطاق C، VV/VH) ثم ضُبط على NISAR (النطاق L، HH/HV){inc_ar} بعلامات OPERA DSWx من {nft} سدود "
            + (f"مغربية أخرى ومن مرور هذا السد بعد {site_after} فقط (معلَّمة «تدريب»؛ لا تستخدمها أي من تواريخ فترة الحالة يونيو–سبتمبر "
               "ولا أي رقم معروض)؛ لم يُتحقق منه إلا مقابل DSWx، وهو بصري."
               if site_after else "مغربية أخرى (ليس هذا السد)؛ لم يُتحقق منه إلا مقابل DSWx، وهو بصري."))}
         if held["variant_selected_on_selection_track"] == "U-Net + AdaBN + NISAR fine-tune" else
         {"template": "backend.water_transfer", "params": {}, "text": L(
            "Trained on Sentinel-1 C-band VV/VH and applied to NISAR L-band HH/HV (HH↔VV, HV↔VH): an assumption, checked only against DSWx.",
            "Entraîné sur Sentinel-1 bande C VV/VH et appliqué à NISAR bande L HH/HV (HH↔VV, HV↔VH) : une hypothèse, vérifiée seulement avec DSWx.",
            "دُرِّب على Sentinel-1 (النطاق C، VV/VH) وطُبِّق على NISAR (النطاق L، HH/HV): افتراض لم يُتحقق منه إلا مقابل DSWx.")}),
        {"template": "backend.water_area_bias", "params": {"bias_km2": round(b["mean_km2"], 2), "ci95_lo_km2": round(bl, 2), "ci95_hi_km2": round(bh, 2)},
         "text": (L(f"Area is biased high near shorelines: {b['mean_km2']:+.2f} km² on held-out tracks (95% interval {bl:+.2f} to {bh:+.2f}).",
                    f"La surface est surestimée près des rives : {b['mean_km2']:+.2f} km² sur les traces tenues à l'écart (intervalle 95 % {bl:+.2f} à {bh:+.2f}).",
                    f"المساحة مُقدَّرة بالزيادة قرب الشواطئ: {b['mean_km2']:+.2f} كم² على المسارات المحجوزة (مجال 95% من {bl:+.2f} إلى {bh:+.2f}).")
                  if bl > 0 else
                  L(f"Area is biased low (water slightly under-mapped): {b['mean_km2']:+.2f} km² on held-out tracks (95% interval {bl:+.2f} to {bh:+.2f}).",
                    f"La surface est sous-estimée (eau légèrement sous-cartographiée) : {b['mean_km2']:+.2f} km² sur les traces tenues à l'écart (intervalle 95 % {bl:+.2f} à {bh:+.2f}).",
                    f"المساحة مُقدَّرة بالنقص (المياه أقل قليلاً من الواقع): {b['mean_km2']:+.2f} كم² على المسارات المحجوزة (مجال 95% من {bl:+.2f} إلى {bh:+.2f}).")
                  if bh < 0 else
                  L(f"Area bias on held-out tracks: {b['mean_km2']:+.2f} km² (95% interval {bl:+.2f} to {bh:+.2f}, includes zero).",
                    f"Biais de surface sur les traces tenues à l'écart : {b['mean_km2']:+.2f} km² (intervalle 95 % {bl:+.2f} à {bh:+.2f}, contient zéro).",
                    f"انحياز المساحة على المسارات المحجوزة: {b['mean_km2']:+.2f} كم² (مجال 95% من {bl:+.2f} إلى {bh:+.2f}، يشمل الصفر)."))},
    ]
    ft_csv = Path(__file__).resolve().parent / "model" / "fine_tuning_scenes.csv"
    if site_after and ft_csv.exists():  # exactly which reservoirs, tracks and dates the fine-tuning used
        ft = pd.read_csv(ft_csv)
        tr = ft[ft["role"].str.startswith("training")]
        own = tr[tr["site"] == res].sort_values("date")
        own_txt = ", ".join(f"{d} (T{int(t)})" for d, t in zip(own["date"], own["track"]))
        n_res, n_sc = tr["site"].nunique() - 1, len(tr) - len(own)
        tracks = ", ".join(str(int(t)) for t in sorted(tr["track"].unique()))
        limits.append({"template": "backend.water_finetune_data",
                       "params": {"n_other_reservoirs": n_res, "n_other_scenes": n_sc, "case_dates": own_txt, "tracks": tracks},
                       "text": L(
            f"Fine-tuning data: {n_sc} NISAR scenes of {n_res} other Moroccan reservoirs (tracks {tracks}, June–November 2026) "
            f"and {len(own)} passes of this reservoir: {own_txt}. OPERA DSWx is both the training label and the reference "
            "used here, so the scores measure agreement with DSWx, not with ground truth. The list is in backend/water/model/fine_tuning_scenes.csv.",
            f"Données d'affinage : {n_sc} scènes NISAR de {n_res} autres barrages marocains (traces {tracks}, juin–novembre 2026) "
            f"et {len(own)} passages de ce barrage : {own_txt}. OPERA DSWx est à la fois l'étiquette d'entraînement et la référence "
            "utilisée ici : les scores mesurent l'accord avec DSWx, pas avec la vérité terrain. Liste : backend/water/model/fine_tuning_scenes.csv.",
            f"بيانات الضبط الدقيق: {n_sc} مشهد NISAR من {n_res} سدًا مغربيًا آخر (المسارات {tracks}، يونيو–نوفمبر 2026) "
            f"و{len(own)} مرورًا لهذا السد: {own_txt}. ‏OPERA DSWx هو في آن واحد علامة التدريب والمرجع المستخدم هنا، "
            "لذا تقيس الدرجات التوافق مع DSWx لا مع الحقيقة الميدانية. القائمة في backend/water/model/fine_tuning_scenes.csv.")})
    findings = [f.model_dump(mode="json") for f in ((f_unseen,) if f_unseen else ()) + (f_change, f_iou, f_orb)]
    status = "final" if all(f["nisar"]["uncertainty"] > 0 for f in findings) else "draft"
    ag = {"agree": ("agree", "concordants", "متوافقان"), "disagree": ("disagree", "discordants", "غير متوافقين")}.get(
        f_change.agreement, (f_change.agreement,) * 3)
    hl_l = [f"NISAR {n.value:+.2f} ± {n.uncertainty:.2f} {u}, DSWx {r.value:+.2f} ± {r.uncertainty:.2f} {u} ({a})"
            for u, a in zip(("km²", "km²", "كم²"), ag)]
    hl = hl_l[0]
    case = {
        "id": CASE_ID, "kind": "method", "status": status,
        "title": L("Bin El Ouidane: reservoir monitoring through clouds", "Bin El Ouidane : suivi du barrage à travers les nuages",
                   "بين الويدان: مراقبة السد عبر السحب"),
        "date": f"{post}T00:00:00Z",
        "location": {"lat": round((bbox[1] + bbox[3]) / 2, 4), "lon": round((bbox[0] + bbox[2]) / 2, 4), "bbox": bbox,
                     "place": L("Bin El Ouidane reservoir, Morocco", "Barrage Bin El Ouidane, Maroc", "سد بين الويدان، المغرب")},
        "headline": {"template": "backend.water_area_change",
                     "params": {"nisar": n.model_dump(mode="json"), "reference": r.model_dump(mode="json"), "agreement": f_change.agreement},
                     "text": L(f"Water area {pre} → {post}, {ntr} tracks: {hl_l[0]}.", f"Surface en eau {pre} → {post}, {ntr} traces : {hl_l[1]}.",
                               f"مساحة المياه {pre} ← {post}، {ntr} مسارات: {hl_l[2]}.")},
        "findings": findings, "figures": figures, "exposure": None, "timeline": timeline, "answer_ids": [],
        "limits": limits, "placeholders": []}
    (OUTPUTS / "reservoir_case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{CASE_ID}: status {status}; {hl}; held-out IoU {iou.value:.1f} ± {iou.uncertainty:.1f} %; "
          f"orbit {orb.value:.2f} ± {orb.uncertainty:.2f} km2; {len(timeline)} passes; CRID {crids}")


if __name__ == "__main__":
    main()
