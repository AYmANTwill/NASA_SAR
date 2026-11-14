"""Runs the fault inversion on the co-seismic GUNW pairs of an earthquake and writes cases/out/<case>.json + a PNG.

    python -m science.panama_fault                       # us6000u18k -> cases/out/panama-2026.json
    python -m science.panama_fault --event <usgs id> --case <case id> --boot 50

Inputs:
- GUNW pairs from the catalog that cover the epicentre and straddle the USGS origin time;
- LOS displacement from recipes/displacement.py with the ionospheric correction requested;
- pixels with coherence < 0.3 masked;
- block means down to about 1500 points per track.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

import catalog
from config import LOS_SIGN
from recipes import decompose, displacement
from science import usgs
from science.case_models import Finding, Measurement, agreement
from science.invert_fault import N_BOOT, Track, invert, predict

log = logging.getLogger(__name__)
COH_MIN = 0.3
N_TARGET = 1500
MIN_VALID_SHARE = 0.5        # a block is kept when at least half of its pixels are valid
MW_REF_SIGMA = 0.1           # USGS gives no magnitude uncertainty
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQ = 111.320
OUT_DIR = Path(__file__).resolve().parents[1] / "cases" / "out"
try:
    from config import LOS_SIGN_VERIFIED
except ImportError:          # older config
    LOS_SIGN_VERIFIED = False


def local_km(lat, lon, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    return ((np.asarray(lon) - lon0) * KM_PER_DEG_LON_EQ * math.cos(math.radians(lat0)),
            (np.asarray(lat) - lat0) * KM_PER_DEG_LAT)


def block_means(values: np.ndarray, n_target: int = N_TARGET) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(row centres, column centres, block means) of square blocks sized to leave about n_target valid blocks."""
    valid = np.isfinite(values)
    n_valid = int(valid.sum())
    if n_valid == 0:
        return np.array([]), np.array([]), np.array([])
    b = max(1, int(math.ceil(math.sqrt(n_valid / n_target))))
    h, w = values.shape
    H, W = math.ceil(h / b) * b, math.ceil(w / b) * b
    pad = np.full((H, W), np.nan, dtype="float64")
    pad[:h, :w] = values
    blocks = pad.reshape(H // b, b, W // b, b)
    count = np.isfinite(blocks).sum(axis=(1, 3))
    mean = np.nansum(blocks, axis=(1, 3)) / np.where(count > 0, count, 1)
    keep = count >= MIN_VALID_SHARE * b * b
    rows, cols = np.nonzero(keep)
    return rows * b + b / 2.0, cols * b + b / 2.0, mean[keep]


def track_from_product(p, lat0: float, lon0: float, n_target: int = N_TARGET) -> Track | None:
    disp, coh, prof, notes, report = displacement.los_cm_full(p, corrections=("iono",))
    disp = np.where(coh >= COH_MIN, disp, np.nan)
    rows, cols, vals = block_means(disp, n_target)
    if vals.size == 0:
        log.warning("%s: no valid pixel after masking", p.id)
        return None
    x, y = prof["transform"] * (cols, rows)
    lon, lat = Transformer.from_crs(prof["crs"], 4326, always_xy=True).transform(x, y)
    east, north = local_km(lat, lon, lat0, lon0)
    vec, vec_source = decompose.los_vector(p)
    track_notes = list(notes) + [f"LOS vector: track mean ({vec_source})"]
    if not report.get("iono", {}).get("applied"):
        track_notes.append(f"ionospheric correction NOT applied: {report.get('iono', {}).get('reason', 'unknown')}")
    return Track(p.id, east, north, vals, np.tile(vec, (vals.size, 1)), tuple(track_notes))


def coseismic_tracks(ev: usgs.UsgsEvent, n_target: int = N_TARGET) -> tuple[list[Track], list[str]]:
    origin = datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    pairs = catalog.straddling(catalog.find(ev.lat, ev.lon, "GUNW"), origin)
    tracks = [t for t in (track_from_product(p, ev.lat, ev.lon, n_target) for p in pairs) if t is not None]
    return tracks, [p.id for p in pairs]


# ---------------------------------------------------------------- output
LIMITS = {
    "uniform": {"fr": "Glissement uniforme sur un seul rectangle : la vraie rupture est hétérogène ; longueur, largeur "
                      "et glissement se compensent, la magnitude est mieux contrainte que chacun d'eux.",
                "en": "Uniform slip on a single rectangle: the real rupture is heterogeneous; length, width and slip "
                      "trade off, the magnitude is better constrained than each of them.",
                "ar": "انزلاق منتظم على مستطيل واحد: التمزق الحقيقي غير متجانس؛ الطول والعرض والانزلاق يعوض بعضها "
                      "بعضا، والقدر أفضل تقييدا من كل منها."},
    "noise": {"fr": "Les incertitudes ignorent le bruit corrélé dans l'espace (atmosphère) : ce sont des minorants.",
              "en": "The uncertainties ignore spatially correlated noise (atmosphere): they are lower bounds.",
              "ar": "لا تأخذ الشكوك في الحسبان الضجيج المترابط مكانيا (الغلاف الجوي): فهي حدود دنيا."},
    "losvec": {"fr": "Direction de visée moyenne par trace : l'incidence varie le long de la fauchée.",
               "en": "One mean line-of-sight direction per track: the incidence angle varies across the swath.",
               "ar": "اتجاه نظر متوسط لكل مسار: تتغير زاوية السقوط عبر عرض المسح."},
    "sign": {"fr": "Le signe de la ligne de visée n'est pas encore vérifié (NISAR_LOS_SIGN_VERIFIED).",
             "en": "The line-of-sight sign is not verified yet (NISAR_LOS_SIGN_VERIFIED).",
             "ar": "لم يتم التحقق بعد من إشارة خط النظر (NISAR_LOS_SIGN_VERIFIED)."},
}


def _m(p: dict, unit: str) -> dict:
    return {"value": round(p["value"], 3), "uncertainty": round(p["sigma"] or 0.0, 3), "unit": unit, "sigma": 1}


def findings_from(best: dict, ev: usgs.UsgsEvent) -> list[dict]:
    """Finding dicts, validated against case_models.Finding. Only called when the fit is stable."""
    prm = best["params"]
    ref = None
    if ev.magnitude_type.lower().startswith("mw"):
        ref = {"value": ev.magnitude, "uncertainty": MW_REF_SIGMA, "unit": "Mw", "sigma": 1}
    mw = {"value": round(best["mw"]["value"], 3), "uncertainty": round(best["mw"]["sigma"], 3), "unit": "Mw",
          "sigma": 1}
    rows = [("mw", ("Magnitude de moment", "Moment magnitude", "قدر العزم"), mw, ref),
            ("length", ("Longueur de rupture", "Rupture length", "طول التمزق"), _m(prm["length_km"], "km"), None),
            ("slip", ("Glissement moyen", "Mean slip", "متوسط الانزلاق"), _m(prm["slip_m"], "m"), None),
            ("top_depth", ("Profondeur du sommet de la faille", "Fault top depth", "عمق أعلى الصدع"),
             _m(prm["top_depth_km"], "km"), None)]
    out = []
    for fid, (fr, en, ar), nisar, reference in rows:
        src = {"name": f"USGS {ev.id} ({ev.magnitude_type})", "url": ev.url} if reference else None
        agr = agreement(Measurement(**nisar), Measurement(**reference) if reference else None)
        f = {"id": fid, "label": {"fr": fr, "en": en, "ar": ar}, "nisar": nisar, "reference": reference,
             "reference_source": src, "agreement": agr}
        out.append(Finding.model_validate(f).model_dump(mode="json"))
    return out


def figure(tracks: list[Track], fits, best: int, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fit = fits[best]
    model = predict(fit.theta, tracks, fit.plane)
    fig, axes = plt.subplots(len(tracks), 3, figsize=(12, 3.8 * len(tracks)), squeeze=False)
    for i, (t, m) in enumerate(zip(tracks, model)):
        lim = float(np.nanpercentile(np.abs(t.los), 98)) or 1.0
        for j, (title, v) in enumerate((("data", t.los), ("model", m), ("residual", t.los - m))):
            ax = axes[i][j]
            sc = ax.scatter(t.east, t.north, c=v, s=6, cmap="RdBu_r", vmin=-lim, vmax=lim)
            short = next((part for part in t.name.split("_") if part.startswith("T")), t.name[:12])
            ax.set_title(f"{short}: {title}", fontsize=9)
            ax.set_aspect("equal")
            ax.set_xlabel("east (km)")
            ax.set_ylabel("north (km)")
        fig.colorbar(sc, ax=axes[i].tolist(), label="LOS (cm, + toward satellite)", shrink=0.8)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def run(event_id: str, case_id: str, n_boot: int = N_BOOT, out_dir: Path = OUT_DIR,
        n_target: int = N_TARGET) -> dict:
    ev = usgs.event(event_id)
    tracks, pair_ids = coseismic_tracks(ev, n_target)
    base = {"case": case_id, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "event": {"id": ev.id, "url": ev.url, "lat": ev.lat, "lon": ev.lon, "depth_km": ev.depth_km,
                      "time_utc": datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).isoformat(),
                      "magnitude": ev.magnitude, "magnitude_type": ev.magnitude_type, "mt_source": ev.mt_source,
                      "planes": [vars(p) for p in ev.planes]},
            "pairs": pair_ids, "los_sign": LOS_SIGN, "los_sign_verified": bool(LOS_SIGN_VERIFIED)}
    limits = [LIMITS["uniform"], LIMITS["noise"], LIMITS["losvec"]] + ([] if LOS_SIGN_VERIFIED else [LIMITS["sign"]])
    if not tracks:
        out = {**base, "stable": False, "unstable_reasons": ["no co-seismic GUNW pair with valid pixels"],
               "findings": [], "figures": [], "limits": limits}
    else:
        result, fits = invert(tracks, ev.planes, n_boot)
        best = result["planes"][result["best_plane"]]
        fig_path = out_dir / f"{case_id}_fit.png"
        figure(tracks, fits, result["best_plane"], fig_path)
        out = {**base, **result, "findings": findings_from(best, ev) if result["stable"] else [],
               "figures": [{"id": "fault_fit", "path": fig_path.name, "kind": "image"}], "limits": limits}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case_id}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="us6000u18k")
    ap.add_argument("--case", default="panama-2026")
    ap.add_argument("--boot", type=int, default=N_BOOT)
    ap.add_argument("--points", type=int, default=N_TARGET, help="target points per track")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    out = run(a.event, a.case, a.boot, a.out_dir, a.points)
    print(json.dumps({k: out.get(k) for k in ("pairs", "stable", "unstable_reasons", "best_plane")}, indent=1))
    for f in out["findings"]:
        print(f"{f['id']}: {f['nisar']['value']} ± {f['nisar']['uncertainty']} {f['nisar']['unit']} ({f['agreement']})")


if __name__ == "__main__":
    main()
