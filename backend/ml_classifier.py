"""Change classifier: tells WHAT changed between two GCOV acquisitions, per pixel.

Classes: 0 stable, 1 flooded, 2 burned, 3 vegetation loss.
Features: HH/HV in dB before and after, their differences, the HH/HV ratio, local texture.
Labels come from independent maps (Copernicus GFM flood extent, FIRMS fire points, forest-loss maps)
rasterised on the GCOV grid. Model: XGBoost (falls back to RandomForest if xgboost is missing).
Evaluation is done on an event NEVER seen during training."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

import raster
from config import CACHE_DIR

CLASSES = ["stable", "flooded", "burned", "vegetation_loss"]
MODEL_PATH = CACHE_DIR / "change_classifier.joblib"


def _db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(a > 0, a, np.nan))


def features(before, after) -> tuple[np.ndarray, dict]:
    """before / after: catalog Products of level GCOV on the same grid. Returns (H, W, F) array."""
    hb, prof = raster.read(before.files["hh"])
    ha, _ = raster.read(after.files["hh"])
    vb = raster.read(before.files["hv"])[0] if "hv" in before.files else np.full_like(hb, np.nan)
    va = raster.read(after.files["hv"])[0] if "hv" in after.files else np.full_like(hb, np.nan)
    hb, ha, vb, va = _db(hb), _db(ha), _db(vb), _db(va)
    tex = lambda a: ndimage.generic_filter(np.nan_to_num(a, nan=-30), np.std, size=5)
    f = np.stack([hb, ha, vb, va, ha - hb, va - vb, ha - va, hb - vb, tex(ha), tex(va)], axis=-1)
    return f.astype("float32"), prof


FEATURE_NAMES = ["hh_before", "hh_after", "hv_before", "hv_after", "d_hh", "d_hv", "ratio_after",
                 "ratio_before", "texture_hh_after", "texture_hv_after"]


def rasterize_points(points: list[tuple[float, float]], prof, buffer_m=375) -> np.ndarray:
    """FIRMS fire points (lat, lon) -> boolean mask on the grid (VIIRS pixel ~375 m)."""
    m = np.zeros((prof["height"], prof["width"]), bool)
    k = max(1, int(buffer_m / raster.pixel_size_m(prof)))
    for lat, lon in points:
        r, c = raster.to_pixel(prof, lat, lon)
        m[max(r - k, 0): r + k + 1, max(c - k, 0): c + k + 1] = True
    return m


def labels_from_masks(shape, flooded=None, burned=None, veg_loss=None) -> np.ndarray:
    y = np.zeros(shape, "int8")
    for cls, m in [(1, flooded), (2, burned), (3, veg_loss)]:
        if m is not None:
            y[m] = cls
    return y


def sample(F, y, per_class=5000, seed=0):
    rng = np.random.default_rng(seed)
    X, Y = [], []
    ok = np.isfinite(F).all(axis=-1)
    for cls in range(len(CLASSES)):
        idx = np.flatnonzero((y == cls) & ok)
        if idx.size == 0:
            continue
        pick = rng.choice(idx, min(per_class, idx.size), replace=False)
        X.append(F.reshape(-1, F.shape[-1])[pick])
        Y.append(np.full(pick.size, cls))
    return np.concatenate(X), np.concatenate(Y)


def _model():
    try:
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
                             colsample_bytree=0.8, tree_method="hist", eval_metric="mlogloss")
    except ImportError:
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=300, max_depth=14, n_jobs=-1, class_weight="balanced")


def train(train_sets: list[tuple[np.ndarray, np.ndarray]], test_set: tuple[np.ndarray, np.ndarray]) -> dict:
    """train_sets / test_set: (features H×W×F, labels H×W). Test = a different event."""
    import joblib
    from sklearn.metrics import classification_report, confusion_matrix
    X = np.concatenate([sample(F, y)[0] for F, y in train_sets])
    Y = np.concatenate([sample(F, y)[1] for F, y in train_sets])
    present = np.unique(Y)
    remap = {c: i for i, c in enumerate(present)}
    model = _model()
    model.fit(X, np.vectorize(remap.get)(Y))
    Xt, Yt = sample(*test_set, per_class=20000, seed=1)
    keep = np.isin(Yt, present)
    pred = present[model.predict(Xt[keep])]
    names = [CLASSES[c] for c in present]
    report = classification_report(Yt[keep], pred, labels=present, target_names=names, output_dict=True,
                                   zero_division=0)
    joblib.dump({"model": model, "classes": present.tolist()}, MODEL_PATH)
    imp = getattr(model, "feature_importances_", None)
    metrics = {"classes": names, "report": report,
               "confusion": confusion_matrix(Yt[keep], pred, labels=present).tolist(),
               "feature_importance": None if imp is None else dict(zip(FEATURE_NAMES, map(float, imp))),
               "n_train": int(len(Y)), "n_test": int(keep.sum())}
    (CACHE_DIR / "change_classifier_metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    return metrics


def predict(before, after, name: str) -> dict:
    import joblib
    bundle = joblib.load(MODEL_PATH)
    F, prof = features(before, after)
    flat = F.reshape(-1, F.shape[-1])
    ok = np.isfinite(flat).all(axis=1)
    out = np.full(flat.shape[0], np.nan, "float32")
    out[ok] = np.array(bundle["classes"])[bundle["model"].predict(flat[ok])]
    cls = out.reshape(F.shape[:2])
    shown = np.where(cls > 0, cls, np.nan)
    layer = raster.render_png(shown, prof, f"classes_{name}", "Set1", 1, 3)
    px_ha = raster.pixel_size_m(prof) ** 2 / 1e4
    areas = {CLASSES[c]: round(float((cls == c).sum() * px_ha), 1) for c in bundle["classes"] if c > 0}
    return {"areas_ha": areas, "layer": layer}
