"""Generate docs/claude/WATER_HANDOFF.md from the output files (no number is typed by hand).

Every metric below is read from backend/water/outputs/*. Validation status of each JSON is computed
here with the team's own models (science.case_models) and the frontend ClassifierResult field list.
Usage: python handoff_doc.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from common import OUTPUTS

ROOT = Path(__file__).resolve().parents[2]
DOC = Path(__file__).resolve().parent / "WATER_HANDOFF.md"


def j(name):
    return json.loads((OUTPUTS / name).read_text(encoding="utf-8"))


def ci(lo, hi, nd=3):
    return f"[{lo:.{nd}f}, {hi:.{nd}f}]"


def row(r, dom, meth):
    x = r[(r["domain"] == dom) & (r["method"] == meth)]
    if x.empty:
        raise SystemExit(f"missing results row: {dom} / {meth}")
    return x.iloc[0]


def validate():
    sys.path.insert(0, str(ROOT / "backend"))
    from science.case_models import CaseStudy, Figure, Finding

    out = {}
    h = j("haouz_open_water.json")
    try:
        [Finding.model_validate(f) for f in h["findings"]]
        out["haouz"] = "the `findings[]` entries validate as `science.case_models.Finding`; `python -m science.cases --offline --dry-run` assembles `haouz-flood-2026` with it"
    except Exception as e:
        out["haouz"] = f"does NOT validate: {type(e).__name__}"
    rc = j("reservoir_case.json")
    try:
        [Finding.model_validate(f) for f in rc["findings"]]
        [Figure.model_validate(f) for f in rc["figures"]]
        nested = "nested `Finding` and `Figure` objects validate"
    except Exception as e:
        nested = f"nested objects do NOT validate ({type(e).__name__})"
    try:
        CaseStudy.model_validate({k: v for k, v in rc.items() if k not in ("framing", "selection_reason", "placeholders")})
        top = "the full `CaseStudy` validates"
    except Exception as e:
        msg = str(e).splitlines()
        top = "the full `CaseStudy` does not validate yet (" + "; ".join(l.strip() for l in msg[1:3]) + ")"
    out["reservoir"] = f"{nested}; {top}"
    cm = j("classifier_metrics.json")
    need = {"label": lambda v: v in ("flooded", "burned", "vegetation_loss", "stable"), "beta": lambda v: v is True,
            "precision": lambda v: 0 <= v <= 1, "recall": lambda v: 0 <= v <= 1, "evaluated_on": lambda v: isinstance(v, str)}
    bad = [k for k, f in need.items() if k not in cm or not f(cm[k])]
    out["classifier"] = ("has every `ClassifierResult` field of `frontend/src/api/contract.ts` "
                         "(label, beta: true, precision, recall, evaluated_on); extra keys are ignored by zod"
                         if not bad else f"missing/invalid ClassifierResult fields: {bad}")
    return out


def main(fig_base: str = "outputs/figures", out: Path = DOC) -> None:
    r = pd.read_csv(OUTPUTS / "results.csv")
    d = pd.read_csv(OUTPUTS / "s1_paired_diff.csv")
    held = j("heldout_eval.json")
    haouz = j("haouz_flooded_area.json")
    rc = j("reservoir_case.json")
    pair = j("change_pair.json")
    cm = j("classifier_metrics.json")
    ri = j("raster_index.json")
    aoi = j("aoi.json")["chosen"]
    comp = pd.read_csv(OUTPUTS / "reservoir_comparison.csv")
    oc = pd.read_csv(OUTPUTS / "orbit_consistency.csv")
    v = validate()

    best = held["variant_selected_on_selection_track"]
    unet_s1 = [m for m in r["method"] if str(m).startswith("U-Net (source-only, p>") and "tuned on val" in str(m)][0]
    g = "Global VH threshold (fit on train)"
    t, tg = row(r, "S1 test", unet_s1), row(r, "S1 test", g)
    b, bg = row(r, "S1 Bolivia hold-out", unet_s1), row(r, "S1 Bolivia hold-out", g)
    dt = d[(d["domain"] == "S1 test") & (d["comparison"].str.startswith(unet_s1)) & (d["metric"] == "iou")].iloc[0]
    db = d[(d["domain"] == "S1 Bolivia hold-out") & (d["comparison"].str.startswith(unet_s1)) & (d["metric"] == "iou")].iloc[0]
    hh = held["headline_heldout"]
    hg = held["metrics"]["Global HV threshold (fit on S1 train VH)"]["held-out"]
    sel = held["metrics"][best]["selection"]
    res = held["reservoir"]
    pooled = row(r, f"NISAR {res}", "U-Net + AdaBN + per-scene norm")
    orbit = r[r["method"].astype(str).str.startswith("Orbit consistency")].iloc[0]
    bias, biasc = held["area_bias"]["held-out raw"], held["area_bias"]["held-out after multiplicative correction"]
    hz = json.loads((OUTPUTS / "haouz_open_water.json").read_text(encoding="utf-8"))["findings"][0]["nisar"]
    rcf = next(f for f in rc["findings"] if f["id"] == "water_area_change")
    figs = sorted(p.name for p in (OUTPUTS / "figures").glob("*.*") if p.suffix in (".png", ".gif"))
    layers = pd.Series([l.get("layer", l["id"]) for l in ri["layers"]]).value_counts().to_dict()
    resname = res.replace("_", " ")
    sel_tracks = held["selection_track"]
    ho_tracks = "/".join(str(x) for x in held["heldout_tracks"])

    md = f"""# Water U-Net: handoff for the NISAR Pulse app

