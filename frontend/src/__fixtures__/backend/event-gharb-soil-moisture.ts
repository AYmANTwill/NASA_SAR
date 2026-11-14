// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = {
 "id": "event-gharb-soil-moisture",
 "created_at": "2026-11-14T13:21:45+00:00",
 "question": "Quelle est l'humidité du sol dans le Gharb ?",
 "lang": "fr",
 "location": {
  "lat": 34.5,
  "lon": -6,
  "name": null,
  "name_i18n": {
   "fr": "Humidité du sol, plaine du Gharb",
   "en": "Soil moisture, Gharb plain",
   "ar": "رطوبة التربة في سهل الغرب"
  },
  "bbox": null
 },
 "recipe": "soil_moisture",
 "product": "SME2",
 "product_status": "provisional",
 "period": {
  "start": "2026-11-14",
  "end": "2026-11-14"
 },
 "acquisitions": [],
 "tracks": [],
 "verdict": {
  "template": "backend.verdict.soil_moisture",
  "params": {},
  "text": {
   "fr": "Humidité du sol le 20/10/2026 : 0.219 m³/m³ (+0.025 par rapport à la moyenne de 6 passages). Cet écart est dans l'incertitude du produit (0.028) : il ne montre pas de changement réel.",
   "en": "Soil moisture on 2026-10-20: 0.219 m³/m³ (+0.025 vs the mean of 6 passes). This change is within the product's uncertainty (0.028): it does not show a real change.",
   "ar": "رطوبة التربة في 20/10/2026: 0.219 م³/م³ (+0.025 مقارنة بمتوسط 6 عمليات مرور). هذا التغيّر ضمن عدم اليقين في المنتج (0.028)، ولا يدل على تغيّر حقيقي."
  }
 },
 "confidence": "low",
 "stable_in_noise": true,
 "metrics": [
  {
   "id": "soil_moisture",
   "measurement": {
    "value": 0.219,
    "uncertainty": 0.028,
    "unit": "m3/m3",
    "sigma": 1
   }
  },
  {
   "id": "soil_moisture_anomaly",
   "measurement": {
    "value": 0.025,
    "uncertainty": 0.028,
    "unit": "m3/m3",
    "sigma": 1
   }
  }
 ],
 "series": [
  {
   "id": "soil_moisture",
   "unit": "m3/m3",
   "points": [
    {
     "date": "2026-09-24",
     "value": 0.169,
     "lo": 0.14100000000000001,
     "hi": 0.197
    },
    {
     "date": "2026-09-26",
     "value": 0.182,
     "lo": 0.154,
     "hi": 0.21
    },
    {
     "date": "2026-10-06",
     "value": 0.196,
     "lo": 0.168,
     "hi": 0.224
    },
    {
     "date": "2026-10-08",
     "value": 0.214,
     "lo": 0.186,
     "hi": 0.242
    },
    {
     "date": "2026-10-18",
     "value": 0.183,
     "lo": 0.155,
     "hi": 0.211
    },
    {
     "date": "2026-10-20",
     "value": 0.219,
     "lo": 0.191,
     "hi": 0.247
    }
   ],
   "sigma": 1,
   "noise_floor": 0.028
  }
 ],
 "checks": [
  {
   "id": "noise_floor",
   "status": "warn",
   "measurement": {
    "value": 0.028,
    "uncertainty": 0,
    "unit": "m3/m3",
    "sigma": 1
   },
   "detail": {
    "template": "check.noise_floor",
    "params": {
     "noise": {
      "value": 0.028,
      "uncertainty": 0,
      "unit": "m3/m3",
      "sigma": 1
     }
    }
   }
  },
  {
   "id": "coherence_mask",
   "status": "not_applicable",
   "measurement": null,
   "detail": null
  },
  {
   "id": "ionosphere",
   "status": "not_applicable",
   "measurement": null,
   "detail": null
  },
  {
   "id": "unwrapping",
   "status": "not_applicable",
   "measurement": null,
   "detail": null
  }
 ],
 "evidence": [
  {
   "source": "open_meteo",
   "agreement": "inconclusive",
   "summary": {
    "template": "evidence.open_meteo.rain",
    "params": {
     "rain": {
      "value": 34.6,
      "uncertainty": 0,
      "unit": "mm",
      "sigma": 1
     },
     "days": 31
    }
   },
   "url": null,
   "retrieved_at": "2026-11-14T13:21:45+00:00"
  },
  {
   "source": "osm",
   "agreement": "unavailable",
   "summary": {
    "template": "backend.evidence.unavailable",
    "params": {},
    "text": {
     "fr": "Source indisponible : OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.de/api/interpreter)",
     "en": "Source unavailable: OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.de/api/interpreter)",
     "ar": "المصدر غير متاح: OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.de/api/interpreter)"
    }
   },
   "url": null,
   "retrieved_at": "2026-11-14T13:21:45+00:00"
  }
 ],
 "layers": [
  {
   "id": "sm_SME2_T116_F019_20261020_20261020",
   "kind": "soil_moisture",
   "url": "/api/layers/sm_SME2_T116_F019_20261020_20261020.png",
   "bounds": [
    -8.589211962655387,
    32.95824252218211,
    -4.480809006182882,
    36.28861666877263
   ],
   "unit": "m3/m3",
   "min": 0,
   "max": 0.5,
   "palette": "sequential_moisture",
   "sign_convention": null,
   "period": {
    "start": "2026-11-14",
    "end": "2026-11-14"
   },
   "source": "Soil moisture (m³/m³), 20261020"
  }
 ],
 "earthquakes": [],
 "limits": [
  {
   "template": "backend.limit.soil_moisture",
   "params": {},
   "text": {
    "fr": "Valeur moyenne des premiers centimètres du sol sur une maille de plusieurs centaines de mètres.",
    "en": "Average of the top few centimetres of soil over a cell of several hundred metres.",
    "ar": "قيمة متوسطة لبضعة سنتيمترات علوية من التربة على خلية بمئات الأمتار."
   }
  },
  {
   "template": "limit.soil_depth",
   "params": {}
  }
 ],
 "indication": null,
 "classifier": null,
 "next_pass": null,
 "cached": true,
 "steps": [
  {
   "id": "s1",
   "kind": "classify",
   "tool": "agent.classify",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "step.classify",
    "params": {
     "recipe": {
      "term": "recipe.soil_moisture"
     }
    }
   },
   "error": null
  },
  {
   "id": "s2",
   "kind": "compute",
   "tool": "recipe.soil_moisture",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 2210,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "NISAR soil moisture (SME2)",
     "en": "NISAR soil moisture (SME2)",
     "ar": "NISAR soil moisture (SME2)"
    }
   },
   "error": null
  },
  {
   "id": "s3",
   "kind": "cross_evidence",
   "tool": "evidence",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 761,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "rain in the 30 days before",
     "en": "rain in the 30 days before",
     "ar": "rain in the 30 days before"
    }
   },
   "error": null
  },
  {
   "id": "s4",
   "kind": "cross_evidence",
   "tool": "evidence",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 290,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "what is exposed (OpenStreetMap)",
     "en": "what is exposed (OpenStreetMap)",
     "ar": "what is exposed (OpenStreetMap)"
    }
   },
   "error": null
  },
  {
   "id": "s5",
   "kind": "verdict",
   "tool": "agent.template",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "step.verdict",
    "params": {}
   },
   "error": null
  }
 ],
 "x_alert_level": null
};
export default data;
