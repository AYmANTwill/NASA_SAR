"""Fake but realistic responses, so the interface can be built before any data is processed.
Every mock response carries "mock": true."""

_SLOW_FACTS = {"velocity_mm_yr": None, "velocity_sigma": None, "total_mm": -6.2, "noise_mm": 2.1, "n_pairs": 8,
               "first_date": "20260622", "last_date": "20261020", "span_days": 120, "min_rate_days": 365,
               "crid": "P05023", "maturity": "provisional", "chain_connected": True, "n_components": 1,
               "unmeasured_dates": [], "acceleration": None}
ASK = {
    "mock": True, "question": "Le terrain autour du barrage Al Wahda bouge-t-il ?", "lang": "fr",
    "type": "slow_motion", "place": {"lat": 34.598, "lon": -5.198, "name": "al wahda"}, "event_time": None,
    "verdict": "Du 22/06/2026 au 20/10/2026 (8 paires, 120 jours) (produit NISAR provisoire), le point a bougé de -6.2 mm "
               "cumulés le long de la ligne de visée (bruit par paire ± 2.1 mm). Série trop courte pour donner une vitesse "
               "en mm/an : il faut au moins 365 jours.",
    "confidence": "low", "alert_level": "yellow",
    "confidence_reasons": ["signal = 1.0× the noise floor",
                           "record of 120 days, shorter than 365: no rate, confidence capped at medium"],
    "layers": [{"url": "/layers/mock_disp.png", "bounds": [[34.0, -6.0], [35.3, -4.3]], "vmin": -3, "vmax": 3,
                "cmap": "RdBu_r", "title": "Displacement (cm), ascending, 20261008→20261020"}],
    "series": [{"track": 116, "frame": 19, "direction": "ascending", "crid": "P05023", "maturity": "provisional",
                "n_pairs": 8, "velocity_mm_yr": None, "span_days": 120, "chain_connected": True,
                "series": [{"date": "20260622", "los_mm": 0.0}, {"date": "20260704", "los_mm": -0.8},
                           {"date": "20260716", "los_mm": -1.1}, {"date": "20260821", "los_mm": -2.4},
                           {"date": "20260902", "los_mm": -3.1}, {"date": "20260914", "los_mm": -3.9},
                           {"date": "20260926", "los_mm": -4.6}, {"date": "20261008", "los_mm": -5.7},
                           {"date": "20261020", "los_mm": -6.2}]}],
    "profile": [{"km": k / 2, "value": round(-0.3 * (1 - abs(k) / 40), 2)} for k in range(-40, 41, 4)],
    "evidence": [{"source": "Open-Meteo", "status": "none", "summary": "41.2 mm of rain between 2026-06-22 and 2026-10-20"},
                 {"source": "OpenStreetMap", "status": "agrees", "summary": "1 dams, 35 buildings", "exposed": True}],
    "cannot_say": "Une tendance sur quelques mois ne permet pas de dater une rupture et n'est pas un verdict sur la sûreté "
                  "d'un barrage ; une inspection sur place reste nécessaire.",
    "steps": [{"step": "question type: slow_motion", "ok": True, "ms": 0},
              {"step": "found 9 interferograms covering the point", "ok": True, "ms": 0},
              {"step": "time series (small-baseline inversion)", "ok": True, "ms": 2140},
              {"step": "rain over the period", "ok": True, "ms": 410},
              {"step": "what is exposed (OpenStreetMap)", "ok": True, "ms": 880}],
    "data_used": ["GUNW_T116_F019_20261008_20261020"], "facts": _SLOW_FACTS,
}

_SURFACE_FACTS = {"mode": "event", "event_day": "20261010", "event_precision": "day",
                  "pre_pair": "GUNW_T044_F017_20260921_20261003", "co_pair": "GUNW_T044_F017_20261003_20261015",
                  "direction": "ascending", "track": 44, "frame": 17, "crid": "P05023", "maturity": "provisional",
                  "pre_date_before": "20260921", "pre_date_after": "20261003", "date_before": "20261003",
                  "date_after": "20261015", "window_days": 12, "loss_at_point": 0.42, "changed_km2_5km": 1.8,
                  "coherent_before_fraction_5km": 0.74, "threshold": 0.3, "n_geometries": 2, "n_usable_geometries": 2,
                  "geometries": [{"direction": "ascending", "track": 44, "frame": 17, "loss_at_point": 0.42,
                                  "changed_km2_5km": 1.8, "coherent_before_fraction_5km": 0.74, "usable": True},
                                 {"direction": "descending", "track": 23, "frame": 73, "loss_at_point": 0.37,
                                  "changed_km2_5km": 1.5, "coherent_before_fraction_5km": 0.69, "usable": True}],
                  "geometries_agree": True, "changed_km2_range": [1.5, 1.8], "ambiguous_pairs": [], "routed_from": None}
