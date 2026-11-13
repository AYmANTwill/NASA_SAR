#!/usr/bin/env python3
"""
NISAR Pulse — téléchargement des données NISAR (ASF DAAC), en 5 parties.

  Partie 1 : pilote d'environ 20 Go (Panama co-sismique, Al Wahda, humidité du sol)
  Parties 2 à 5 : le reste (~73 Go chacune), équilibré

Chaque fichier HDF5 est téléchargé, réduit aux couches utiles (GeoTIFF compressé),
puis supprimé. Ctrl+C arrête proprement à tout moment : relancer la même commande
reprend exactement où on s'était arrêté (fichiers finis gardés, fichier en cours repris
à l'octet près).

Installation (une fois) :
    pip install requests h5py numpy rasterio pyproj rich

Lancement (PowerShell, Windows) :
    $env:EARTHDATA_TOKEN="<ton jeton Earthdata>"
    python download_all.py run --part 1

Autres commandes :
    python download_all.py status             # avancement des 5 parties
    python download_all.py run --part 2       # partie suivante (même dossier data)
    python download_all.py run --part 1 --workers 3

Plan Maroc (voir docs/claude/MOROCCO_PLAN.md) : les « parties » sont des paliers (tier 1, 2, 3).
    python tools/make_morocco_plan.py                       # écrit plan_morocco.json (métadonnées ASF seulement)
    python download_all.py status --plan plan_morocco.json
    python download_all.py run --plan plan_morocco.json --part 1 --keep-raw
  --plan FICHIER : utilise ce plan à la place de plan_nisar.json (jamais modifié).
  --keep-raw     : garde le .h5 brut à côté des GeoTIFF extraits (GUNW/GCOV/GOFF).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import date
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
PLAN_FILE = HERE / "plan_nisar.json"
SEARCH_URL = "https://api.daac.asf.alaska.edu/services/search/param"
N_PARTS = 5
PILOT_GB = 20

# ---------------------------------------------------------------------------
# Ce qu'on télécharge (vérifié sur ASF le 11/11/2026)
# ---------------------------------------------------------------------------
ATLAS_FRAMES = {
    (116, 18), (116, 19), (15, 19), (44, 17), (44, 18), (145, 17),   # ascendants
    (95, 71), (95, 72), (23, 71), (23, 72), (23, 73),                # descendants
}
DATASETS = {
    # Panama : séisme M7.7 du 9/10/2026 17:56 UTC (USGS us6000u18k)
    "panama": dict(level="GUNW", bbox="-81.8,6.8,-79.8,8.6", start="2026-09-01",
                   end="2026-11-15", spans={12, 24, 36}, event="20261009T175606"),
    # Venezuela : séismes du 24/06/2026
    "venezuela": dict(level="GUNW", bbox="-67.6,10.2,-66.4,10.9", start="2026-06-01",
                      end="2026-07-31", spans={12, 24, 36}, event="20260624T000000"),
    # Atlas Maroc : 11 cadres, paires de 12 et 24 jours
    "atlas": dict(level="GUNW", bbox="-10,28,-1,36", start="2026-06-17", end=None,
                  frames=ATLAS_FRAMES, spans={12, 24}),
    # Humidité du sol, nord du Maroc (petits fichiers gardés entiers)
    "sme2": dict(level="SME2", bbox="-8.5,32.5,-3.5,36", start="2026-06-17", end=None),
}
PRIORITY = {"panama": 0, "atlas": 1, "venezuela": 2, "sme2": 3}

LAYERS = {
    "GUNW": ["unwrappedPhase", "coherenceMagnitude", "connectedComponents", "ionospherePhaseScreen"],
    "GCOV": ["HHHH", "HVHV", "VVVV", "VHVH"],
    "GOFF": ["alongTrackOffset", "slantRangeOffset", "correlationSurfacePeak"],
}
META_KEYWORDS = ["losUnitVector", "incidenceAngle", "elevationAngle"]

# Couches supplémentaires (plan Maroc), extraites seulement pour les lignes du plan qui portent
# "extra_layers": true ; sans cela l'extraction reste exactement celle d'avant.
# NOMS NON VÉRIFIÉS sur un vrai fichier (data/GUNW/_structure.json n'existait pas à l'inventaire du
# 2026-11-12) : ils viennent de la description du produit GUNW. Si un nom est faux, la couche est
# simplement absente et listée dans _extra_layers.json (« manquantes ») ; garder --keep-raw au début.
EXTRA_LAYERS = {"GUNW": ["ionospherePhaseScreenUncertainty", "mask"]}          # grilles 2D -> GeoTIFF
EXTRA_META_KEYWORDS = {"GUNW": ["TroposphericPhaseScreen", "solidEarthTide"]}  # cubes -> radar_geometry.npz
# La cohérence 80 m est déjà extraite (coherenceMagnitude de la grille « unwrapped »).


class Stopped(Exception):
    """Arrêt demandé par l'utilisateur (Ctrl+C)."""