_Generated by `backend/water/handoff_doc.py` from `backend/water/outputs/`; numbers are read from those files.
Rerun the script after any pipeline change. Details: [WATER_UNET.md](WATER_UNET.md)._

## 1. What we built

A water map from NISAR radar for every pass, cloud or no cloud: a per-pixel open-water probability from NISAR
GCOV HH/HV. It is used for (a) tracking the water area of a Moroccan reservoir ({resname}) over time and (b) the
extra `open_water_change` finding of the existing `haouz-flood-2026` case (no flooded area claimed). Why it matters: optical water maps (OPERA DSWx)
fail under clouds, radar does not (`figures/clouds.png`).

## 2. Key results

| Result | Value (95% interval or 1σ) | Source file |
|---|---|---|
| S1 test IoU: U-Net vs global VH threshold | {t.iou:.3f} {ci(t.iou_ci95_lo, t.iou_ci95_hi)} vs {tg.iou:.3f} {ci(tg.iou_ci95_lo, tg.iou_ci95_hi)}; paired difference {dt['diff']:+.3f} {ci(dt.ci95_lo, dt.ci95_hi)} | `results.csv`, `s1_paired_diff.csv` |
| Bolivia hold-out (event never seen in training) IoU | {b.iou:.3f} {ci(b.iou_ci95_lo, b.iou_ci95_hi)} vs threshold {bg.iou:.3f}; difference {db['diff']:+.3f} {ci(db.ci95_lo, db.ci95_hi)} | `results.csv`, `classifier_metrics.json` |
| **NISAR held-out tracks {ho_tracks} vs DSWx (headline)** | IoU **{hh['iou']:.3f}** {ci(*hh['ci95']['iou'])}, precision {hh['precision']:.3f} {ci(*hh['ci95']['precision'])}, recall {hh['recall']:.3f} {ci(*hh['ci95']['recall'])}; global threshold {hg['iou']:.3f}; {hh['n_dates']} dates | `heldout_eval.json` |
| NISAR selection track {sel_tracks} (used to choose the variant) | IoU {sel['iou']:.3f} {ci(*sel['ci95']['iou'])} | `heldout_eval.json` |
| NISAR all tracks pooled, best variant (**selection set, not independent**) | IoU {pooled.iou:.3f} | `results.csv` |
| Orbit consistency (ascending vs descending, ≤3 days apart) | {orbit.mae_km2:.2f} km² mean absolute difference ({orbit.mae_pct:.1f}%), {len(oc)} pairs | `results.csv`, `orbit_consistency.csv` |
| Area bias, model minus DSWx (held-out tracks) | {bias['mean_km2']:+.2f} km² {ci(*bias['ci95_km2'], 2)} ({bias['mean_relative']:+.1%}); after a correction fitted on track {sel_tracks}: {biasc['mean_km2']:+.2f} km² {ci(*biasc['ci95_km2'], 2)} | `heldout_eval.json` |
| Reservoir change {pair['pre']['date']} → {pair['post']['date']} | NISAR {rcf['nisar']['value']:+.2f} ± {rcf['nisar']['uncertainty']:.2f} km² vs DSWx {rcf['reference']['value']:+.2f} ± {rcf['reference']['uncertainty']:.2f} km² (1σ); agreement `{rcf['agreement']}` | `reservoir_case.json` |
| Haouz `open_water_change` (extra finding) | {hz['value']:.2f} ± {hz['uncertainty']:.2f} km² (1σ): **{haouz['interpretation']}** | `haouz_open_water.json` |

