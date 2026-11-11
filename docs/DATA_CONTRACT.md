# Data contract v1

All JSON files are UTF-8. All coordinate reference systems are WGS84 / EPSG:4326. No auth or API keys. Paths are relative to VITE_DATA_URL (default /data). Files must be available over HTTP, not file://. Remote endpoints must allow CORS.

## cases.json

Array of case objects:

    {
      "id": "venezuela",
      "name": "Venezuela",
      "subtitle": "Coastal earthquakes",
      "phenomenon": "earthquake",
      "accentColor": "#FF6B35",
      "center": [10.6, -66.9],
      "zoom": 7.2,
      "pitch": 42,
      "bearing": -12,
      "bbox": [-68.1, 9.76, -65.7, 11.44],
      "dates": ["2026-05-14", "2026-05-26"],
      "description": "Human-readable interpretation and uncertainty.",
      "kpis": {
        "displacement_mm": 128,
        "affected_area_km2": 2840,
        "backscatter_db": -4.8,
        "coherence": 0.42,
        "affected_population": 84000
      },
      "classProbabilities": {
        "earthquake": 0.94, "flood": 0.015,
        "deforestation": 0.015, "waterStress": 0.015,
        "subsidence": 0.015
      },
      "predictedClass": "earthquake",
      "confidence": 0.94,
      "contextValue": "M7.2 / M7.5",
      "contextLabel": "Simulated seismic sequence"
    }

center is **[latitude, longitude]**; bbox is **[west, south, east, north]**. GeoJSON coordinates use **[longitude, latitude]**. Dates must be ordered ascending and nonempty. IDs must be URL-safe. The five allowed class keys are earthquake, waterStress, flood, deforestation, subsidence. Probabilities are fractions 0–1 and should sum to 1. Confidence is a fraction, not a percentage.

subtitle, contextValue and contextLabel are presentation extensions to the brief. Supply them along with all fields above. Case KPIs represent the full case window; selected-date metrics come from the time series.

## Raster files

    {caseId}/{product}/{YYYY-MM-DD}.png
    {caseId}/{product}/{YYYY-MM-DD}.json

Products: gcov, gunw, coherence, goff, ndvi, rainfall. Supply every enabled product for every declared date. A missing product should be removed from the UI configuration or exported as a fully transparent raster with metadata. PNGs are RGBA, north-up, no rotation. Bounds describe pixel outer edges, not pixel centers. Use geographic (longitude/latitude) raster grids. Avoid antimeridian-crossing images; split them upstream.

Sidecar:

    {
      "bounds": [-68.1, 9.76, -65.7, 11.44],
      "colormap": ["#287dff", "#162d49", "#ff633e"],
      "unit": "dB", "min": -12, "max": 12,
      "simulated": true
    }

min/max describe the physical color scale, not PNG byte values. GCOV: dB, diverging centered at 0. GUNW: signed line-of-sight mm; if using cyclic colors, disclose that they are display colors rather than wrapped phase. Coherence: unitless [0,1], viridis-like. GOFF: meters. NDVI: unitless [-1,1] or a declared restricted range. Rainfall: accumulated mm over the documented interval.

Transparent pixels represent no data. Alpha may also express visual emphasis in demo rasters. PNG alone does not retain physical values; numeric pixel interrogation requires a separate value grid/API. The current inspector consequently labels its case-level series.

### Python GeoTIFF export

This example reprojects into a geographic, north-up grid and writes a diverging RGBA visualization. Install rasterio, numpy, matplotlib and pillow. Supply vmin/vmax from your product definition; do not normalize each date independently.

    import json
    from pathlib import Path
    import numpy as np
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.transform import array_bounds
    from PIL import Image
    from matplotlib import colormaps

    source = "gcov_change_db.tif"
    out = Path("public/data/venezuela/gcov/2026-06-07")
    out.parent.mkdir(parents=True, exist_ok=True)
    vmin, vmax = -12.0, 12.0
    with rasterio.open(source) as src:
        transform, width, height = calculate_default_transform(
            src.crs, "EPSG:4326", src.width, src.height, *src.bounds
        )
        values = np.full((height, width), np.nan, dtype="float32")
        src_values = src.read(1, masked=True).astype("float32").filled(np.nan)
        reproject(
            source=src_values, destination=values,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=transform, dst_crs="EPSG:4326",
            src_nodata=np.nan, dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )
    valid = np.isfinite(values)
    normalized = np.clip(
        (np.nan_to_num(values, nan=vmin) - vmin) / (vmax - vmin), 0, 1
    )
    rgba = (colormaps["RdBu_r"](normalized) * 255).astype("uint8")
    rgba[..., 3] = np.where(valid, 210, 0).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(str(out) + ".png")
    west, south, east, north = array_bounds(height, width, transform)
    metadata = {
        "bounds": [west, south, east, north],
        "colormap": ["#053061", "#f7f7f7", "#67001f"],
        "unit": "dB", "min": vmin, "max": vmax, "simulated": False
    }
    Path(str(out) + ".json").write_text(json.dumps(metadata), encoding="utf-8")

Use nearest-neighbor resampling for categorical labels. Validate geolocation and nodata masks with the SAR analyst before publication.

## Context GeoJSON

Files: events.geojson, fires.geojson, floodExtent.geojson, infrastructure.geojson, classification.geojson.

Each is a FeatureCollection. Empty collections are supported. Every feature needs properties.caseId matching cases.json. Point coordinates are [lng,lat]. Polygon rings must close. Useful properties: name, class, magnitude, height (illustrative extrusion), value, simulated. Events/fires use Points; flood/classification/infrastructure use Polygons. Classification uses the five keys above. Current context rendering filters by caseId; context collections cover the whole case rather than filtering by timestamp.

## timeseries/{caseId}.json

One row for every case date, in exactly the same order:

    [
      {
        "date": "2026-05-14",
        "backscatter_db": -0.5,
        "coherence": 0.91,
        "displacement_mm": 0,
        "rainfall_mm": 12,
        "ndvi": 0.8
      }
    ]

All numeric fields must be finite. No NaN/Infinity. Rainfall is interval accumulation. Define the LOS sign convention in each case description. Missing observations should be resolved or documented upstream; do not fabricate interpolation without disclosing it.

## alerts.json

    [
      {
        "id": "venezuela-0",
        "caseId": "venezuela",
        "class": "earthquake",
        "severity": "high",
        "confidence": 0.94,
        "lat": 10.6,
        "lng": -66.9,
        "timestamp": "2026-06-07T10:24:00Z",
        "message": "Surface displacement detected"
      }
    ]

severity is high or moderate. timestamp is an ISO UTC instant. Alerts sort newest first. Clicking selects the case, centers the map and opens the location inspector.

## Responsibilities

Data engineering: paths, dates, CRS, CORS, schema consistency and provenance.
SAR analyst: calibrated units, masks, bounds, sign conventions and stable color ranges.
ML engineer: probabilities, confidence calibration and classified polygons.
Frontend: visualization and interaction only; no scientific inference is executed here.

Treat scientific text, attributions and files as trusted reviewed exports. Do not embed HTML in JSON fields. Keep any observation provenance and licenses alongside your exports.

### Optional numeric sampling grid

A sidecar may include sampleGrid: {width, height, values}. values is a row-major array (north to south, west to east), with null for nodata. It contains physical values in the sidecar unit, not colors. The mock exporter supplies a 40×40 grid so hover readouts correspond to the generated field. The UI uses nearest-cell sampling and displays no numeric value outside the grid or over nodata. Real exports may omit this extension; the raster and all other UI remain usable. Include calibrated data at an appropriate resolution for real pixel interrogation.