STOP = threading.Event()


# ---------------------------------------------------------------------------
# Recherche ASF et construction du plan
# ---------------------------------------------------------------------------
def _d(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def parse_name(name: str) -> dict:
    p = name.split("_")
    stamps = [s for s in p if len(s) == 15 and s[8] == "T"]
    ref_ts = stamps[0] if stamps else ""
    sec_ts = stamps[2] if len(stamps) >= 4 else ref_ts
    return {"track": int(p[5]), "dir": p[6], "frame": int(p[7]), "pf": p[-3],
            "ref_ts": ref_ts, "sec_ts": sec_ts,
            "span": (_d(sec_ts) - _d(ref_ts)).days if ref_ts else 0}


def parse_crid(name: str) -> str:
    """CRID du produit dans le nom de fichier (ex. P05023 provisoire, P05036 validé)."""
    for tok in name.split("_")[8:]:
        if len(tok) == 6 and tok[0].isalpha() and tok[1:].isdigit():
            return tok
    return ""


def collection_of(url: str) -> str:
    """Dossier de collection dans l'URL (ex. NISAR_L2_GUNW_PROVISIONAL_V1)."""
    for part in url.split("/"):
        if part.startswith("NISAR_L") and "_V" in part:
            return part
    return ""


def maturity_of(collection: str) -> str:
    c = collection.upper()
    return "provisional" if "PROVISIONAL" in c else "beta" if "BETA" in c else "validated"


def search(level, bbox, start, end):
    params = dict(platform="NISAR", processingLevel=level, bbox=bbox, start=start,
                  maxResults=5000, output="geojson")
    if end:
        params["end"] = end
    r = requests.get(SEARCH_URL, params=params, timeout=300)
    r.raise_for_status()
    out = []
    for f in r.json()["features"]:
        p = f["properties"]
        name = p.get("fileID") or p.get("sceneName")
        size = p.get("bytes")
        if isinstance(size, dict):
            size = sum(v["bytes"] for k, v in size.items() if k.endswith(".h5") and "QA" not in k)
        out.append({"name": name, "url": p["url"], "size": int(size or 0), "level": level,
                    **parse_name(name)})
    return out


def search_ex(level, start, end=None, bbox=None, point=None):
    """Comme search(), mais par point (lat, lon) ou par bbox, et avec le CRID, la collection
    (PROVISIONAL / VALIDATED) et le type de produit. Utilisé par tools/make_morocco_plan.py."""
    params = dict(platform="NISAR", processingLevel=level, start=start, maxResults=5000, output="geojson")
    if point:
        params["intersectsWith"] = f"POINT({point[1]} {point[0]})"
    if bbox:
        params["bbox"] = bbox
    if end:
        params["end"] = end
    r = requests.get(SEARCH_URL, params=params, timeout=300)
    r.raise_for_status()
    out = []
    for f in r.json()["features"]:
        p = f["properties"]
        name = p.get("fileID") or p.get("sceneName")
        size = p.get("bytes")
        if isinstance(size, dict):
            size = sum(v["bytes"] for k, v in size.items() if k.endswith(".h5") and "QA" not in k)
        row = {"name": name, "url": p["url"], "size": int(size or 0), "level": level, **parse_name(name)}
        row["crid"] = p.get("crid") or parse_crid(name)
        row["collection"] = p.get("collectionName") or collection_of(p["url"])
        row["maturity"] = maturity_of(row["collection"])
        row["config"] = name.split("_")[9] if level == "GUNW" and len(name.split("_")) > 9 else ""
        out.append(row)
    return out


def nearest_neighbour(rows, max_span=48):
    """Garde les paires GUNW « plus proche voisin » : les deux dates sont deux acquisitions
    consécutives de la même série (orbite, cadre, direction, configuration, CRID), écart <= max_span
    jours. Une paire qui enjambe la lacune de données (27/07→10/08/2026) est donc gardée, une paire
    redondante qui saute une acquisition est écartée. Les CRID ne sont jamais mélangés dans une série.
    Limite : les dates viennent des paires elles-mêmes ; une acquisition sans aucune paire est invisible."""
    series = {}
    for r in rows:
        series.setdefault((r["track"], r["frame"], r["dir"], r.get("config", ""), r.get("crid", "")), []).append(r)
    kept = []
    for g in series.values():
        days = sorted({r["ref_ts"][:8] for r in g} | {r["sec_ts"][:8] for r in g})
        nxt = {d: days[i + 1] for i, d in enumerate(days[:-1])}
        kept += [r for r in g if r["span"] <= max_span and nxt.get(r["ref_ts"][:8]) == r["sec_ts"][:8]]
    return kept


def collect(key, cfg):
    rows = search(cfg["level"], cfg["bbox"], cfg["start"], cfg.get("end"))
    if cfg.get("frames"):
        rows = [r for r in rows if (r["track"], r["frame"]) in cfg["frames"]]
    if cfg.get("spans") and cfg["level"] != "SME2":
        rows = [r for r in rows if r["span"] in cfg["spans"]]
    if cfg.get("event"):
        ev = cfg["event"]
        rows = [r for r in rows if r["sec_ts"] < ev or r["ref_ts"] <= ev <= r["sec_ts"]]
        for r in rows:
            r["coseismic"] = r["ref_ts"] <= ev <= r["sec_ts"]
    best = {}
    for r in rows:      # une version par paire : cadre complet (F) en priorité
        k = (r["track"], r["frame"], r["ref_ts"], r["sec_ts"])
        if k not in best or (r["pf"] == "F" and best[k]["pf"] != "F"):
            best[k] = r
    for r in best.values():
        r["dataset"] = key
    return list(best.values())


def build_plan():
    rows, seen = [], set()
    for key, cfg in DATASETS.items():
        for r in collect(key, cfg):
            if r["name"] not in seen:
                seen.add(r["name"])
                rows.append(r)
    # --- Partie 1 : pilote ~20 Go -----------------------------------------
    pilot, budget = [], PILOT_GB * 1e9
    def take(cands):
        nonlocal budget
        for r in cands:
            if r not in pilot and r["size"] <= budget:
                pilot.append(r)
                budget -= r["size"]
    take([r for r in rows if r["dataset"] == "panama" and r.get("coseismic")])     # ~13 Go
    for fr in [(116, 19), (95, 71)]:                                               # Al Wahda, asc + desc
        last = sorted([r for r in rows if r["dataset"] == "atlas" and (r["track"], r["frame"]) == fr
                       and r["span"] == 12], key=lambda r: r["sec_ts"])[-1:]
        take(last)
    take(sorted([r for r in rows if r["dataset"] == "sme2" and (r["track"], r["frame"]) in
                 {(116, 19), (95, 71)}], key=lambda r: r["ref_ts"], reverse=True))
    for r in pilot:
        r["part"] = 1
    # --- Parties 2 à 5 : le reste, équilibré (plus gros fichiers d'abord) ---
    rest = sorted([r for r in rows if r not in pilot], key=lambda r: -r["size"])
    loads = {p: 0 for p in range(2, N_PARTS + 1)}
    for r in rest:
        p = min(loads, key=loads.get)
        r["part"] = p
        loads[p] += r["size"]
    rows.sort(key=lambda r: (r["part"], PRIORITY[r["dataset"]], r["track"], r["frame"], r["ref_ts"]))
    plan = {"created": time.strftime("%Y-%m-%d %H:%M"), "files": rows}
    PLAN_FILE.write_text(json.dumps(plan, indent=1))
    return plan


def load_plan(plan_file=None):
    if plan_file is not None:                       # --plan : jamais reconstruit automatiquement
        plan_file = Path(plan_file)
        if not plan_file.exists():
            sys.exit(f"Plan introuvable : {plan_file}")
        return json.loads(plan_file.read_text())
    if not PLAN_FILE.exists():
        print("Pas de plan_nisar.json à côté du script : construction depuis ASF…")
        return build_plan()
    return json.loads(PLAN_FILE.read_text())


# ---------------------------------------------------------------------------
# État sur disque (reprise)
# ---------------------------------------------------------------------------
def paths(out: Path, r):
    final = out / r["level"] / r["name"]
    return final, final / "_DONE", out / "_tmp" / (r["name"] + ".h5.part")


def state(out: Path, r):
    """'done', ('partial', octets) ou 'todo'."""
    final, done, part = paths(out, r)
    if done.exists():
        return "done", r["size"]
    if part.exists():
        return "partial", part.stat().st_size
    return "todo", 0


# ---------------------------------------------------------------------------
# Téléchargement avec reprise
# ---------------------------------------------------------------------------
_local = threading.local()


def session(token):
    if getattr(_local, "s", None) is None:
        _local.s = requests.Session()
        _local.s.headers["Authorization"] = f"Bearer {token}"
    return _local.s


def _range_total(content_range: str):
    """Taille totale dans un en-tête `Content-Range: bytes */1234` (réponse 416), sinon None."""
    tail = content_range.rsplit("/", 1)[-1].strip()
    return int(tail) if tail.isdigit() else None


def download(s, r, part: Path, on_bytes, tries=6):
    expected = r["size"]
    part.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, tries + 1):
        have = part.stat().st_size if part.exists() else 0
        if expected and have > expected:          # fichier corrompu : on repart de zéro
            part.unlink()
            have = 0
        if expected and have == expected:
            return
        try:
            headers = {"Range": f"bytes={have}-"} if have else {}
            with s.get(r["url"], headers=headers, stream=True, timeout=(30, 120)) as resp:
                if resp.status_code == 401:
                    raise SystemExit("Erreur 401 : jeton Earthdata invalide ou expiré.")
                if have and resp.status_code == 416:   # Range hors du fichier : en général il est déjà complet
                    total = _range_total(resp.headers.get("Content-Range", ""))
                    if total is None or total == have:
                        return                         # complet (ou taille inconnue) : finish() le vérifiera
                    on_bytes(-have)                    # le serveur dit une autre taille : on repart de zéro
                    part.unlink()
                    continue
                if have and resp.status_code == 200:   # reprise refusée par le serveur
                    have = 0
                    on_bytes(-part.stat().st_size)
                resp.raise_for_status()
                with open(part, "ab" if have else "wb") as f:
                    for chunk in resp.iter_content(chunk_size=4 << 20):
                        if STOP.is_set():
                            raise Stopped()
                        f.write(chunk)
                        on_bytes(len(chunk))
            if not expected or part.stat().st_size == expected:
                return
        except Stopped:
            raise
        except (requests.RequestException, OSError) as e:
            if attempt == tries:
                raise RuntimeError(f"téléchargement impossible après {tries} essais : {e}")
            for _ in range(5 * attempt):           # attente interruptible
                if STOP.is_set():
                    raise Stopped()
                time.sleep(1)


