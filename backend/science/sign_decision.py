"""Decision on the LOS sign (NISAR_LOS_SIGN) for the Panama earthquake, written as results-ready JSON.

Everything is evaluated in the documented +1 convention (positive = toward the satellite), whatever NISAR_LOS_SIGN
is set to: the -1 hypothesis is the same data with the opposite sign.

+1 is accepted only if all three hold:
1. USGS finite-fault forward model (science.ffm_sign): k > 0 at > 3σ on at least 3 tracks, none significantly < 0;
2. the inversion fits clearly better with +1 than with -1: variance reduction(+1) - VR(-1) >= 0.10;
3. with +1, the best nodal plane is the left-lateral one (USGS plane 288/66/-17).
-1 is accepted by the mirrored rule. Anything else is "undecided".
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from science import ffm_sign
from science.invert_fault import STARTS, PlaneFit, Track, fit_plane
from science.usgs import Plane

MIN_TRACKS = 3
VR_MARGIN = 0.10
EXPECTED_PLANE = Plane(288.32, 66.22, -16.68)     # USGS us6000u18k nodal plane 2 (left-lateral)
STRIKE_DIP_TOL_DEG = 15.0
RAKE_TOL_DEG = 30.0
RULE = ("+1 accepted only if: USGS finite-fault model k > 0 at > 3 sigma on >= 3 tracks with none significantly < 0; "
        f"AND variance reduction(+1) - VR(-1) >= {VR_MARGIN}; AND the best plane with +1 is the left-lateral plane "
        "288/66/-17. -1 by the mirrored rule. Otherwise undecided.")


def _angle(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def plane_matches(p: Plane, ref: Plane = EXPECTED_PLANE) -> bool:
    return (_angle(p.strike, ref.strike) <= STRIKE_DIP_TOL_DEG and abs(p.dip - ref.dip) <= STRIKE_DIP_TOL_DEG
            and _angle(p.rake, ref.rake) <= RAKE_TOL_DEG)


def flipped(tracks: list[Track]) -> list[Track]:
    return [replace(t, los=-t.los) for t in tracks]      # keeps the noise model and the components


def _best(fits: list[PlaneFit]) -> PlaneFit:
    return fits[int(np.argmin([f.rms_cm for f in fits]))]


def decide(tracks_plus: list[Track], planes: tuple[Plane, ...], lat0: float, lon0: float,
           ffm: ffm_sign.FiniteFault = ffm_sign.USGS_FFM_PANAMA, fits_plus: list[PlaneFit] | None = None,
           fits_minus: list[PlaneFit] | None = None, starts=STARTS) -> dict:
    """tracks_plus: LOS in the +1 convention. fits_*: fits already computed on the same planes, reused.
    starts: multi-start points of the refits (fewer only to keep the tests fast)."""
    ffm_res = ffm_sign.sign_check(tracks_plus, lat0, lon0, 1.0, ffm)
    verdicts = [v["verdict"] for v in ffm_res["per_track"].values()]
    n_pos, n_neg = verdicts.count("consistent"), verdicts.count("flipped")
    fits_plus = fits_plus or [fit_plane(tracks_plus, p, starts) for p in planes]
    fits_minus = fits_minus or [fit_plane(flipped(tracks_plus), p, starts) for p in planes]
    bp, bm = _best(fits_plus), _best(fits_minus)
    vr_p, vr_m = bp.variance_reduction, bm.variance_reduction
    plus = {"ffm_k_positive_on_3_tracks_none_negative": n_pos >= MIN_TRACKS and n_neg == 0,
            "inversion_fits_clearly_better": vr_p - vr_m >= VR_MARGIN,
            "best_plane_is_left_lateral": plane_matches(bp.plane)}
    minus = {"ffm_k_negative_on_3_tracks_none_positive": n_neg >= MIN_TRACKS and n_pos == 0,
             "inversion_fits_clearly_better": vr_m - vr_p >= VR_MARGIN,
             "best_plane_is_left_lateral": plane_matches(bm.plane)}
    decision = "+1" if all(plus.values()) else "-1" if all(minus.values()) else "undecided"
    notes = [f"only {len(tracks_plus)} track(s): the rule needs >= {MIN_TRACKS}"] if len(tracks_plus) < MIN_TRACKS else []
    per = {name: {"k": v["k"], "sigma_k": v["sigma_k"],
                  "k_over_sigma": v["k"] / v["sigma_k"] if v["sigma_k"] else None,
                  "partial_r": v["partial_r"], "verdict": v["verdict"]}
           for name, v in ffm_res["per_track"].items()}
    return {
        "decision": decision, "rule": RULE, "notes": notes,
        "criteria_plus1": plus, "criteria_minus1": minus,
        "ffm": {"model": ffm_res["model"], "n_tracks": len(verdicts), "n_k_positive_3sigma": n_pos,
                "n_k_negative_3sigma": n_neg, "per_track": per},
        "inversion": {"variance_reduction_plus1": vr_p, "variance_reduction_minus1": vr_m,
                      "rms_cm_plus1": bp.rms_cm, "rms_cm_minus1": bm.rms_cm,
                      "best_plane_plus1": vars(bp.plane), "best_plane_minus1": vars(bm.plane)},
        "expected_plane": vars(EXPECTED_PLANE),
        "convention": "+1 = positive toward the satellite (documented NISAR convention)",
    }
