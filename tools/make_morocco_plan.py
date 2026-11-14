#!/usr/bin/env python3
"""Construit plan_morocco.json pour download_all.py (--plan). Métadonnées ASF seulement :
AUCUN produit n'est téléchargé et plan_nisar.json n'est jamais modifié.

Les « parties » du plan sont des paliers (docs/claude/MOROCCO_PLAN.md §4, docs/claude/morocco_inventory.md) :
  palier 1 : Al Haouz (dernière paire avant, paire qui enjambe, première paire après le 10/10/2026,
             une par cadre), SME2 aux sites depuis le 20/09, dernière paire VALIDATED par cadre (si elle existe)
  palier 2 : toutes les paires « plus proche voisin » (<= 48 j, ponts de lacune inclus) des cadres minimaux
  palier 3 : reste du SME2 de la boîte -10,30.5,-1,36

Usage (depuis la racine du dépôt) :
    python tools/make_morocco_plan.py [--out plan_morocco.json] [--include-partial] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import download_all as da  # noqa: E402

# Sites (lat, lon) — docs/claude/morocco_inventory.md §1. ksar_el_kebir et ben_guerir_mine sont les
# points proposés par l'inventaire (à confirmer sur fond de carte), pas ceux du plan initial.
SITES = {
    "imlil": (31.136, -7.919),
    "asni": (31.250, -7.983),
    "moulay_brahim": (31.286, -7.966),
    "al_wahda_dam": (34.598, -5.198),
    "gharb": (34.50, -6.00),
    "ksar_el_kebir": (35.0105, -5.9031),
    "ben_guerir_mine": (32.25825, -7.82355),
    "chefchaouen": (35.17, -5.27),
}
HAOUZ = ("imlil", "asni", "moulay_brahim")
EVENT = "20261010T000000"          # crue éclair d'Al Haouz ; minuit, comme dans le plan
START = "2026-06-17"
SME2_FROM = "20260920"
SME2_BBOX = "-10,30.5,-1,36"
MAX_SPAN = 48
TIERS = {"1": "Al Haouz + SME2 aux sites + dernière paire VALIDATED",
         "2": "chaînes complètes des cadres minimaux (ponts de lacune inclus)",
         "3": "reste du SME2 de la boîte Maroc"}


def _fetch_default(level, start, bbox=None, point=None):
    return da.search_ex(level, start, bbox=bbox, point=point)


def dedupe_sme2(rows):
    """Une version par (orbite, cadre, dates) : cadre complet (F) en priorité, comme da.collect()."""
    best = {}
    for r in rows:
        k = (r["track"], r["frame"], r["ref_ts"], r["sec_ts"])
        if k not in best or (r["pf"] == "F" and best[k]["pf"] != "F"):
            best[k] = r
    return list(best.values())


def minimal_frames(frame_sites):
    """Plus petit ensemble de cadres (glouton, par direction) qui couvre tous les sites."""
    chosen = []
    for d in ("A", "D"):
        cand = {f: s for f, s in frame_sites.items() if f[2] == d}
        todo = set().union(*cand.values()) if cand else set()
        while todo:
            best = max(sorted(cand), key=lambda f: len(cand[f] & todo))   # sorted : départage déterministe
            chosen.append(best)
            todo -= cand[best]
    return chosen


def event_pairs(chain):
    """Dernière paire avant, paires qui enjambent, première paire après l'événement, dans UNE chaîne."""
    pre = [r for r in chain if r["sec_ts"] <= EVENT]
    strad = [r for r in chain if r["ref_ts"] < EVENT < r["sec_ts"]]
    post = [r for r in chain if r["ref_ts"] >= EVENT]
    out = []
    if pre:
        out.append(("pre", max(pre, key=lambda r: r["sec_ts"])))
    out += [("straddle", r) for r in strad]
    if post:
        out.append(("post", min(post, key=lambda r: r["ref_ts"])))
    return out


