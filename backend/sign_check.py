"""Sign-check helper for the line-of-sight convention (STATUS H4). A HUMAN decides; this script never sets anything.

1. Prints the attributes of unwrappedPhase and of the line-of-sight vectors, read from a raw .h5 kept with --keep-raw
   (if none was kept, says how to get one and how to list its layers with tools/list_h5_layers.py).
2. Renders the Panama co-seismic line-of-sight maps (ascending and descending) with the current NISAR_LOS_SIGN.
3. Prints the expected pattern to compare against: the USGS event page, its focal mechanism and finite fault.
   The 9 Oct 2026 M7.7 is STRIKE-SLIP: expect a four-lobe (quadrant) pattern with opposite signs across the fault
   and opposite look directions, not a single uplift bulge. The synthetic Panama of the tests (25 cm uplift) is NOT
   sign evidence.
4. Prints the exact commands to record the decision (NISAR_LOS_SIGN, NISAR_LOS_SIGN_VERIFIED).

Documented convention (Phase A): NISAR GUNW unwrapped phase is positive = motion away from the sensor (ARIA-tools,
MintPy prep_nisar), so displacement = -lambda/(4 pi) x phase with NISAR_LOS_SIGN=1 is positive = toward the satellite.

Usage (from backend/):  python sign_check.py [--data D:\\nisar_data] [--out ..\\results_out]
Writes <out>/sign_check.md and <out>/sign_check.png.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "results_out"
EVENT = {"id": "us6000u18k", "name": "Panama M7.7, 9 Oct 2026 17:56:06 UTC", "utc": "20261009T175606",
         "lat": 7.59, "lon": -80.77, "mechanism": "strike-slip"}
USGS = "https://earthquake.usgs.gov/earthquakes/eventpage/us6000u18k"
ATTR_NAMES = ("unwrappedPhase", "losUnitVectorX", "losUnitVectorY")


def _text(v) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return str(v.tolist() if hasattr(v, "tolist") else v)


def raw_attributes(h5_path: Path) -> dict:
    """{dataset path: {attribute: value}} for unwrappedPhase and the LOS unit vectors (read only)."""
    import h5py
    out = {}
    with h5py.File(h5_path, "r") as h5:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset) and name.split("/")[-1] in ATTR_NAMES:
                out[name] = {k: _text(v) for k, v in obj.attrs.items()}
        h5.visititems(visit)
    return out


def coseismic(products) -> list:
    import catalog
    ps = [p for p in products if p.level == "GUNW" and p.covers(EVENT["lat"], EVENT["lon"])]
    return sorted(catalog.straddling(ps, EVENT["utc"], "exact"), key=lambda p: (p.direction, p.track, p.frame))


def render(pairs, path: Path) -> list[dict]:
    """One panel per co-seismic pair (LOS cm with the current sign, epicentre marked). Returns per-pair facts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio.transform as rt
    from pyproj import Transformer

    from recipes import displacement
    n = max(1, len(pairs))
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 4.0 * rows), squeeze=False)
    facts = []
    for ax in axes.ravel()[len(pairs):]:
        ax.axis("off")
    if not pairs:
        axes[0, 0].text(0.5, 0.5, "no Panama co-seismic pair in the data", ha="center", va="center")
    for ax, p in zip(axes.ravel(), pairs):
        d, _, prof, _ = displacement.los_cm(p)
        d = d - np.nanmedian(d) if np.isfinite(d).any() else d
        lim = float(np.nanpercentile(np.abs(d), 98)) if np.isfinite(d).any() else 1.0
        w, s, e, nn = rt.array_bounds(prof["height"], prof["width"], prof["transform"])[::-1][::-1]
        im = ax.imshow(d, cmap="RdBu_r", vmin=-lim, vmax=lim, extent=(w, e, s, nn), origin="upper")
        x, y = Transformer.from_crs(4326, prof["crs"], always_xy=True).transform(EVENT["lon"], EVENT["lat"])
        ax.plot([x], [y], marker="*", color="k", ms=12)
        ax.set_title(f"{p.direction} T{p.track} F{p.frame}\n{p.ref[:8]}→{p.sec[:8]}", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046, label="LOS cm (red = toward satellite)")
        facts.append({"product": p.id, "direction": p.direction, "track": p.track, "frame": p.frame,
                      "p98_abs_cm": round(lim, 2)})
    fig.suptitle(f"{EVENT['name']}: line-of-sight change, NISAR_LOS_SIGN={os.environ.get('NISAR_LOS_SIGN', '1')}")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return facts