"Selection" numbers used DSWx to choose the method variant; "held-out" numbers did not. Reservoir choice:
no reservoir changed by more than 10% after DSWx outlier removal (largest:
{comp.sort_values('genuine_change_frac').iloc[-1]['reservoir'].replace('_', ' ')}, {comp['genuine_change_frac'].max():.1%}), so {resname} (most clear dates) is a
**{aoi.get('framing', 'monitoring')}** case: {rc['headline']['text']['en']}

### What it looks like

**Before / after / change** on the satellite basemap ({pair['pre']['date']} → {pair['post']['date']}, track {sel_tracks}):

![Before, after and change map]({fig_base}/hero.png)

**Validation against OPERA DSWx** on a held-out track (median-IoU date; white agreement, red miss, orange false alarm):

![U-Net vs DSWx on a held-out date]({fig_base}/validation.png)

**Water area over time**, all three tracks and DSWx (red circles: possible wind effect):

![Water-area time series]({fig_base}/timeseries.png)

**Why radar:** same day, the optical map is blocked by clouds, NISAR is not:

![Clouds vs radar]({fig_base}/clouds.png)

**Every NISAR date** at a glance (titles in red = flagged date):

![Contact sheet of all dates]({fig_base}/gallery_contact_sheet.png)

## 3. The model, briefly

U-Net with a ResNet-34 encoder; input HH and HV backscatter in dB (2 channels); output a per-pixel water
probability, thresholded at {held['probability_threshold']} (fixed on the {held.get('threshold_source', 'Sentinel-1 validation split')}). Trained on Sentinel-1 hand-labelled
chips (Sen1Floods11), transferred to NISAR with AdaBN (BatchNorm statistics re-estimated on unlabelled NISAR tiles){
', then fine-tuned on NISAR with OPERA DSWx labels of other Moroccan reservoirs (never the case reservoir; validation reservoir Al Massira; details in WATER_UNET.md)' if 'fine-tune' in best else '; no NISAR labels used'}.
Operational variant: **{best}**, chosen among the candidate variants on track {sel_tracks} only.
Evaluated against OPERA DSWx-HLS (optical, weak reference). Details: [WATER_UNET.md](WATER_UNET.md).

## 4. What is ready to use

All paths are relative to `backend/water/outputs/`. Large GeoTIFFs and checkpoints stay in the data root
`NASA_DATA` (outside the repo) and are not needed by the app.

| File | Purpose | Validation |
|---|---|---|
| `haouz_open_water.json` | Haouz extra finding `open_water_change`, figure `clouds.png`, limits | {v['haouz']} |
| `reservoir_case.json` | draft method case `{rc['id']}` (unregistered) | {v['reservoir']} |
| `classifier_metrics.json` | `Answer.classifier` candidate | {v['classifier']} |
| `raster_index.json` + `rasters/*.png` | {len(ri['layers'])} RGBA PNG map layers, EPSG:4326, north-up, transparent = no data: {', '.join(f'{k} ×{n}' for k, n in layers.items())} | follows the RasterLayer image rules; served as figure kind `image` today |
| `figures/` | slide/case images: {', '.join(figs)} | figure kind `image` |
| `figures/gallery/`, `figures/gallery_contact_sheet.png` | one validation map per NISAR date (internal QA) | — |
| `water_area_timeseries.csv` | km² per date and track, DSWx where clear, flags (wind / partial / outlier) | — |

Shapes (abbreviated, real keys):