# ---------------------------------------------------------------------------
# Extraction HDF5 -> GeoTIFF
# ---------------------------------------------------------------------------
def _find_coords(h5, ds_path):
    parts = ds_path.strip("/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        g = "/" + "/".join(parts[:i])
        if f"{g}/xCoordinates" in h5 and f"{g}/yCoordinates" in h5:
            epsg = None
            if f"{g}/projection" in h5:
                pr = h5[f"{g}/projection"]
                epsg = int(pr.attrs.get("epsg_code", pr[()]))
            return h5[f"{g}/xCoordinates"][()], h5[f"{g}/yCoordinates"][()], epsg
    return None, None, None


def _write_tif(path, arr, x, y, epsg):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    transform = None
    if x is not None and len(x) > 1 and len(y) > 1:
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        transform = from_origin(float(x[0]) - dx / 2, float(y[0]) - dy / 2, dx, -dy)
    if arr.dtype == np.float64:
        arr = arr.astype(np.float32)
    is_f = np.issubdtype(arr.dtype, np.floating)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=arr.dtype, crs=f"EPSG:{epsg}" if epsg else None, transform=transform,
                       compress="LZW", predictor=3 if is_f else 2, tiled=True,
                       nodata=np.nan if is_f else None) as dst:
        dst.write(arr, 1)


