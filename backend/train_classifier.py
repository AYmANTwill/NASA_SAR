"""Train and evaluate the change classifier.

Describe your labelled events in training_events.json, e.g.:
[
  {"before": "GCOV_T015_F019_20261001_20261001", "after": "GCOV_T015_F019_20261013_20261013",
   "flood_mask": "labels/gharb_gfm_flood.tif", "fires_csv": null, "veg_loss_mask": null, "role": "train"},
  {"before": "...", "after": "...", "fires_csv": "labels/firms_rif.csv", "role": "test"}
]
Masks are GeoTIFFs on the same grid as the GCOV layers (0/1). fires_csv = FIRMS export (latitude, longitude).
Usage:  python train_classifier.py training_events.json"""
import csv
import json
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):          # redirected stdout on Windows is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import catalog
import ml_classifier as mc
import raster


def build(ev):
    b, a = catalog.by_id(ev["before"]), catalog.by_id(ev["after"])
    F, prof = mc.features(b, a)
    masks = {}
    for key in ("flood_mask", "veg_loss_mask"):
        if ev.get(key):
            masks[key] = raster.read(ev[key])[0] > 0.5
    burned = None
    if ev.get("fires_csv"):
        with open(ev["fires_csv"]) as f:
            pts = [(float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(f)]
        burned = mc.rasterize_points(pts, prof)
    y = mc.labels_from_masks(F.shape[:2], masks.get("flood_mask"), burned, masks.get("veg_loss_mask"))
    return F, y


if __name__ == "__main__":
    evs = json.load(open(sys.argv[1]))
    train = [build(e) for e in evs if e.get("role", "train") == "train"]
    test = [build(e) for e in evs if e.get("role") == "test"]
    if not train or not test:
        sys.exit("need at least one 'train' and one 'test' event")
    m = mc.train(train, test[0])
    print(json.dumps({k: m[k] for k in ("classes", "n_train", "n_test", "confusion")}, indent=1))
    for c in m["classes"]:
        r = m["report"][c]
        print(f"{c:<16} precision {r['precision']:.2f}  recall {r['recall']:.2f}  f1 {r['f1-score']:.2f}")