def build_plan(fetch=None, include_partial=False):
    fetch = fetch or _fetch_default
    warnings = []
    gunw_all, sme2_all, sites_of = {}, {}, {}
    for key, (lat, lon) in SITES.items():
        for r in fetch("GUNW", START, point=(lat, lon)):
            gunw_all.setdefault(r["name"], r)
            sites_of.setdefault(r["name"], set()).add(key)
        for r in fetch("SME2", START, point=(lat, lon)):
            sme2_all.setdefault(r["name"], r)
            sites_of.setdefault(r["name"], set()).add(key)
    fkey = lambda r: (r["track"], r["frame"], r["dir"])
    frame_sites = {}
    for n, r in gunw_all.items():
        frame_sites.setdefault(fkey(r), set()).update(sites_of[n])
    # Un seul type de produit par chaîne : cadre complet seulement (les doublons « Partial » sont écartés).
    pool = [r for r in gunw_all.values() if include_partial or r["pf"] == "F"]
    gunw = da.nearest_neighbour(pool, MAX_SPAN)
    minimal = minimal_frames(frame_sites)
    haouz_frames = sorted(f for f, s in frame_sites.items() if s & set(HAOUZ))

    assigned, role = {}, {}

    def put(r, tier, why=None):
        if r["name"] not in assigned:
            assigned[r["name"]] = (tier, r)
            if why:
                role[r["name"]] = why

    # --- palier 1a : Al Haouz, une chaîne (CRID) à la fois --------------------------------------------
    for f in haouz_frames:
        straddled = False
        for crid in sorted({r["crid"] for r in gunw if fkey(r) == f}):
            chain = [r for r in gunw if fkey(r) == f and r["crid"] == crid]
            found = event_pairs(chain)
            straddled = straddled or any(w == "straddle" for w, _ in found)
            for why, r in found:
                put(r, 1, why)
            if any(EVENT[:8] in (r["ref_ts"][:8], r["sec_ts"][:8]) for r in chain):
                warnings.append(f"cadre {f[0]}/{f[1]}/{f[2]} : une acquisition tombe le 10 octobre (paire ambiguë)")
        if not straddled:
            warnings.append(f"cadre {f[0]}/{f[1]}/{f[2]} : aucune paire n'enjambe le 2026-10-10")
    # --- palier 1b : SME2 aux sites depuis le 20/09 ----------------------------------------------------
    site_sme2 = [r for n, r in sme2_all.items() if r["ref_ts"][:8] >= SME2_FROM]
    for r in dedupe_sme2(site_sme2):
        put(r, 1)
    # --- palier 1c : dernière paire VALIDATED par cadre (cadres minimaux + Al Haouz) --------------------
    for f in sorted(set(minimal) | set(haouz_frames)):
        val = [r for r in gunw if fkey(r) == f and r["maturity"] == "validated"]
        if val:
            put(max(val, key=lambda r: r["sec_ts"]), 1, "latest_validated")
    # --- palier 2 : chaînes complètes des cadres minimaux ---------------------------------------------
    for r in gunw:
        if fkey(r) in minimal:
            put(r, 2)
    # --- palier 3 : SME2 de la boîte ------------------------------------------------------------------
    for r in dedupe_sme2(fetch("SME2", START, bbox=SME2_BBOX)):
        put(r, 3)

    rows = []
    for name, (tier, r) in assigned.items():
        row = dict(r)
        row.update(dataset="morocco_gunw" if r["level"] == "GUNW" else "morocco_sme2", tier=tier, part=tier)
        if r["level"] == "GUNW":
            row["extra_layers"] = True
        if name in sites_of:
            row["sites"] = sorted(sites_of[name])
        if name in role:
            row["event_role"] = role[name]
        if r["level"] == "GUNW" and EVENT[:8] in (r["ref_ts"][:8], r["sec_ts"][:8]):
            row["event_ambiguous"] = True       # une acquisition tombe le jour de l'événement
        rows.append(row)
    rows.sort(key=lambda r: (r["tier"], r["dataset"], r["track"], r["frame"], r["ref_ts"], r["name"]))
    return {"created": time.strftime("%Y-%m-%d %H:%M"), "scheme": "morocco-v1", "tiers": TIERS,
            "event": EVENT, "minimal_frames": [list(f) for f in minimal],
            "haouz_frames": [list(f) for f in haouz_frames], "include_partial": include_partial,
            "warnings": warnings, "files": rows}


def summary(plan):
    lines = []
    for t in sorted(TIERS):
        rs = [r for r in plan["files"] if r["tier"] == int(t)]
        gb = sum(r["size"] for r in rs) / 1e9
        lines.append(f"palier {t}: {len(rs):4d} fichiers  {gb:8.2f} Go  {gb * 8000 / 50 / 3600:5.2f} h à 50 Mbps  — {TIERS[t]}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "plan_morocco.json"))
    ap.add_argument("--include-partial", action="store_true", help="garde aussi les produits « Partial » (doublons)")
    ap.add_argument("--dry-run", action="store_true", help="affiche le résumé sans écrire le fichier")
    a = ap.parse_args()
    if Path(a.out).resolve() == (REPO / "plan_nisar.json").resolve():
        sys.exit("Refus : plan_nisar.json ne doit pas être modifié.")
    plan = build_plan(include_partial=a.include_partial)
    print("Cadres minimaux :", ", ".join("/".join(map(str, f)) for f in plan["minimal_frames"]))
    print("Cadres Al Haouz :", ", ".join("/".join(map(str, f)) for f in plan["haouz_frames"]))
    print("\n".join(summary(plan)))
    for w in plan["warnings"]:
        print("ATTENTION :", w)
    if a.dry_run:
        return
    Path(a.out).write_text(json.dumps(plan, indent=1))
    print(f"Écrit : {a.out}")


if __name__ == "__main__":
    main()