def commands() -> list[str]:
    return ["# If the maps match the USGS mechanism with the current sign (red = toward the satellite):",
            '$env:NISAR_LOS_SIGN = "1"; $env:NISAR_LOS_SIGN_VERIFIED = "1"',
            "# If every lobe has the opposite sign in both look directions:",
            '$env:NISAR_LOS_SIGN = "-1"; $env:NISAR_LOS_SIGN_VERIFIED = "1"',
            "# then, in the same PowerShell window:", "python precompute.py",
            "# (bash: export NISAR_LOS_SIGN=1 NISAR_LOS_SIGN_VERIFIED=1). Undecided: change nothing."]


def report(attrs: dict, raw: Path | None, pairs_facts: list[dict], png: Path, data_dir) -> str:
    import config
    lines = ["# Sign check: line-of-sight convention (STATUS H4)", "",
             f"Current: `NISAR_LOS_SIGN={os.environ.get('NISAR_LOS_SIGN', '1')}`, "
             f"`NISAR_LOS_SIGN_VERIFIED={'1' if config.LOS_SIGN_VERIFIED else '0'}`. This script changes nothing.", "",
             f"Basis: {config.SIGN_BASIS}.", "", "## 1. Attributes in the raw file", ""]
    if raw is None:
        lines += ["No raw `.h5` was kept in the data folder. To get one (about 2 GB per file):", "",
                  "```powershell",
                  "python download_all.py run --plan plan_validation.json --part 1 --keep-raw --out D:\\nisar_validation",
                  "python tools/list_h5_layers.py D:\\nisar_validation\\GUNW\\<name>\\<name>.h5 unwrappedPhase losUnitVector",
                  "python backend\\sign_check.py --data D:\\nisar_validation",
                  "```", "",
                  "`list_h5_layers.py` prints the dataset paths; this script then prints their attributes "
                  "(description, units) from the kept file."]
    else:
        lines += [f"From `{raw.name}`:", ""]
        for path, a in attrs.items():
            lines.append(f"- `{path}`")
            lines += [f"  - {k}: {v}" for k, v in a.items()] or ["  - (no attribute)"]
    lines += ["", "## 2. Panama co-seismic maps", "", f"![maps]({png.name})", ""]
    lines += ([f"- {f['direction']} T{f['track']} F{f['frame']}: `{f['product']}` (98th percentile |LOS| {f['p98_abs_cm']} cm)"
               for f in pairs_facts] or [f"No Panama co-seismic pair found in `{data_dir}`: download "
                                         "`plan_validation.json` part 1 first."])
    lines += ["", "## 3. What to compare with", "",
              f"- USGS event page: {USGS}", f"- Focal mechanism / moment tensor: {USGS}/moment-tensor",
              f"- Finite fault: {USGS}/finite-fault", "",
              f"The event is **{EVENT['mechanism']}**: the line-of-sight map should show lobes of opposite sign on either "
              "side of the fault, and the ascending and descending maps differ (they look from opposite sides). Compare "
              "the sign of each lobe with the motion predicted by the finite-fault model projected on each look "
              "direction. Do NOT use the synthetic Panama of the tests (25 cm uplift) as sign evidence.", "",
              "## 4. Record the decision (a human runs this)", "", "```powershell", *commands(), "```", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="data folder (default: NISAR_DATA or ../data)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    if a.data:
        os.environ["NISAR_DATA"] = a.data
    sys.path.insert(0, str(HERE))
    import catalog
    from config import DATA_DIR
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pairs = coseismic(catalog.load())
    raw = next((h for p in pairs for h in sorted(p.folder.glob("*.h5"))), None)
    if raw is None:
        raw = next((h for d in sorted((Path(DATA_DIR) / "GUNW").glob("*")) if d.is_dir() for h in d.glob("*.h5")), None)
    attrs = {}
    if raw is not None:
        try:
            attrs = raw_attributes(raw)
        except Exception as e:                       # noqa: BLE001 - unreadable raw file: said in the report
            attrs = {str(raw.name): {"error": f"{type(e).__name__}: {e}"}}
    png = out / "sign_check.png"
    facts = render(pairs, png)
    md = report(attrs, raw, facts, png, DATA_DIR)
    (out / "sign_check.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Written: {out / 'sign_check.md'} and {png}")
    return 0 if pairs else 2


if __name__ == "__main__":
    sys.exit(main())