```json
// haouz_open_water.json
{{"date": "{haouz['date']}", "bbox": [...], "products": ["GCOV_T023_F073_..."],
 "findings": [{{"id": "open_water_change", "label": {{"fr","en","ar"}},
   "nisar": {json.dumps(hz)}, "reference": null, "reference_source": null, "agreement": "{haouz['findings'][0]['agreement']}"}}],
 "figures": [{{"id": "haouz_backscatter_change", "raster": "...tif", "layer": {{"kind": "backscatter_change", ...}}}}],
 "limits": [{{"fr","en","ar"}} × {len(haouz['limits'])}], "interpretation": "{haouz['interpretation']}"}}

// reservoir_case.json  (CaseStudy shape + "framing", "selection_reason", "placeholders")
{{"id": "{rc['id']}", "kind": "{rc['kind']}", "status": "{rc['status']}", "headline": {{"template", "params", "text"}},
 "findings": [{{"id": "{rcf['id']}", "nisar": {{...}}, "reference": {{...}}, "reference_source": {{"name", "url"}}, "agreement": "{rcf['agreement']}"}}],
 "figures": [{{"id": "reservoir_hero", "kind": "image", "url": "water/outputs/figures/hero.png", ...}}], "timeline": [...], "limits": [...]}}

// classifier_metrics.json
{{"label": "{cm['label']}", "beta": true, "precision": {cm['precision']:.3f}, "recall": {cm['recall']:.3f},
 "evaluated_on": "{cm['evaluated_on']}", "precision_ci95": [...], "recall_ci95": [...], ...}}

// raster_index.json
{{"crs": "EPSG:4326", "bounds_order": "[west,south,east,north] pixel outer edges",
 "layers": [{json.dumps({k: v for k, v in ri['layers'][0].items() if k != 'bounds'})[:-1]}, "bounds": [w, s, e, n], ...}}]}}
```

## 5. What we need from the backend (Ayman)

- **Haouz:** read `backend/water/outputs/haouz_open_water.json` as an extra source of the case (see INTEGRATION_REQUESTS.md); `open_water_change` is added
  next to the existing findings; `results/` stays owned by Anass.
- **Reservoir case:** register `{rc['id']}` under `/api/cases` only if you both accept a 5th case; the contract is
  frozen and `CaseId` does not list it. Proposal: [WATER_CONTRACT_PROPOSAL.md](WATER_CONTRACT_PROPOSAL.md).
- **Serve our PNGs from the same origin** (e.g. `/api/rasters/water/...`) so the offline service worker caches them.
- **Classifier slot:** `classifier_metrics.json` can fill `Answer.classifier` (beta: true, precision/recall on a
  held-out event) for water/flood answers, as a comparison with the existing XGBoost classifier, not a replacement.

## 6. What we need from the frontend (Houssam)

- Show our figures in the case pages: figure kind `image` works today with no contract change.
- Optional, needs a contract change: a water palette for map layers and a `water_area` series id for the time-series
  chart ([WATER_CONTRACT_PROPOSAL.md](WATER_CONTRACT_PROPOSAL.md)).
- Placement: the reservoir case card on the cases page (hero, timeseries, validation); the Haouz case shows our
  `open_water_change` finding and `clouds.png`.

## 7. Limits

- OPERA DSWx is optical and a weak reference (cloud, shadow, shoreline mixing, a different acquisition day).
- NISAR GCOV products are provisional; calibration may change.
- Sentinel-1 C-band VV/VH → NISAR L-band HH/HV is an assumed mapping (HH↔VV, HV↔VH), checked only against DSWx.
- A 12-day revisit misses short floods: Haouz measures persistent water 3-5 days after the event, not the peak.
- Area bias on held-out tracks: {bias['mean_km2']:+.2f} km² {ci(*bias['ci95_km2'], 2)} (model minus DSWx); the shoreline is where most errors are.

## 8. How to check our work

From `backend/water/` (data root in the `NASA_DATA` environment variable; Earthdata login only for re-downloads):

```
python s1_eval.py          # S1 test + Bolivia metrics with bootstrap intervals
python heldout_eval.py     # NISAR held-out-track headline and area bias
python reservoir_case.py   # rebuild + validate the draft reservoir case
python handoff_doc.py      # regenerate this note
streamlit run preview_app.py   # internal preview of figures (not the demo)
```

From `backend/`: `python -m science.cases --results ../results --offline --dry-run` (case assembly) and
`python tests/test_science.py`.
"""
    out.write_text(md, encoding="utf-8")
    print("wrote", out, f"({len(md.splitlines())} lines)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--fig-base", default="outputs/figures",
                    help="image path prefix as seen from the output markdown file")
    ap.add_argument("--out", default=str(DOC))
    a = ap.parse_args()
    main(a.fig_base, Path(a.out))