def extract(h5_path: Path, out_dir: Path, level: str, extra: bool = False):
    import h5py
    import numpy as np
    extra_names = EXTRA_LAYERS.get(level, []) if extra else []
    extra_kw = EXTRA_META_KEYWORDS.get(level, []) if extra else []
    wanted = LAYERS[level] + extra_names
    meta_kw = META_KEYWORDS + extra_kw
    seen_extra = set()
    tmp_dir = out_dir.with_name(out_dir.name + ".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    found, meta = [], {}
    with h5py.File(h5_path, "r") as h5:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                base = name.split("/")[-1]
                # GUNW: only the unwrapped grid (the wrappedInterferogram coherence is full resolution, ~450 MB, unused)
                if level == "GUNW" and "wrappedInterferogram" in name and "unwrappedInterferogram" not in name:
                    return
                if base in wanted and obj.ndim == 2:
                    found.append(name)
                    if base in extra_names:
                        seen_extra.add(base)
                elif any(k in base for k in meta_kw) and obj.size < 50_000_000:
                    meta[name.replace("/", "__")] = obj[()]
                    seen_extra.update(k for k in extra_kw if k in base)
        h5.visititems(visit)
        if not found:
            raise RuntimeError(f"aucune couche {wanted} dans le fichier")
        for name in found:
            if STOP.is_set():
                raise Stopped()
            x, y, epsg = _find_coords(h5, "/" + name)
            tag = "_".join(name.split("/")[-3:])
            if "frequencyB" in name:
                tag = "freqB_" + tag
            _write_tif(tmp_dir / f"{tag}.tif", h5[name][()], x, y, epsg)
        if meta:
            np.savez_compressed(tmp_dir / "radar_geometry.npz", **meta)
        if extra:                                   # trace : quelles couches supplémentaires existent vraiment
            asked = extra_names + extra_kw
            (tmp_dir / "_extra_layers.json").write_text(json.dumps(
                {"demandees": asked, "trouvees": sorted(seen_extra),
                 "manquantes": [k for k in asked if k not in seen_extra]}, indent=1))
        inv = out_dir.parent / "_structure.json"
        if not inv.exists():
            items = []
            h5.visititems(lambda n, o: items.append([n, list(o.shape), str(o.dtype)])
                          if isinstance(o, h5py.Dataset) else None)
            inv.write_text(json.dumps(items, indent=1))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp_dir.rename(out_dir)                       # écriture atomique : tout ou rien
    return sum(f.stat().st_size for f in out_dir.iterdir())


def extra_missing(final: Path, required: bool = False):
    """Couches supplémentaires demandées mais absentes du fichier (lu dans _extra_layers.json).
    Si le rapport est illisible, ou absent alors qu'il est `required`, on renvoie ["?"] : dans le doute
    le fichier brut est gardé (filet de sécurité de finish)."""
    f = final / "_extra_layers.json"
    try:
        if not f.exists():
            return ["?"] if required else []
        miss = json.loads(f.read_text())["manquantes"]
        return list(miss) if isinstance(miss, list) else ["?"]
    except Exception:
        return ["?"]


def missing_warning(miss, raw_path: Path) -> str:
    what = ("état des couches supplémentaires inconnu (_extra_layers.json illisible)" if miss == ["?"]
            else "couches supplémentaires ABSENTES du fichier : " + ", ".join(miss))
    return (f"{what}. Le .h5 brut est GARDÉ : {raw_path}. Vérifier les noms avec "
            f"`python tools/list_h5_layers.py <fichier.h5> <mot-clé>` puis corriger EXTRA_LAYERS / "
            f"EXTRA_META_KEYWORDS avant de lancer le palier suivant.")


def finish(r, part: Path, final: Path, done: Path, keep_raw: bool = False):
    raw, missing = False, []
    if r["level"] in LAYERS:
        try:
            kept = extract(part, final, r["level"], extra=bool(r.get("extra_layers")))
        except Stopped:
            raise
        except Exception as e:
            part.unlink(missing_ok=True)          # fichier illisible : sera retéléchargé
            raise RuntimeError(f"extraction impossible ({e}) ; fichier supprimé, relancer")
        # Filet de sécurité : si une couche supplémentaire demandée manque (ou si on ne sait pas), le .h5
        # brut est GARDÉ même sans --keep-raw, sinon la couche serait perdue à jamais.
        missing = extra_missing(final, required=True) if r.get("extra_layers") else []
        if keep_raw or missing:                   # --keep-raw : le .h5 brut reste à côté des GeoTIFF
            dest = final / (r["name"] + ".h5")
            shutil.move(str(part), dest)
            kept += dest.stat().st_size
            raw = True
        else:
            part.unlink()
    else:                                         # SME2 : gardé entier
        final.mkdir(parents=True, exist_ok=True)
        dest = final / (r["name"] + ".h5")
        shutil.move(str(part), dest)
        kept = dest.stat().st_size
    meta = {"kept_bytes": kept, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if raw:
        meta["raw"] = True
    if missing:                                   # visible dans _DONE : le brut est gardé faute de couche
        meta["raw_kept_missing_layers"] = missing
    done.write_text(json.dumps(meta))
    return kept


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------
def human(b):
    return f"{b/1e9:.1f} Go" if b >= 1e9 else f"{b/1e6:.0f} Mo"


def short(name):
    p = parse_name(name)
    return f"{name.split('_')[3]} T{p['track']:03d} F{p['frame']:03d} {p['ref_ts'][:8]}→{p['sec_ts'][:8]}"


def plan_parts(plan):
    """Numéros de parties : 1..5 pour plan_nisar.json ; paliers présents pour un plan à « tiers »."""
    if plan.get("tiers"):
        return sorted({r["part"] for r in plan["files"]})
    return list(range(1, N_PARTS + 1))


def part_tag(plan, p):
    if plan.get("tiers"):
        return f" (palier {p} : {plan['tiers'].get(str(p), '')})"
    return " (pilote)" if p == 1 else ""


def cmd_status(plan, out):
    from rich.console import Console
    from rich.table import Table
    t = Table(title=f"Avancement — dossier {out.resolve()}")
    for c in ["Partie", "Fichiers", "Taille", "Finis", "Partiels", "Reste", "%"]:
        t.add_column(c, justify="right")
    for p in plan_parts(plan):
        rows = [r for r in plan["files"] if r["part"] == p]
        tot = sum(r["size"] for r in rows)
        got, nd, npart = 0, 0, 0
        for r in rows:
            st, b = state(out, r)
            got += b
            nd += st == "done"
            npart += st == "partial"
        t.add_row(f"{p}{part_tag(plan, p)}", str(len(rows)), human(tot), str(nd),
                  str(npart), human(tot - got), f"{100*got/max(tot,1):.0f} %")
    Console().print(t)


def space_needed(todo, workers, keep_raw=False):
    """Octets libres conseillés : ~3 Go par worker + marge ; avec --keep-raw, la taille des .h5 bruts
    (GUNW/GCOV/GOFF) qui resteront sur le disque."""
    need = workers * 3e9 + 5e9
    if keep_raw:
        need += sum(r["size"] for r in todo if r["level"] in LAYERS)
    return need


def cmd_run(plan, out, part_no, workers, token, keep_raw=False, resume_extra=""):
    from rich.console import Console
    from rich.progress import (Progress, BarColumn, DownloadColumn, TransferSpeedColumn,
                               TimeRemainingColumn, TextColumn, TimeElapsedColumn)
    console = Console()
    rows = [r for r in plan["files"] if r["part"] == part_no]
    total = sum(r["size"] for r in rows)
    todo, already, n_done, n_partial = [], 0, 0, 0
    for r in rows:
        st, b = state(out, r)
        already += b
        if st == "done":
            n_done += 1
        else:
            n_partial += st == "partial"
            todo.append(r)
    free = shutil.disk_usage(out).free
    need = space_needed(todo, workers, keep_raw)
    n_shown = max(plan_parts(plan)) if plan.get("tiers") else N_PARTS
    console.rule(f"[bold]NISAR Pulse — partie {part_no}/{n_shown}{part_tag(plan, part_no)}")
    console.print(f"{len(rows)} fichiers, {human(total)} au total · déjà finis : {n_done} · "
                  f"repris en cours de route : {n_partial} ({human(already)} déjà sur le disque)")
    console.print(f"Workers : {workers} · disque libre : {human(free)} · dossier : {out.resolve()}")
    if free < need:
        console.print(f"[yellow]Attention : moins de {human(need)} libres ; risque de disque plein.")
    if not todo:
        console.print("[green]Cette partie est déjà complète.")
        return 0
    console.print("[dim]Ctrl+C pour arrêter proprement ; relancer la même commande pour reprendre.\n")

    errors, kept_total = [], 0
    manifest = out / "manifest.csv"
    new_manifest = not manifest.exists()
    lock = threading.Lock()
    with Progress(TextColumn("{task.description}"), BarColumn(bar_width=30),
                  TextColumn("{task.percentage:>5.1f} %"), DownloadColumn(),
                  TransferSpeedColumn(), TextColumn("reste"), TimeRemainingColumn(),
                  console=console, refresh_per_second=4) as prog, \
            open(manifest, "a", newline="") as mf:
        w = csv.writer(mf)
        if new_manifest:
            w.writerow(["date", "partie", "fichier", "jeu", "taille_octets", "garde_octets", "statut"])
        overall = prog.add_task(f"[bold cyan]Partie {part_no} · 0/{len(todo)} fichiers",
                                total=total, completed=already)
        files_done = [0]

        def job(r):
            final, done, part = paths(out, r)
            have = part.stat().st_size if part.exists() else 0
            tid = prog.add_task(f"  {short(r['name'])}", total=r["size"], completed=have)
            def on_bytes(n):
                prog.advance(tid, n)
                prog.advance(overall, n)
            try:
                download(session(token), r, part, on_bytes)
                prog.update(tid, description=f"  [magenta]extraction[/] {short(r['name'])}")
                kept = finish(r, part, final, done, keep_raw)
                return r, kept, None
            except Stopped:
                return r, 0, "arrêt"
            except Exception as e:
                return r, 0, str(e)
            finally:
                prog.remove_task(tid)

        pool = ThreadPoolExecutor(workers)
        pending = {pool.submit(job, r) for r in todo}
        try:
            while pending:
                finished, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                for f in finished:
                    r, kept, err = f.result()
                    if err == "arrêt":
                        continue
                    with lock:
                        status = "ok" if err is None else f"erreur: {err}"
                        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), part_no, r["name"],
                                    r["dataset"], r["size"], kept, status])
                        mf.flush()
                    if err:
                        errors.append((r["name"], err))
                        prog.console.print(f"[red]✗ {short(r['name'])} : {err}")
                    else:
                        kept_total += kept
                        files_done[0] += 1
                        prog.console.print(f"[green]✓[/] {short(r['name'])} "
                                           f"[dim]{human(r['size'])} → gardé {human(kept)}[/]")
                        if r.get("extra_layers"):
                            fin = paths(out, r)[0]
                            miss = extra_missing(fin, required=True)
                            if miss:
                                prog.console.print(f"[bold yellow]  ⚠ {missing_warning(miss, fin / (r['name'] + '.h5'))}")
                    prog.update(overall, description=f"[bold cyan]Partie {part_no} · "
                                f"{files_done[0]}/{len(todo)} fichiers")
        except KeyboardInterrupt:
            STOP.set()
            prog.console.print("\n[yellow]Arrêt demandé : on termine proprement l'écriture en cours…")
            pool.shutdown(wait=True, cancel_futures=True)
            prog.stop()
            console.print("[yellow]Arrêté. Tout ce qui a été téléchargé est conservé. "
                          f"Pour reprendre : python download_all.py run --part {part_no}{resume_extra}")
            return 130
        pool.shutdown(wait=True)

    console.rule("[bold]Bilan")
    console.print(f"Fichiers finis : {files_done[0]}/{len(todo)} · données gardées : {human(kept_total)}")
    if errors:
        console.print(f"[red]{len(errors)} erreur(s) — relancer la même commande pour réessayer "
                      "ces fichiers (les autres ne seront pas refaits).")
        return 1
    console.print(f"[green]Partie {part_no} terminée.")
    return 0


