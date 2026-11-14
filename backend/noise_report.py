"""Noise floor of every GUNW with and without the phase corrections (recipes/corrections.py).

For each product the noise floor is the robust sigma (1.4826 x MAD, cm) of the referenced line-of-sight map in the
stable reference area used by the sudden-motion recipe (pixels farther than 25 km from the point; the point is the
frame centre here). It is computed with no correction, with each correction set, and with each single correction
applied with the OPPOSITE sign (a convention check: the right sign should lower the noise, the wrong one raise it).

A correction is "recommended" only if it lowers the median noise floor by at least 5 % AND lowers it on at least two
thirds of the products where it could be applied. Everything else stays OFF by default.

Usage (from backend/):
    python noise_report.py [--data D:\\nisar_data] [--out ..\\results_out] [--match T004] [--limit 20]
Writes <out>/noise_report.json and <out>/noise_report.md (default out: results_out/ at the repo root, git-ignored).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "results_out"
SETS = {"none": (), "iono": ("iono",), "tropo": ("tropo",), "tide": ("tide",), "iono+tropo": ("iono", "tropo"),
        "iono+tropo+tide": ("iono", "tropo", "tide")}
SIGN_TESTS = ("iono", "tropo", "tide")
MIN_REDUCTION = 0.05          # 5 % lower median noise floor
MIN_SHARE = 2 / 3             # ... on at least two thirds of the products


def _r(x, d=3):
    return None if x is None or x != x else round(float(x), d)


def product_noise(p, displacement) -> dict:
    """Noise floor (cm) per correction set and per opposite-sign single correction, for one product."""
    lat, lon = (p.bbox[1] + p.bbox[3]) / 2, (p.bbox[0] + p.bbox[2]) / 2
    row = {"id": p.id, "direction": p.direction, "span_days": p.span_days, "point": [round(lat, 4), round(lon, 4)],
           "sigma_cm": {}, "applied": {}, "reasons": {}, "details": {}, "sigma_cm_opposite_sign": {}}
    for label, names in SETS.items():
        sigma = displacement.referenced(p, lat, lon, names)[3]
        rep = displacement.los_cm_full(p, names)[4]
        row["sigma_cm"][label] = _r(sigma)
        # the ionosphere rule counts as applied when it kept the raw phase on purpose (subtraction did not help)
        row["applied"][label] = all(rep.get(n, {}).get("applied") or rep.get(n, {}).get("kept_raw") for n in names)
        if label == "iono" and "iono" in rep:
            row["iono_decision"] = {k: rep["iono"].get(k) for k in (
                "applied", "kept_raw", "reason", "frame_sigma_raw_rad", "frame_sigma_subtracted_rad",
                "uncertainty_layer", "uncertainty_max_rad", "uncertainty_masked_fraction")}
        for n in names:
            row["reasons"].setdefault(n, rep.get(n, {}).get("reason"))
            for k in ("units", "height_source", "attributes_from", "already_applied_flag", "description"):
                if rep.get(n, {}).get(k) is not None:
                    row["details"].setdefault(n, {})[k] = rep[n][k]
    for n in SIGN_TESTS:
        if row["applied"].get(n):
            row["sigma_cm_opposite_sign"][n] = _r(displacement.referenced(p, lat, lon, (n,), ((n, -1),))[3])
    displacement._los_cm.cache_clear()            # bound the memory: one product's maps at a time
    return row


def summarise(rows: list[dict]) -> dict:
    import numpy as np
    out = {}
    for label in SETS:
        if label == "none":
            continue
        pairs = [(r["sigma_cm"]["none"], r["sigma_cm"][label]) for r in rows
                 if r["applied"].get(label) and r["sigma_cm"]["none"] and r["sigma_cm"][label] is not None]
        if not pairs:
            out[label] = {"n_products": 0, "recommended": False, "why": "never applicable (layer or cube missing)"}
            continue
        base, corr = np.array(pairs).T
        red = 1 - corr / base
        share = float(np.mean(corr < base))
        med = float(np.median(red))
        ok = med >= MIN_REDUCTION and share >= MIN_SHARE
        out[label] = {"n_products": len(pairs), "median_sigma_cm_none": _r(np.median(base)),
                      "median_sigma_cm": _r(np.median(corr)), "median_reduction_pct": _r(100 * med, 1),
                      "share_reduced": _r(share, 2), "recommended": bool(ok),
                      "why": ("lowers the noise floor" if ok else
                              f"does not lower the noise floor enough (needs >= {MIN_REDUCTION:.0%} median and "
                              f">= {MIN_SHARE:.0%} of products)")}
    for n in SIGN_TESTS:
        both = [(r["sigma_cm"][n], r["sigma_cm_opposite_sign"][n]) for r in rows
                if n in r["sigma_cm_opposite_sign"] and r["sigma_cm"][n] is not None
                and r["sigma_cm_opposite_sign"][n] is not None]
        if both:
            better = float(np.mean([a < b for a, b in both]))
            out[n]["sign_check"] = {"n_products": len(both), "share_subtract_better": _r(better, 2),
                                    "verdict": "subtracting the screen is better (convention consistent)" if better >= 0.5
                                    else "ADDING the screen lowers the noise more: check the sign convention"}
    return out


def recommendation(summary: dict) -> str:
    on = [n for n in ("iono", "tropo", "tide") if summary.get(n, {}).get("recommended")]
    return ",".join(on) if on else "none"


def markdown(rep: dict) -> str:
    lines = ["# Noise report: phase corrections", "",
             f"Created {rep['created']} from `{rep['data_dir']}` ({rep['n_products']} GUNW products).", "",
             "Noise floor = robust sigma (cm) of the referenced LOS map in the recipe's stable reference area "
             "(> 25 km from the frame centre). Lower is better.", "",
             "| correction set | products applied | median sigma none (cm) | median sigma (cm) | median reduction | "
             "products reduced | recommended |", "|---|---|---|---|---|---|---|"]
    for label, s in rep["summary"].items():
        lines.append(f"| {label} | {s['n_products']} | {s.get('median_sigma_cm_none', '—')} | "
                     f"{s.get('median_sigma_cm', '—')} | {s.get('median_reduction_pct', '—')} % | "
                     f"{s.get('share_reduced', '—')} | {'yes' if s['recommended'] else 'no'} |")
    lines += ["", "## Sign convention check (single corrections, screen subtracted vs added)", ""]
    for n in SIGN_TESTS:
        sc = rep["summary"].get(n, {}).get("sign_check")
        lines.append(f"- **{n}**: " + (f"{sc['verdict']} ({sc['share_subtract_better']} of {sc['n_products']} products)"
                                       if sc else "not tested (never applicable)"))
    lines += ["", "## Ionosphere, per pair (uncertainty mask + keep the raw phase when subtracting does not help)", "",
              "| product | decision | frame sigma raw (rad) | frame sigma subtracted (rad) | masked by uncertainty |",
              "|---|---|---|---|---|"]
    for r in rep["products"]:
        d = r.get("iono_decision") or {}
        decision = ("subtracted" if d.get("applied") else "kept raw" if d.get("kept_raw") else
                    f"not applied ({d.get('reason')})" if d else "—")
        lines.append(f"| {r['id']} | {decision} | {d.get('frame_sigma_raw_rad', '—')} | "
                     f"{d.get('frame_sigma_subtracted_rad', '—')} | {d.get('uncertainty_masked_fraction', '—')} |")
    lines += ["", f"**Recommended setting:** `NISAR_CORRECTIONS={rep['recommended_setting']}` "
                  "(current default: `iono`). Corrections that do not lower the noise stay off.", "",
              "## Per product", "", "| product | " + " | ".join(SETS) + " | not applied because |",
              "|---|" + "---|" * (len(SETS) + 1)]
    for r in rep["products"]:
        why = "; ".join(f"{n}: {w}" for n, w in r["reasons"].items() if w and w != "applied")
        lines.append(f"| {r['id']} | " + " | ".join(str(r["sigma_cm"][k]) for k in SETS) + f" | {why} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data folder (default: NISAR_DATA or ../data)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--match", default="", help="only products whose id contains this text (e.g. T004)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many products (0 = all)")
    a = ap.parse_args(argv)
    if a.data:
        os.environ["NISAR_DATA"] = a.data
    sys.path.insert(0, str(HERE))
    import catalog
    from config import DATA_DIR
    from recipes import displacement
    ps = [p for p in catalog.load() if p.level == "GUNW" and a.match in p.id]
    if a.limit:
        ps = ps[:a.limit]
    if not ps:
        print(f"No GUNW product found in {DATA_DIR}: nothing to report.")
        return 1
    rows = []
    for i, p in enumerate(ps, 1):
        t = time.time()
        rows.append(product_noise(p, displacement))
        s = rows[-1]["sigma_cm"]
        print(f"[{i}/{len(ps)}] {p.id}  none {s['none']}  iono {s['iono']}  tropo {s['tropo']}  tide {s['tide']}  "
              f"all {s['iono+tropo+tide']}  ({time.time() - t:.1f}s)")
    summ = summarise(rows)
    rep = {"created": time.strftime("%Y-%m-%d %H:%M"), "data_dir": str(DATA_DIR), "n_products": len(rows),
           "sets": {k: list(v) for k, v in SETS.items()},
           "rule": {"min_median_reduction": MIN_REDUCTION, "min_share_reduced": round(MIN_SHARE, 3)},
           "summary": summ, "recommended_setting": recommendation(summ), "products": rows}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "noise_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / "noise_report.md").write_text(markdown(rep), encoding="utf-8")
    print(f"Recommended: NISAR_CORRECTIONS={rep['recommended_setting']}")
    print(f"Written: {out / 'noise_report.json'} and {out / 'noise_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
