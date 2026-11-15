"""Internal-only preview of generated water-analysis artifacts.

Run from the repository root with:
    streamlit run backend/water/preview_app.py

This is not part of the NISAR Pulse demo frontend.
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"

st.set_page_config(page_title="Water pipeline preview", layout="wide")
st.title("Water pipeline — internal preview")
st.caption("Generated files only; the product UI remains the React/MapLibre frontend.")

figures = OUTPUTS / "figures"
for name in ("hero.png", "timeseries.png", "validation.png", "locator.png", "timelapse.gif"):
    path = figures / name
    if path.exists():
        st.subheader(name)
        st.image(str(path), use_container_width=True)

for name in ("reservoir_case.json", "haouz_flooded_area.json", "classifier_metrics.json",
             "raster_index.json"):
    path = OUTPUTS / name
    if path.exists():
        with st.expander(name):
            st.json(json.loads(path.read_text(encoding="utf-8")))