TOKEN_FILE = HERE / ".earthdata_token"
# Team Earthdata token (Ayman's account, expires January 2027). An EARTHDATA_TOKEN environment
# variable, if set, takes priority over this one.
EARTHDATA_TOKEN = "eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6InR3aWx6YWIyMDIwIiwic3ViIjoidHdpbHphYjIwMjAiLCJleHAiOjE3OTk2MTI4NTgsImlhdCI6MTc5NDQyODg1OCwiaXNzIjoiaHR0cHM6Ly91cnMuZWFydGhkYXRhLm5hc2EuZ292IiwiaWRlbnRpdHlfcHJvdmlkZXIiOiJlZGxfb3BzIiwiYWNyIjoiZWRsIiwiYXNzdXJhbmNlX2xldmVsIjozfQ.QjUANaG37WwJoPsXQ61bheDQkctuCurTbvgem5z5qKd5Ix6wOXEk5ihJd97qm8Myg2PrIaQ4o1Bb5szmLcV8L4TQZVl-ZkCl89uG91jrBsD_Gp-TNO0-P-6IkshrhBT8heuG_wFQtzFBRQe1VG_-8X0Nhf8lHDY7Gz-1nkm5hnpH1roEYrpL1S5W27d5K37yIHNQIKA18qIBReVxDIG_wz77pNqabNx0aNjSq-Y0Nu1AT5ExyNm3umXoDlsXCmbgIE5Ufvu9uY7geK9-u3jhQxLcyyG4-zsaZTPyamG9LrjKTd3fYVjEecoy3STHbZS-kbAZIZ1Cf8mWjDzA9yDq6A"


