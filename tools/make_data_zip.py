"""Builds a zip of the processed data folder to share with the team (data is not in git).
Leaves out the unused full-resolution 'wrappedInterferogram' coherence layer (~4.4 GB), the
temporary download folder.
Run from the repo root:  python tools/make_data_zip.py [data_folder] [output.zip]
Defaults: ./data  ->  ./NISAR_Pulse_data.zip"""
import os
import sys
import time
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(REPO, "data")
OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(REPO, "NISAR_Pulse_data.zip")
SKIP_FILE = "wrappedInterferogram_HH_coherenceMagnitude.tif"   # exact name (NOT the unwrapped one)

files = []
for top in ("GUNW", "SME2"):
    for dp, _, fn in os.walk(os.path.join(ROOT, top)):
        files += [os.path.join(dp, f) for f in fn if f != SKIP_FILE]
for extra in ("manifest.csv",):
    if os.path.exists(os.path.join(ROOT, extra)):
        files.append(os.path.join(ROOT, extra))
files.sort()
total = sum(os.path.getsize(f) for f in files)
print(f"{len(files)} files, {total/1e9:.2f} GB -> {OUT}")
done, t0 = 0, time.time()
# ZIP_STORED: the GeoTIFFs are already compressed, so storing is fast and loses nothing
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
    for i, f in enumerate(files, 1):
        z.write(f, os.path.relpath(f, ROOT))
        done += os.path.getsize(f)
        rate = done / max(time.time() - t0, 1e-6)
        print(f"\r[{i}/{len(files)}] {done/1e9:.2f}/{total/1e9:.2f} GB  "
              f"{rate/1e6:.0f} MB/s  reste {(total-done)/max(rate,1)/60:.1f} min   ", end="", flush=True)
with zipfile.ZipFile(OUT) as z:
    bad = z.testzip()
print(f"\nDone: {os.path.getsize(OUT)/1e9:.2f} GB, {'archive OK' if bad is None else 'CORRUPT: ' + bad}")
