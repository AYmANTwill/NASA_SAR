"""GPS validation: NISAR line-of-sight change at a permanent GNSS station vs the station's daily positions.

GPS source: Nevada Geodetic Laboratory (NGL, University of Nevada Reno), free, no account. Checked on 2026-11-14:
  - daily positions (east/north/up, IGS20 frame):  https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/<STA>.tenv3
  - station list with coordinates and data span:     https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt
Station coordinates are read from NGL (the tenv3 file itself, or DataHoldings.txt), never typed in.
Note: NGL's RABT (Rabat) series ends on 2024-11-14, so it cannot test the 2026 NISAR pairs; use --auto to find the
stations inside the downloaded frames that have data in the NISAR window (in northern Morocco: Ceuta, Melilla).

Method, per NISAR pair whose footprint holds the station:
  1. GPS change = mean position over +-W days around the second date minus the same around the first date (E, N, U).
  2. Projected on the line of sight with recipes/decompose.los_vector (ground-to-satellite unit vector, positive =
     toward the satellite, the convention of the displacement recipe with NISAR_LOS_SIGN=+1).
  3. NISAR value = the displacement recipe at the station (median within 1 km, referenced to the stable area).
  4. InSAR is relative: the raw comparison AND the comparison after removing the mean difference are reported.
Outputs RMS difference, correlation, number of pairs, a PNG of both series. A strongly NEGATIVE correlation hints
that the LOS sign is reversed: see sign_check.py; this script never changes NISAR_LOS_SIGN.

Usage (from backend/):
    python validate_gps.py [--station RABT] [--auto] [--window 3] [--data D:\\nisar_data] [--out ..\\results_out]
    python validate_gps.py --offline-sample [DIR]      (no internet: DIR holds <STA>.tenv3 and DataHoldings.txt;
                                                          default DIR = <data>/GPS_sample, made by the synthetic tests)
Writes <out>/gps_<STATION>.json, .md, .png. Exit code 0 = compared, 2 = nothing to compare (said in the files).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "results_out"
TENV3_URL = "https://geodesy.unr.edu/gps_timeseries/IGS20/tenv3/IGS20/{sta}.tenv3"
HOLDINGS_URL = "https://geodesy.unr.edu/NGLStationPages/DataHoldings.txt"
DEFAULT_STATION = "RABT"
WINDOW_DAYS = 3
MIN_EPOCHS = 2            # GPS days needed around each date
SIGN_HINT_CORR = -0.5


# ---------------------------------------------------------------------------------------------------------------------
# NGL files
# ---------------------------------------------------------------------------------------------------------------------
def parse_tenv3(text: str) -> dict:
    """{"station", "lat", "lon", "height", "epochs": [(date, east_m, north_m, up_m)]} from an NGL tenv3 file."""
    epochs, sta, last = [], None, None
    for line in text.splitlines():
        f = line.split()
        if len(f) < 23 or f[0] == "site":
            continue
        try:
            d = datetime.strptime(f[1].title(), "%y%b%d").date()
            e, n, u = float(f[7]) + float(f[8]), float(f[9]) + float(f[10]), float(f[11]) + float(f[12])
        except ValueError:
            continue
        epochs.append((d, e, n, u))
        sta, last = f[0], f
    if not epochs:
        raise ValueError("no position in the tenv3 file")
    lon = float(last[21])
    return {"station": sta, "lat": float(last[20]), "lon": lon - 360 if lon > 180 else lon,
            "height": float(last[22]), "epochs": epochs}


def parse_holdings(text: str) -> list[dict]:
    """Stations from NGL DataHoldings.txt: {station, lat, lon (-180..180), start, end}."""
    out = []
    for line in text.splitlines()[1:]:
        f = line.split()
        if len(f) < 9:
            continue
        try:
            lon = float(f[2])
            out.append({"station": f[0], "lat": float(f[1]), "lon": lon - 360 if lon > 180 else lon,
                        "start": date.fromisoformat(f[7]), "end": date.fromisoformat(f[8])})
        except ValueError:
            continue
    return out


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "nisar-pulse-validation"})
    with urllib.request.urlopen(req, timeout=120) as r:      # noqa: S310 - fixed https NGL URLs
        return r.read().decode("utf-8", "replace")


class Source:
    """NGL over the internet, or an offline sample folder holding <STA>.tenv3 and DataHoldings.txt."""

    def __init__(self, sample_dir: Path | None = None):
        self.sample = Path(sample_dir) if sample_dir else None

    def tenv3(self, sta: str) -> str:
        if self.sample:
            f = self.sample / f"{sta}.tenv3"
            if not f.exists():
                raise FileNotFoundError(f"{f} not found in the offline sample")
            return f.read_text()
        return _fetch(TENV3_URL.format(sta=sta))

    def holdings(self) -> str:
        if self.sample:
            return (self.sample / "DataHoldings.txt").read_text()
        return _fetch(HOLDINGS_URL)

    def label(self, sta: str) -> str:
        return str(self.sample / f"{sta}.tenv3") if self.sample else TENV3_URL.format(sta=sta)


# ---------------------------------------------------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------------------------------------------------
def _d(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def mean_position(epochs, center: date, half_window: int = WINDOW_DAYS):
    """Mean (E, N, U) in metres over the days within +-half_window of center; None if fewer than MIN_EPOCHS."""
    import numpy as np
    sel = [(e, n, u) for d, e, n, u in epochs if abs((d - center).days) <= half_window]
    if len(sel) < MIN_EPOCHS:
        return None, len(sel)
    return np.mean(np.array(sel), axis=0), len(sel)


def gps_los_change_mm(epochs, d1: date, d2: date, los_vec, half_window: int = WINDOW_DAYS):
    """GPS line-of-sight change (mm, positive = toward the satellite) between two dates, and the ENU change (mm)."""
    import numpy as np
    p1, n1 = mean_position(epochs, d1, half_window)
    p2, n2 = mean_position(epochs, d2, half_window)
    if p1 is None or p2 is None:
        return None, None, (n1, n2)
    denu = (p2 - p1) * 1000.0
    return float(np.dot(denu, np.asarray(los_vec))), [round(float(x), 2) for x in denu], (n1, n2)


def stats(nisar, gps) -> dict:
    import numpy as np
    a, b = np.asarray(nisar, float), np.asarray(gps, float)
    n = int(a.size)
    if n == 0:
        return {"n_pairs": 0}
    diff = a - b
    out = {"n_pairs": n, "rms_mm": round(float(np.sqrt(np.mean(diff ** 2))), 2),
           "mean_difference_mm": round(float(diff.mean()), 2),
           "rms_after_removing_mean_mm": round(float(np.sqrt(np.mean((diff - diff.mean()) ** 2))), 2),
           "correlation": None}
    if n >= 3 and a.std() > 0 and b.std() > 0:
        out["correlation"] = round(float(np.corrcoef(a, b)[0, 1]), 3)
    return out


def compare(station: dict, products, displacement, decompose, half_window: int = WINDOW_DAYS) -> list[dict]:
    """One row per NISAR pair covering the station."""
    rows = []
    for p in products:
        if not p.covers(station["lat"], station["lon"]):
            continue
        v, src = decompose.los_vector(p)
        g, denu, n_ep = gps_los_change_mm(station["epochs"], _d(p.ref), _d(p.sec), v, half_window)
        f = displacement.analyze(p, station["lat"], station["lon"], make_layer=False)
        rows.append({"product": p.id, "direction": p.direction, "track": p.track, "frame": p.frame, "crid": p.crid,
                     "date_before": p.ref[:8], "date_after": p.sec[:8], "los_vector": [round(float(x), 4) for x in v],
                     "los_vector_source": src, "gps_enu_change_mm": denu, "gps_epochs_used": list(n_ep),
                     "gps_los_mm": None if g is None else round(g, 2),
                     "nisar_los_mm": None if f["los_cm"] is None else round(f["los_cm"] * 10, 2),
                     "nisar_noise_mm": None if f["noise_cm"] is None else round(f["noise_cm"] * 10, 2),
                     "corrections_applied": f.get("corrections_applied", [])})
    return rows


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["gps_los_mm"] is not None and r["nisar_los_mm"] is not None]
    out = {"all": stats([r["nisar_los_mm"] for r in ok], [r["gps_los_mm"] for r in ok]), "by_geometry": {}}
    for key in sorted({(r["track"], r["frame"], r["direction"]) for r in ok}):
        sel = [r for r in ok if (r["track"], r["frame"], r["direction"]) == key]
        out["by_geometry"][f"{key[0]}/{key[1]} {key[2]}"] = stats([r["nisar_los_mm"] for r in sel],
                                                                  [r["gps_los_mm"] for r in sel])
    c = out["all"].get("correlation")
    out["sign_hint"] = (None if c is None else
                        "anti-correlated: the LOS sign may be reversed (see sign_check.py)" if c <= SIGN_HINT_CORR else
                        "same sign as GPS" if c >= -SIGN_HINT_CORR else "inconclusive")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------------------------------------------------
def plot(rows: list[dict], station: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    ok = sorted([r for r in rows if r["gps_los_mm"] is not None and r["nisar_los_mm"] is not None],
                key=lambda r: r["date_after"])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if ok:
        x = [datetime.strptime(r["date_after"], "%Y%m%d") for r in ok]
        g = np.array([r["gps_los_mm"] for r in ok])
        n = np.array([r["nisar_los_mm"] for r in ok])
        ax.plot(x, g, "o-", label="GPS (NGL), projected on the line of sight")
        ax.plot(x, n, "s-", label="NISAR, raw")
        ax.plot(x, n - (n - g).mean(), "s--", alpha=0.6, label="NISAR, mean difference removed")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "no pair to compare", ha="center", va="center", transform=ax.transAxes)
    ax.axhline(0, color="0.6", lw=0.8)
    ax.set_ylabel("LOS change per pair (mm, + = toward satellite)")
    ax.set_xlabel("second date of the pair")
    ax.set_title(f"GPS validation at {station}")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def markdown(rep: dict) -> str:
    st = rep["station"]
    lines = [f"# GPS validation at {st['station']}", "", f"Status: **{rep['status']}**. {rep['message']}", "",
             f"Station {st['station']} at {st.get('lat')}, {st.get('lon')} (NGL coordinates). "
             f"GPS source: `{rep['gps_source']}`.",
             f"GPS days used: +-{rep['window_days']} around each date. LOS sign verified: {rep['sign_verified']}.", ""]
    s = rep.get("summary", {}).get("all", {})
    if s.get("n_pairs"):
        lines += ["| | value |", "|---|---|", f"| pairs compared | {s['n_pairs']} |",
                  f"| RMS difference (raw) | {s['rms_mm']} mm |",
                  f"| mean difference (NISAR - GPS) | {s['mean_difference_mm']} mm |",
                  f"| RMS after removing the mean | {s['rms_after_removing_mean_mm']} mm |",
                  f"| correlation | {s['correlation']} |", f"| sign hint | {rep['summary']['sign_hint']} |", "",
                  "| pair | direction | GPS LOS (mm) | NISAR LOS (mm) | NISAR noise (mm) |", "|---|---|---|---|---|"]
        for r in rep["pairs"]:
            lines.append(f"| {r['date_before']}→{r['date_after']} T{r['track']} F{r['frame']} | {r['direction']} | "
                         f"{r['gps_los_mm']} | {r['nisar_los_mm']} | {r['nisar_noise_mm']} |")
    return "\n".join(lines) + "\n"


def write(rep: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sta = rep["station"]["station"]
    (out / f"gps_{sta}.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / f"gps_{sta}.md").write_text(markdown(rep), encoding="utf-8")
    plot(rep.get("pairs", []), sta, out / f"gps_{sta}.png")


# ---------------------------------------------------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------------------------------------------------
def validate(sta: str, source: Source, products, window: int, out: Path) -> dict:
    import config
    from recipes import decompose, displacement
    sta = sta.upper()
    rep = {"station": {"station": sta}, "gps_source": source.label(sta), "window_days": window,
           "sign_verified": config.LOS_SIGN_VERIFIED, "n_gunw_products": len(products), "pairs": []}
    try:
        st = parse_tenv3(source.tenv3(sta))
    except Exception as e:                                   # noqa: BLE001 - unreachable or empty series: said
        rep.update(status="no_gps", message=f"Could not read the NGL series of {sta}: {type(e).__name__}: {e}")
        write(rep, out)
        return rep
    rep["station"] = {k: st[k] for k in ("station", "lat", "lon", "height")}
    rep["gps_first_date"], rep["gps_last_date"] = str(st["epochs"][0][0]), str(st["epochs"][-1][0])
    covering = [p for p in products if p.covers(st["lat"], st["lon"])]
    if not covering:
        rep.update(status="no_coverage",
                   message=f"Station {sta} ({st['lat']:.4f}, {st['lon']:.4f}) is inside none of the {len(products)} "
                           "downloaded GUNW frames: nothing to compare. Try --auto.")
        write(rep, out)
        return rep
    rows = compare(st, covering, displacement, decompose, window)
    rep["pairs"] = rows
    rep["summary"] = summarise(rows)
    n = rep["summary"]["all"]["n_pairs"]
    if n == 0:
        rep.update(status="no_gps_in_window",
                   message=f"{len(covering)} NISAR pair(s) cover {sta}, but the GPS series ({rep['gps_first_date']} to "
                           f"{rep['gps_last_date']}) has fewer than {MIN_EPOCHS} days within +-{window} days of their "
                           "dates (or NISAR has no valid pixel there): nothing to compare. Try --auto.")
    else:
        rep.update(status="compared", message=f"{n} pair(s) compared out of {len(covering)} covering the station.")
    write(rep, out)
    return rep


def stations_in_frames(holdings: list[dict], products) -> list[dict]:
    """NGL stations inside at least one GUNW footprint, flagged when their data overlap that frame's pair dates."""
    out = []
    for s in holdings:
        ps = [p for p in products if p.covers(s["lat"], s["lon"])]
        if not ps:
            continue
        first, last = min(_d(p.ref) for p in ps), max(_d(p.sec) for p in ps)
        out.append({**s, "n_pairs": len(ps), "overlaps_nisar": s["start"] <= last and s["end"] >= first,
                    "start": str(s["start"]), "end": str(s["end"])})
    return sorted(out, key=lambda s: (not s["overlaps_nisar"], -s["n_pairs"], s["station"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--station", default=DEFAULT_STATION, help="NGL 4-character station id (default RABT)")
    ap.add_argument("--auto", action="store_true", help="validate every NGL station inside the downloaded frames")
    ap.add_argument("--window", type=int, default=WINDOW_DAYS, help="GPS days averaged around each date (+-)")
    ap.add_argument("--offline-sample", nargs="?", const="", default=None, metavar="DIR",
                    help="read the GPS files from DIR instead of NGL (default DIR: <data>/GPS_sample)")
    ap.add_argument("--data", help="data folder (default: NISAR_DATA or ../data)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    if a.data:
        os.environ["NISAR_DATA"] = a.data
    sys.path.insert(0, str(HERE))
    import catalog
    from config import DATA_DIR
    sample = None if a.offline_sample is None else Path(a.offline_sample or DATA_DIR / "GPS_sample")
    source = Source(sample)
    products = [p for p in catalog.load() if p.level == "GUNW"]
    out = Path(a.out)
    if not products:
        print(f"No GUNW product in {DATA_DIR}: nothing to compare.")
    names = [a.station]
    if a.auto:
        try:
            found = stations_in_frames(parse_holdings(source.holdings()), products)
        except Exception as e:                               # noqa: BLE001
            print(f"Could not read the NGL station list: {type(e).__name__}: {e}")
            return 2
        out.mkdir(parents=True, exist_ok=True)
        (out / "gps_stations.json").write_text(json.dumps(found, indent=1), encoding="utf-8")
        names = [s["station"] for s in found if s["overlaps_nisar"]]
        print(f"{len(found)} NGL station(s) inside the frames, {len(names)} with GPS data in the NISAR window: "
              + (", ".join(names) or "none") + f"  (list: {out / 'gps_stations.json'})")
        if not names:
            return 2
    code = 2
    for sta in names:
        rep = validate(sta, source, products, a.window, out)
        s = rep.get("summary", {}).get("all", {})
        print(f"{rep['station']['station']}: {rep['status']} — {rep['message']}")
        if s.get("n_pairs"):
            print(f"  pairs {s['n_pairs']}  RMS {s['rms_mm']} mm  RMS after mean removal "
                  f"{s['rms_after_removing_mean_mm']} mm  correlation {s['correlation']}  ({rep['summary']['sign_hint']})")
            code = 0
        print(f"  written: {out / ('gps_' + rep['station']['station'])}.json/.md/.png")
    return code


if __name__ == "__main__":
    sys.exit(main())
