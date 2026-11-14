"""Recipe 'soil_moisture': NISAR Level-3 SME2 product, value at a point and series over passes."""
from __future__ import annotations

import numpy as np

import raster
from catalog import Product
from config import SM_UNCERTAINTY

NAME_HINTS = ["soilMoisture", "soil_moisture", "SM"]


def _read(p: Product):
    """Returns (array, prof-like dict) of the soil-moisture grid. Dataset names are discovered."""
    import h5py
    from rasterio.transform import from_origin
    with h5py.File(p.files["h5"], "r") as h5:
        cands = []
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset) and obj.ndim == 2 and obj.dtype.kind == "f":
                base = name.split("/")[-1]
                # real files: science/LSAR/SME2/grids/soilMoisture (the final product) beside
                # soilMoistureUncertainty and algorithmCandidates/*/soilMoisture -> prefer exact name, shortest path
                score = 3 if base == "soilMoisture" else 1 if any(h.lower() in base.lower() for h in NAME_HINTS) \
                    and "uncertainty" not in base.lower() else 0
                cands.append((score, -name.count("/"), name))
        h5.visititems(visit)
        if not cands:
            raise RuntimeError("no 2-D float dataset in SME2 file")
        name = max(cands)[2]
        arr = h5[name][()].astype("float32")
        fill = h5[name].attrs.get("_FillValue")
        if fill is not None:
            arr[arr == fill] = np.nan
        arr[(arr < 0) | (arr > 1)] = np.nan
        grp = "/" + "/".join(name.split("/")[:-1])
        def find(base):
            g = grp
            while g:
                if f"{g}/{base}" in h5:
                    return h5[f"{g}/{base}"]
                g = g.rsplit("/", 1)[0]
            return None
        x, y, pr = find("xCoordinates"), find("yCoordinates"), find("projection")
        x, y = x[()], y[()]
        epsg = int(pr.attrs.get("epsg_code", pr[()])) if pr is not None else 4326
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    prof = dict(transform=from_origin(float(x[0]) - dx / 2, float(y[0]) - dy / 2, dx, -dy),
                crs=f"EPSG:{epsg}", width=arr.shape[1], height=arr.shape[0])
    return arr, prof, name


def _uncertainty(p: Product, prof, lat: float, lon: float, radius_m: float):
    """Median retrieval uncertainty (m3/m3) around the point, from the product's soilMoistureUncertainty layer."""
    import h5py
    try:
        with h5py.File(p.files["h5"], "r") as h5:
            hits = []
            h5.visititems(lambda n, o: hits.append(n) if n.split("/")[-1] == "soilMoistureUncertainty"
                          and isinstance(o, h5py.Dataset) and o.ndim == 2 and "algorithmCandidates" not in n else None)
            if not hits:
                return None
            u = h5[sorted(hits, key=lambda n: n.count("/"))[0]][()].astype("float32")
        u[(u <= 0) | (u >= 1)] = np.nan
        w = raster.window(u, prof, lat, lon, radius_m)
        return float(np.nanmedian(w)) if np.isfinite(w).any() else None
    except Exception:
        return None


def analyze(products: list[Product], lat: float, lon: float, radius_m: float = 3000) -> dict:
    series, latest = [], None
    for p in sorted(products, key=lambda p: p.ref):
        try:
            arr, prof, ds = _read(p)
        except Exception as e:
            series.append({"date": p.ref[:8], "value": None, "error": str(e)})
            continue
        w = raster.window(arr, prof, lat, lon, radius_m)
        v = float(np.nanmedian(w)) if np.isfinite(w).any() else None
        series.append({"date": p.ref[:8], "value": None if v is None else round(v, 3), "track": p.track})
        latest = (p, arr, prof, ds)
    vals = [s["value"] for s in series if s.get("value") is not None]
    if not latest or not vals:
        return {"error": "no readable soil-moisture value at this point", "series": series}
    p, arr, prof, ds = latest
    mean = float(np.mean(vals))
    unc = _uncertainty(p, prof, lat, lon, radius_m)
    unc = SM_UNCERTAINTY if unc is None else unc
    anomaly = vals[-1] - mean
    layer = raster.render_png(arr, prof, f"sm_{p.id}", "YlGnBu", 0.0, 0.5)
    layer["title"] = f"Soil moisture (m³/m³), {p.ref[:8]}"
    return {"latest_date": series[-1]["date"], "latest_m3m3": vals[-1], "mean_m3m3": round(mean, 3),
            "anomaly_m3m3": round(anomaly, 3), "uncertainty_m3m3": round(unc, 3),
            "within_uncertainty": bool(abs(round(anomaly, 3)) < round(unc, 3)), "n_passes": len(vals), "series": series,
            "dataset": ds, "layer": layer}
