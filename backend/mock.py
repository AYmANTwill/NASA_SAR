"""Fake but realistic responses, so the interface can be built before any data is processed.
Every mock response carries "mock": true."""

ASK = {
    "mock": True, "question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lang": "fr",
    "type": "slow_motion", "place": {"lat": 34.64, "lon": -5.17, "name": "al wahda"},
    "verdict": "Du 20260622 au 20261020 (9 paires), le point a bougé de -6.2 mm, soit -18.9 mm/an le long de la ligne de visée. Vertical : -15.1 mm/an.",
    "confidence": "medium", "confidence_reasons": ["signal = 3.4× the noise floor"], "alert_level": "orange",
    "layers": [{"url": "/layers/mock_disp.png", "bounds": [[34.0, -6.0], [35.3, -4.3]], "vmin": -3, "vmax": 3,
                "cmap": "RdBu_r", "title": "Displacement (cm), ascending, 20261008→20261020"}],
    "series": [{"track": 116, "frame": 19, "direction": "ascending", "n_pairs": 9, "velocity_mm_yr": -18.9,
                "series": [{"date": "20260622", "los_mm": 0.0}, {"date": "20260704", "los_mm": -0.8},
                           {"date": "20260716", "los_mm": -1.1}, {"date": "20260728", "los_mm": -2.0},
                           {"date": "20260809", "los_mm": -2.6}, {"date": "20260821", "los_mm": -3.4},
                           {"date": "20260902", "los_mm": -4.1}, {"date": "20260914", "los_mm": -4.6},
                           {"date": "20261008", "los_mm": -5.7}, {"date": "20261020", "los_mm": -6.2}]}],
    "profile": [{"km": k / 2, "value": round(-0.3 * (1 - abs(k) / 40), 2)} for k in range(-40, 41, 4)],
    "evidence": [{"source": "Open-Meteo", "status": "none", "summary": "41.2 mm of rain between 2026-06-22 and 2026-10-20"},
                 {"source": "OpenStreetMap", "status": "agrees", "summary": "1 dams, 35 buildings", "exposed": True}],
    "cannot_say": "Une tendance sur quelques mois ne permet pas de dater une rupture ; une inspection sur place reste nécessaire.",
    "steps": [{"step": "question type: slow_motion", "ok": True, "ms": 0},
              {"step": "found 25 interferograms covering the point", "ok": True, "ms": 0},
              {"step": "time series (small-baseline inversion)", "ok": True, "ms": 2140},
              {"step": "rain over the period", "ok": True, "ms": 410},
              {"step": "what is exposed (OpenStreetMap)", "ok": True, "ms": 880}],
    "data_used": ["GUNW_T116_F019_20261008_20261020"], "facts": {},
}

DISCOVERIES = {"mock": True, "n_geometries": 11, "zones": [
    {"id": "zone-1", "rank": 1, "lat": 32.24, "lon": -7.95, "area_km2": 3.1, "mean": -24.0, "peak": 41.0,
     "unit": "mm/yr", "snr": 6.2, "confidence": "high", "alert_level": "orange", "track": 44, "frame": 18,
     "direction": "ascending", "exposure": {"buildings": 4, "quarries_mines": 2}, "exposed": False},
    {"id": "zone-2", "rank": 2, "lat": 33.59, "lon": -7.55, "area_km2": 1.4, "mean": -11.0, "peak": 19.0,
     "unit": "mm/yr", "snr": 3.8, "confidence": "medium", "alert_level": "orange", "track": 23, "frame": 72,
     "direction": "descending", "exposure": {"buildings": 412}, "exposed": True}]}

WATCH = {"mock": True, "id": "a1b2c3d4", "lat": 34.64, "lon": -5.17, "question": ASK["question"], "lang": "fr",
         "level": "orange", "last_verdict": ASK["verdict"],
         "next_passes": [{"track": 116, "frame": 19, "direction": "ascending", "next_pass": "2026-11-13"},
                         {"track": 95, "frame": 71, "direction": "descending", "next_pass": "2026-11-15"}],
         "notifications": [{"at": "2026-11-13 08:00", "from": "yellow", "to": "orange",
                            "message": "Alerte NISAR Pulse : le niveau passe de jaune à orange."}]}
