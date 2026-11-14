"""Independent evidence: free public APIs that confirm or contradict what the radar shows.
Every function returns {"source", "status": agrees|disagrees|none|unavailable, "summary", "items"}
and never raises (a missing source must not break an answer)."""
from __future__ import annotations

import math
from datetime import date, timedelta

import requests

from config import FIRMS_MAP_KEY, OFFLINE

TIMEOUT = 15
# Sent with every outside request: Overpass answers 406 to a request without a User-Agent. Generic, no personal data.
HEADERS = {"User-Agent": "NISAR-Pulse/0.1 (NASA Space Apps 2026 research prototype)"}


def _iso(d: str) -> str:
    d = d.replace("-", "")[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _unavailable(source, err):
    return {"source": source, "status": "unavailable", "summary": f"{source} unreachable ({err})", "items": []}


def _km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def earthquakes(lat, lon, start, end, radius_km=150, min_mag=4.0) -> dict:
    """USGS catalogue: earthquakes between the two radar passes."""
    if OFFLINE:
        return _unavailable("USGS", "offline mode")
    try:
        r = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", timeout=TIMEOUT, headers=HEADERS, params=dict(
            format="geojson", starttime=_iso(start), endtime=_iso(end), latitude=lat, longitude=lon,
            maxradiuskm=radius_km, minmagnitude=min_mag, orderby="magnitude"))
        r.raise_for_status()
        items = []
        for f in r.json()["features"][:10]:
            p, (qlon, qlat, depth) = f["properties"], f["geometry"]["coordinates"]
            items.append({"magnitude": p["mag"], "place": p["place"], "time_ms": p["time"],
                          "lat": qlat, "lon": qlon, "depth_km": depth, "url": p["url"],
                          "distance_km": round(_km(lat, lon, qlat, qlon), 1)})
        if not items:
            return {"source": "USGS", "status": "none", "summary": f"no M{min_mag}+ earthquake within {radius_km} km", "items": []}
        top = items[0]
        return {"source": "USGS", "status": "agrees" if top["magnitude"] >= 5.5 else "none",
                "summary": f"M{top['magnitude']} {top['place']}, {top['distance_km']} km away", "items": items}
    except Exception as e:
        return _unavailable("USGS", e)


def rainfall(lat, lon, start, end) -> dict:
    """Open-Meteo archive (ERA5): daily rain between two dates."""
    if OFFLINE:
        return _unavailable("Open-Meteo", "offline mode")
    try:
        s, e = _iso(start), _iso(end)
        if date.fromisoformat(e) > date.today() - timedelta(days=5):
            e = (date.today() - timedelta(days=5)).isoformat()
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=TIMEOUT, headers=HEADERS, params=dict(
            latitude=lat, longitude=lon, start_date=s, end_date=e, daily="precipitation_sum", timezone="UTC"))
        r.raise_for_status()
        d = r.json()["daily"]
        days = [{"date": t, "mm": v} for t, v in zip(d["time"], d["precipitation_sum"]) if v is not None]
        total = round(sum(x["mm"] for x in days), 1)
        wettest = max(days, key=lambda x: x["mm"]) if days else None
        return {"source": "Open-Meteo", "status": "agrees" if total >= 50 else "none",
                "summary": f"{total} mm of rain between {s} and {e}"
                           + (f" (max {wettest['mm']} mm on {wettest['date']})" if wettest else ""),
                "total_mm": total, "items": days}
    except Exception as e:
        return _unavailable("Open-Meteo", e)


def fires(lat, lon, end, days=10, half_deg=0.25) -> dict:
    """NASA FIRMS active fires (VIIRS). Needs a free MAP_KEY."""
    if OFFLINE or not FIRMS_MAP_KEY:
        return _unavailable("FIRMS", "offline mode" if OFFLINE else "no FIRMS_MAP_KEY set")
    try:
        bbox = f"{lon-half_deg},{lat-half_deg},{lon+half_deg},{lat+half_deg}"
        start = (date.fromisoformat(_iso(end)) - timedelta(days=days - 1)).isoformat()
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{bbox}/{min(days,10)}/{start}"
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        lines = [l.split(",") for l in r.text.strip().splitlines()]
        head, rows = lines[0], lines[1:]
        items = [dict(zip(head, row)) for row in rows][:200]
        return {"source": "FIRMS", "status": "agrees" if items else "none",
                "summary": f"{len(items)} fire detections within ~25 km in the {days} days before {_iso(end)}",
                "items": items[:20]}
    except Exception as e:
        return _unavailable("FIRMS", e)


def exposure(lat, lon, radius_m=2000) -> dict:
    """OpenStreetMap (Overpass): what is exposed around the point."""
    if OFFLINE:
        return _unavailable("OpenStreetMap", "offline mode")
    q = f"""[out:json][timeout:20];
    (way["building"](around:{radius_m},{lat},{lon});
     way["highway"~"motorway|trunk|primary|secondary"](around:{radius_m},{lat},{lon});
     nwr["waterway"="dam"](around:{radius_m*3},{lat},{lon});
     nwr["landuse"="quarry"](around:{radius_m*3},{lat},{lon});
     nwr["amenity"~"hospital|school"](around:{radius_m},{lat},{lon}););
    out tags center 2000;"""
    try:
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=30, headers=HEADERS)
        r.raise_for_status()
        els = r.json()["elements"]
        count = lambda k, v=None: sum(1 for e in els if k in e.get("tags", {}) and (v is None or e["tags"][k] in v))
        c = {"buildings": count("building"), "major_roads": count("highway"),
             "dams": count("waterway", {"dam"}), "quarries_mines": count("landuse", {"quarry"}),
             "hospitals_schools": count("amenity", {"hospital", "school"})}
        exposed = c["buildings"] > 20 or c["dams"] or c["hospitals_schools"]
        return {"source": "OpenStreetMap", "status": "agrees" if exposed else "none",
                "summary": ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in c.items() if v) or "nothing mapped",
                "counts": c, "exposed": bool(exposed), "items": []}
    except Exception as e:
        return _unavailable("OpenStreetMap", e)