def get_token():
    """Jeton : variable EARTHDATA_TOKEN, sinon fichier .earthdata_token à côté du script,
    sinon demandé une fois puis enregistré dans ce fichier."""
    tok = os.environ.get("EARTHDATA_TOKEN", "").strip() or EARTHDATA_TOKEN.strip()
    if tok:
        return tok
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    import getpass
    tok = getpass.getpass("Colle ton jeton Earthdata (invisible à l'écran), puis Entrée : ").strip()
    if not tok:
        sys.exit("Aucun jeton fourni.")
    TOKEN_FILE.write_text(tok)
    print(f"Jeton enregistré dans {TOKEN_FILE} (supprime ce fichier après le hackathon).")
    return tok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", choices=["run", "status", "build-plan"])
    ap.add_argument("--part", type=int, choices=range(1, N_PARTS + 1))
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out", default=str(HERE / "data"),
                    help="dossier de sortie (par défaut : data/ à côté du script)")
    ap.add_argument("--plan", default=None,
                    help="plan à utiliser à la place de plan_nisar.json (ex. plan_morocco.json) ; "
                         "les « parties » sont alors les paliers du plan")
    ap.add_argument("--keep-raw", action="store_true",
                    help="garde le .h5 brut à côté des GeoTIFF extraits (GUNW/GCOV/GOFF)")
    a = ap.parse_args()

    if a.action is None:            # lancé sans argument (bouton Run de VS Code, double-clic)
        print("NISAR Pulse — téléchargement. Parties : 1 = pilote (~20 Go), 2 à 5 = ~78 Go chacune.")
        cmd_status(load_plan(a.plan), Path(a.out)) if Path(a.out).exists() else None
        choix = input("Quelle partie lancer ? [1-5, Entrée = 1] : ").strip() or "1"
        if choix not in {str(i) for i in range(1, N_PARTS + 1)}:
            sys.exit("Choix invalide.")
        a.action, a.part = "run", int(choix)

    if a.action == "build-plan":
        if a.plan:
            sys.exit("build-plan ne s'applique qu'à plan_nisar.json. Pour le plan Maroc : "
                     "python tools/make_morocco_plan.py")
        plan = build_plan()
        for p in range(1, N_PARTS + 1):
            rs = [r for r in plan["files"] if r["part"] == p]
            print(f"partie {p}: {len(rs)} fichiers, {human(sum(r['size'] for r in rs))}")
        return
    plan = load_plan(a.plan)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.action == "status":
        cmd_status(plan, out)
        return
    if not a.part:
        sys.exit("Indique la partie : --part 1 (pilote) à --part 5")
    token = get_token()
    resume_extra = (f" --plan {a.plan}" if a.plan else "") + (" --keep-raw" if a.keep_raw else "")
    sys.exit(cmd_run(plan, out, a.part, a.workers, token, a.keep_raw, resume_extra))


if __name__ == "__main__":
    main()
