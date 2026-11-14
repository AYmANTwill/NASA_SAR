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
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

import catalog
import raster
from config import LOS_SIGN
from recipes import decompose, displacement
from science import ffm_sign, noise_cov, sign_decision, usgs
from science.case_models import Finding, Measurement, agreement
from science.invert_fault import N_BOOT, Track, invert, predict

log = logging.getLogger(__name__)
COH_MIN = 0.3
N_TARGET = 1500
MIN_VALID_SHARE = 0.5        # a block is kept when at least half of its pixels are valid
MIN_COMPONENT_BLOCKS = 20    # a connected component needs this many blocks to get its own offset
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


def block_size(n_valid: int, n_target: int = N_TARGET) -> int:
    """Side (pixels) of the square blocks that leave about n_target valid blocks."""
    return max(1, int(math.ceil(math.sqrt(n_valid / n_target))))


def block_means(values: np.ndarray, n_target: int = N_TARGET,
                block: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(row centres, column centres, block means) of square blocks sized to leave about n_target valid blocks
    (or of side `block` pixels when given)."""
    valid = np.isfinite(values)
    n_valid = int(valid.sum())
    if n_valid == 0:
        return np.array([]), np.array([]), np.array([])
    b = block or block_size(n_valid, n_target)
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


def component_blocks(disp: np.ndarray, cc: np.ndarray | None, n_target: int = N_TARGET):
    """Block means computed inside each connected component (a block never mixes two components) and the index of
    its component, so that the inversion fits one offset per component (2π jumps between components).
    Components with fewer than MIN_COMPONENT_BLOCKS blocks are dropped; the largest one is always kept.
    Returns (rows, cols, values, comp or None, note)."""
    if cc is None or cc.shape != disp.shape:
        rows, cols, vals = block_means(disp, n_target)
        why = "no connected-component layer" if cc is None else f"connected-component layer shape {cc.shape} != {disp.shape}"
        return rows, cols, vals, None, f"{why}: unwrapping jumps between components are not handled"
    valid = np.isfinite(disp) & np.isfinite(cc) & (cc > 0)
    empty = np.array([])
    if not valid.any():
        return empty, empty, empty, None, "no valid pixel in any connected component"
    labels, counts = np.unique(cc[valid], return_counts=True)
    b = block_size(int(valid.sum()), n_target)
    parts, dropped, kept_px = [], 0, 0
    for label, n_px in sorted(zip(labels, counts), key=lambda lc: -lc[1]):
        r, c, v = block_means(np.where(valid & (cc == label), disp, np.nan), block=b)
        if parts and v.size < MIN_COMPONENT_BLOCKS:
            dropped += 1
            continue
        parts.append((r, c, v))
        kept_px += int(n_px)
    comp = np.concatenate([np.full(v.size, i) for i, (_, _, v) in enumerate(parts)])
    rows, cols, vals = (np.concatenate([p[j] for p in parts]) for j in range(3))
    note = (f"{len(parts)} connected component(s) kept with one offset each ({kept_px / counts.sum():.0%} of the valid "
            f"pixels); {dropped} smaller component(s) (< {MIN_COMPONENT_BLOCKS} blocks) dropped")
    return rows, cols, vals, comp, note


def track_from_product(p, lat0: float, lon0: float, n_target: int = N_TARGET) -> Track | None:
    disp, coh, prof, notes, report = displacement.los_cm_full(p, corrections=("iono",))
    disp = np.where(coh >= COH_MIN, disp, np.nan)
    cc = raster.read(p.files["conncomp"])[0] if "conncomp" in p.files else None
    rows, cols, vals, comp, cc_note = component_blocks(disp, cc, n_target)
    if vals.size == 0:
        log.warning("%s: no valid pixel after masking", p.id)
        return None
    x, y = prof["transform"] * (cols, rows)
    lon, lat = Transformer.from_crs(prof["crs"], 4326, always_xy=True).transform(x, y)
    east, north = local_km(lat, lon, lat0, lon0)
    vec, vec_source = decompose.los_vector(p)
    track_notes = list(notes) + [f"LOS vector: track mean ({vec_source})", cc_note]
    if not report.get("iono", {}).get("applied"):
        track_notes.append(f"ionospheric correction NOT applied: {report.get('iono', {}).get('reason', 'unknown')}")
    return Track(p.id, east, north, vals, np.tile(vec, (vals.size, 1)), tuple(track_notes), comp=comp)


def with_noise_models(tracks: list[Track], pairs: list, origin: str, lat0: float, lon0: float,
                      n_target: int = N_TARGET) -> tuple[list[Track], dict]:
    """Attaches to each co-seismic track the noise covariance estimated on the latest pre-event pair of the same
    geometry (track, direction, frame), processed the same way. Returns (tracks, {track: model summary or reason})."""
    before = catalog.before(catalog.find(lat0, lon0, "GUNW"), origin)
    out, report = [], {}
    for t, p in zip(tracks, pairs):
        same = [q for q in before if (q.track, q.direction, q.frame) == (p.track, p.direction, p.frame)]
        if not same:
            report[t.name] = {"status": "no pre-event pair of the same geometry"}
            out.append(t)
            continue
        q = max(same, key=lambda x: x.sec)
        try:
            pre = track_from_product(q, lat0, lon0, n_target)
            if pre is None:
                raise ValueError("no valid pixel")
            nm = noise_cov.from_points(pre.east, pre.north, pre.los, q.id, pre.comp)
            out.append(replace(t, notes=t.notes + (f"noise covariance from {q.id}",), chol=nm.cholesky(t.east, t.north)))
            report[t.name] = {"status": "ok", **nm.summary()}
        except (ValueError, np.linalg.LinAlgError) as exc:
            log.warning("%s: noise model from %s failed: %s", t.name, q.id, exc)
            report[t.name] = {"status": f"failed: {exc}", "pre_event_pair": q.id}
            out.append(t)
    return out, report


def coseismic_tracks(ev: usgs.UsgsEvent, n_target: int = N_TARGET,
                     noise: bool = True) -> tuple[list[Track], list[str], dict]:
    """(tracks, pair ids, noise-model report). noise=True: noise covariance from pre-event pairs when available."""
    origin = datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    pairs = catalog.straddling(catalog.find(ev.lat, ev.lon, "GUNW"), origin)
    kept = [(p, t) for p, t in ((p, track_from_product(p, ev.lat, ev.lon, n_target)) for p in pairs) if t is not None]
    tracks = [t for _, t in kept]
    report = {}
    if noise and kept:
        tracks, report = with_noise_models(tracks, [p for p, _ in kept], origin, ev.lat, ev.lon, n_target)
    return tracks, [p.id for p in pairs], report


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
    "noise_modelled": {
        "fr": "Incertitudes par Monte-Carlo avec le bruit corrélé mesuré sur une paire avant le séisme (variogramme). "
              "Elles n'incluent pas l'erreur de modèle (glissement uniforme, module de cisaillement de 30 GPa).",
        "en": "Uncertainties by Monte Carlo with the correlated noise measured on a pre-event pair (variogram). "
              "They do not include the model error (uniform slip, 30 GPa shear modulus).",
        "ar": "الشكوك بطريقة مونت كارلو مع الضجيج المترابط المقاس على زوج قبل الزلزال (مخطط التباين). "
              "لا تشمل خطأ النموذج (انزلاق منتظم، معامل قص 30 جيغاباسكال)."},
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
        n_target: int = N_TARGET, ffm: "ffm_sign.FiniteFault | None" = None, noise: bool = True) -> dict:
    """ffm: finite-fault model for the independent sign test (USGS model by default for us6000u18k).
    noise: estimate the noise covariance from pre-event pairs (plan_validation.json part 2) when present."""
    if ffm is None and event_id == "us6000u18k":
        ffm = ffm_sign.USGS_FFM_PANAMA
    timing = {}
    t0 = time.perf_counter()
    ev = usgs.event(event_id)
    tracks, pair_ids, noise_report = coseismic_tracks(ev, n_target, noise)
    modelled = bool(tracks) and all(t.chol is not None for t in tracks)
    timing["load_tracks_s"] = round(time.perf_counter() - t0, 2)
    base = {"case": case_id, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "event": {"id": ev.id, "url": ev.url, "lat": ev.lat, "lon": ev.lon, "depth_km": ev.depth_km,
                      "time_utc": datetime.fromtimestamp(ev.time_ms / 1000, tz=timezone.utc).isoformat(),
                      "magnitude": ev.magnitude, "magnitude_type": ev.magnitude_type, "mt_source": ev.mt_source,
                      "planes": [vars(p) for p in ev.planes]},
            "pairs": pair_ids, "los_sign": LOS_SIGN, "los_sign_verified": bool(LOS_SIGN_VERIFIED)}
    base["noise_models"] = noise_report
    limits = ([LIMITS["uniform"], LIMITS["noise_modelled"] if modelled else LIMITS["noise"], LIMITS["losvec"]]
              + ([] if LOS_SIGN_VERIFIED else [LIMITS["sign"]]))
    if not tracks:
        out = {**base, "stable": False, "unstable_reasons": ["no co-seismic GUNW pair with valid pixels"],
               "findings": [], "figures": [], "limits": limits}
    else:
        t0 = time.perf_counter()
        result, fits = invert(tracks, ev.planes, n_boot)
        timing["inversion_s"] = round(time.perf_counter() - t0, 2)
        best = result["planes"][result["best_plane"]]
        sign = None
        if ffm:
            t0 = time.perf_counter()
            plus = tracks if LOS_SIGN > 0 else sign_decision.flipped(tracks)
            sign = sign_decision.decide(plus, ev.planes, ev.lat, ev.lon, ffm,
                                        fits_plus=fits if LOS_SIGN > 0 else None,
                                        fits_minus=fits if LOS_SIGN < 0 else None)
            sign = {"case": case_id, "event": ev.id, "los_sign_env": LOS_SIGN, "pairs": pair_ids, **sign}
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{case_id}_sign.json").write_text(json.dumps(sign, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
            timing["sign_decision_s"] = round(time.perf_counter() - t0, 2)
        fig_path = out_dir / f"{case_id}_fit.png"
        figure(tracks, fits, result["best_plane"], fig_path)
        out = {**base, **result, "sign_check": sign, "findings": findings_from(best, ev) if result["stable"] else [],
               "figures": [{"id": "fault_fit", "path": fig_path.name, "kind": "image"}], "limits": limits}
    out["timing"] = timing
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
    ap.add_argument("--ffm-top-depth", type=float, default=0.0, help="top depth (km) of the USGS finite-fault model")
    ap.add_argument("--no-noise-cov", action="store_true",
                    help="do not use pre-event pairs for the noise covariance (independent points, lower-bound sigma)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")     # Windows consoles default to cp1252
    ffm = None
    if a.event == "us6000u18k":
        from dataclasses import replace
        ffm = replace(ffm_sign.USGS_FFM_PANAMA, top_depth_km=a.ffm_top_depth)
    out = run(a.event, a.case, a.boot, a.out_dir, a.points, ffm, noise=not a.no_noise_cov)
    for name, nm in out.get("noise_models", {}).items():
        print(f"noise model {name}: {nm['status']}" + (f", sigma {nm['sigma_cm']:.2f} cm, range {nm['range_km']:.1f} km"
                                                       if nm["status"] == "ok" else ""))
    print(f"NISAR_LOS_SIGN = {out['los_sign']}")
    print(json.dumps({k: out.get(k) for k in ("pairs", "stable", "unstable_reasons", "best_plane")}, indent=1))
    if out.get("planes"):
        print("variance reduction per track:", json.dumps(
            out["planes"][out["best_plane"]]["variance_reduction_per_track"], indent=1))
    sc = out.get("sign_check")
    if sc:
        print(f"LOS sign decision: {sc['decision']}   (written to {a.out_dir / (a.case + '_sign.json')})")
        for name, v in sc["ffm"]["per_track"].items():
            print(f"  FFM {name}: k = {v['k']:.3g} +/- {v['sigma_k']:.2g} ({v['k_over_sigma'] or 0:+.1f} sigma), "
                  f"r = {v['partial_r']:.2f} -> {v['verdict']}")
        inv = sc["inversion"]
        print(f"  inversion VR +1 = {inv['variance_reduction_plus1']:.3f}, -1 = {inv['variance_reduction_minus1']:.3f}")
        print("  criteria +1:", sc["criteria_plus1"])
    print_timing(out, a.boot)


def print_timing(out: dict, n_boot: int) -> None:
    """Stage times and the projected duration of a 50-run bootstrap (to time a run made with --boot 5)."""
    tm = out.get("timing", {})
    print("timing:", ", ".join(f"{k} {v} s" for k, v in tm.items()))
    for i, p in enumerate(out.get("planes", [])):
        t = p.get("timing", {})
        per = t.get("per_bootstrap_run_s")
        proj = f", --boot {N_BOOT} would take ~{t['fit_s'] + per * N_BOOT:.0f} s" if per else ""
        print(f"  plane {i + 1}: fit {t.get('fit_s')} s, bootstrap {t.get('bootstrap_s')} s "
              f"({n_boot} runs, {per} s/run){proj}")
    for f in out["findings"]:
        print(f"{f['id']}: {f['nisar']['value']} ± {f['nisar']['uncertainty']} {f['nisar']['unit']} ({f['agreement']})")


if __name__ == "__main__":
    main()
