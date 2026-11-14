// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = {
 "id": "event-haouz-soil-moisture",
 "created_at": "2026-11-14T13:22:25+00:00",
 "question": "Quelle est l'humidité du sol à Asni ?",
 "lang": "fr",
 "location": {
  "lat": 31.25,
  "lon": -7.983,
  "name": null,
  "name_i18n": {
   "fr": "Humidité du sol à Asni (Al Haouz)",
   "en": "Soil moisture at Asni (Al Haouz)",
   "ar": "رطوبة التربة في أسني (الحوز)"
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
   "fr": "Humidité du sol le 18/10/2026 : 0.174 m³/m³ (-0.027 par rapport à la moyenne de 7 passages). Cet écart est dans l'incertitude du produit (0.028) : il ne montre pas de changement réel.",
   "en": "Soil moisture on 2026-10-18: 0.174 m³/m³ (-0.027 vs the mean of 7 passes). This change is within the product's uncertainty (0.028): it does not show a real change.",
   "ar": "رطوبة التربة في 18/10/2026: 0.174 م³/م³ (-0.027 مقارنة بمتوسط 7 عمليات مرور). هذا التغيّر ضمن عدم اليقين في المنتج (0.028)، ولا يدل على تغيّر حقيقي."
  }
 },
 "confidence": "low",
 "stable_in_noise": true,
 "metrics": [
  {
   "id": "soil_moisture",
   "measurement": {
    "value": 0.174,
    "uncertainty": 0.028,
    "unit": "m3/m3",
    "sigma": 1
   }
  },
  {
   "id": "soil_moisture_anomaly",
   "measurement": {
    "value": -0.027,
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
     "date": "2026-09-21",
     "value": 0.184,
     "lo": 0.156,
     "hi": 0.212
    },
    {
     "date": "2026-10-01",
     "value": 0.228,
     "lo": 0.2,
     "hi": 0.256
    },
    {
     "date": "2026-10-01",
     "value": 0.227,
     "lo": 0.199,
     "hi": 0.255
    },
    {
     "date": "2026-10-03",
     "value": 0.187,
     "lo": 0.159,
     "hi": 0.215
    },
    {
     "date": "2026-10-13",
     "value": 0.205,
     "lo": 0.177,
     "hi": 0.23299999999999998
    },
    {
     "date": "2026-10-13",
     "value": 0.203,
     "lo": 0.17500000000000002,
     "hi": 0.231
    },
    {
     "date": "2026-10-15",
     "value": 0.174,
     "lo": 0.146,
     "hi": 0.20199999999999999
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
   "agreement": "agrees",
   "summary": {
    "template": "evidence.open_meteo.rain",
    "params": {
     "rain": {
      "value": 59.7,
      "uncertainty": 0,
      "unit": "mm",
      "sigma": 1
     },
     "days": 31
    }
   },
   "url": null,
   "retrieved_at": "2026-11-14T13:22:25+00:00"
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
   "retrieved_at": "2026-11-14T13:22:25+00:00"
  }
 ],
 "layers": [
  {
   "id": "sm_SME2_T095_F073_20261018_20261018",
   "kind": "soil_moisture",
   "url": "/api/layers/sm_SME2_T095_F073_20261018_20261018.png",
   "bounds": [
    -8.495850966804772,
    29.09761650599211,
    -4.761589159453161,
    32.288076437648144
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
   "source": "Soil moisture (m³/m³), 20261018"
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
   "started_at": "2026-11-14T13:22:25+00:00",
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
   "started_at": "2026-11-14T13:22:25+00:00",
   "duration_ms": 4444,
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
   "started_at": "2026-11-14T13:22:25+00:00",
   "duration_ms": 721,
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
   "started_at": "2026-11-14T13:22:25+00:00",
   "duration_ms": 293,
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
   "started_at": "2026-11-14T13:22:25+00:00",
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