SURFACE_CHANGE = {
    "mock": True, "question": "Le sol a-t-il changé à Asni lors de la crue éclair du 10 octobre 2026 ?", "lang": "fr",
    "type": "surface_change", "place": {"lat": 31.25, "lon": -7.983, "name": "asni"},
    "event_time": {"utc": "20261010T000000", "precision": "day"},
    "verdict": "Entre le 03/10/2026 et le 15/10/2026 (12 jours, fenêtre qui contient l'événement du 10/10/2026) "
               "(produit NISAR provisoire) : perte de cohérence radar de 0.42 au point (0 = aucune, 1 = totale) ; 1.80 km² "
               "avec une perte supérieure à 0.3 dans un rayon de 5 km. Cela indique un changement de la surface (eau, boue, "
               "éboulement, travaux, végétation) ; le radar ne dit ni la cause, ni les dégâts, ni la hauteur d'eau.",
    "confidence": "medium", "alert_level": "orange",
    "confidence_reasons": ["coherence loss 0.42 (a pixel counts as changed above 0.3)",
                           "74% of the 5 km area was coherent before",
                           "every usable viewing geometry shows the same side of the threshold",
                           "coherence loss says the surface changed, not why; no independent source tests it"],
    "layers": [{"url": "/layers/mock_disp.png", "bounds": [[30.9, -8.3], [31.6, -7.6]], "vmin": 0.1, "vmax": 0.8,
                "cmap": "inferno", "title": "Surface change (coherence loss), 20261003→20261015"}],
    "series": None, "profile": None,
    "evidence": [{"source": "Open-Meteo", "status": "context", "summary": "62.0 mm of rain between 2026-10-03 and 2026-10-15"},
                 {"source": "OpenStreetMap", "status": "agrees", "summary": "6 buildings, 1 road", "exposed": True}],
    "cannot_say": "Une perte de cohérence montre que la surface a changé, pas pourquoi : eau, boue, éboulement, travaux ou "
                  "végétation. Ce n'est ni une mesure de dégâts, ni de hauteur ou de durée d'inondation ; la fenêtre dure "
                  "plusieurs jours.",
    "steps": [{"step": "question type: surface_change", "ok": True, "ms": 0},
              {"step": "found 17 interferograms covering the point", "ok": True, "ms": 0},
              {"step": "surface change (coherence loss)", "ok": True, "ms": 1900},
              {"step": "rain over the change window (context only)", "ok": True, "ms": 420}],
    "data_used": ["GUNW_T044_F017_20261003_20261015", "GUNW_T044_F017_20260921_20261003"], "facts": _SURFACE_FACTS,
}
EVENTS = {"haouz-flood-2026-10-10": SURFACE_CHANGE}

DISCOVERIES = {"mock": True, "n_geometries": 11, "zones": [
    {"id": "zone-1", "rank": 1, "lat": 32.24, "lon": -7.95, "area_km2": 3.1, "mean": -24.0, "peak": 41.0,
     "unit": "mm/yr", "snr": 6.2, "confidence": "high", "alert_level": "orange", "track": 44, "frame": 18,
     "direction": "ascending", "exposure": {"buildings": 4, "quarries_mines": 2}, "exposed": False},
    {"id": "zone-2", "rank": 2, "lat": 33.59, "lon": -7.55, "area_km2": 1.4, "mean": -11.0, "peak": 19.0,
     "unit": "mm/yr", "snr": 3.8, "confidence": "medium", "alert_level": "orange", "track": 23, "frame": 72,
     "direction": "descending", "exposure": {"buildings": 412}, "exposed": True}]}

WATCH = {"mock": True, "id": "a1b2c3d4", "lat": 34.598, "lon": -5.198, "question": ASK["question"], "lang": "fr",
         "level": "yellow", "last_verdict": ASK["verdict"],
         "next_passes": [{"track": 116, "frame": 19, "direction": "ascending", "next_pass": "2026-11-13"},
                         {"track": 95, "frame": 71, "direction": "descending", "next_pass": "2026-11-15"}],
         "notifications": [{"at": "2026-11-13 08:00", "from": "none", "to": "yellow",
                            "message": "Alerte NISAR Pulse : le niveau passe de aucune à jaune."}]}
