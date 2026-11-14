// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = {
 "id": "event-al-wahda-surroundings",
 "created_at": "2026-11-14T13:21:44+00:00",
 "question": "Le terrain autour du barrage Al Wahda bouge-t-il ?",
 "lang": "fr",
 "location": {
  "lat": 34.598,
  "lon": -5.198,
  "name": null,
  "name_i18n": {
   "fr": "Alentours du barrage Al Wahda",
   "en": "Surroundings of the Al Wahda dam",
   "ar": "محيط سد الوحدة"
  },
  "bbox": null
 },
 "recipe": "slow_motion",
 "product": "GUNW",
 "product_status": "provisional",
 "period": {
  "start": "2026-11-14",
  "end": "2026-11-14"
 },
 "acquisitions": [],
 "tracks": [],
 "verdict": {
  "template": "backend.verdict.slow_motion",
  "params": {},
  "text": {
   "fr": "Variation de ligne de visée non corrigée, signe non vérifié : du 20/06/2026 au 18/10/2026 (9 paires, 120 jours) (produit NISAR provisoire), 43.4 mm cumulés au point (bruit par paire ± 29.8 mm). Série trop courte pour donner une vitesse en mm/an : il faut au moins 365 jours. Ionosphère : écran du produit soustrait (non validé) ; troposphère : non corrigée. La série traverse la lacune de données du 27/07/2026 au 10/08/2026 (1 paire l'enjambe). La zone de référence est dans la même composante connexe que le point.",
   "en": "Uncorrected line-of-sight change, sign unverified: from 2026-06-20 to 2026-10-18 (9 pairs, 120 days) (provisional NISAR product), 43.4 mm cumulative at the point (noise per pair ± 29.8 mm). The record is too short for a rate in mm/yr: at least 365 days are needed. Ionosphere: the product's screen is subtracted (not validated); troposphere: not corrected. The chain crosses the data gap of 2026-07-27 to 2026-08-10 (1 pair bridges it). The reference area is in the same connected component as the point.",
   "ar": "تغيّر غير مصحَّح على خط الرؤية، والإشارة غير متحقَّق منها: من 20/06/2026 إلى 18/10/2026 (9 أزواج، 120 يومًا) (منتج NISAR مؤقت)، 43.4 ملم تراكميًا عند النقطة (ضجيج كل زوج ± 29.8 ملم). السلسلة قصيرة جدًا لحساب سرعة بالملم/سنة؛ يلزم 365 يومًا على الأقل. الأيونوسفير: خُصمت شاشة المنتج (دون تحقق)؛ التروبوسفير: غير مصحَّح. تمتد السلسلة عبر فجوة البيانات من 27/07/2026 إلى 10/08/2026 (زوج واحد يعبرها). منطقة المرجع في المركّبة المتصلة نفسها للنقطة."
  }
 },
 "confidence": "low",
 "stable_in_noise": true,
 "metrics": [
  {
   "id": "los_displacement_max",
   "measurement": {
    "value": 43.4,
    "uncertainty": 29.8,
    "unit": "mm",
    "sigma": 1
   }
  },
  {
   "id": "noise_floor",
   "measurement": {
    "value": 29.8,
    "uncertainty": 0,
    "unit": "mm",
    "sigma": 1
   }
  }
 ],
 "series": [
  {
   "id": "los",
   "unit": "mm",
   "points": [
    {
     "date": "2026-06-20",
     "value": 0,
     "lo": -29.8,
     "hi": 29.8
    },
    {
     "date": "2026-07-02",
     "value": 30.9,
     "lo": 1.0999999999999979,
     "hi": 60.7
    },
    {
     "date": "2026-07-14",
     "value": 37.2,
     "lo": 7.400000000000002,
     "hi": 67
    },
    {
     "date": "2026-07-26",
     "value": 41,
     "lo": 11.2,
     "hi": 70.8
    },
    {
     "date": "2026-08-19",
     "value": 60.2,
     "lo": 30.400000000000002,
     "hi": 90
    },
    {
     "date": "2026-08-31",
     "value": 39.1,
     "lo": 9.3,
     "hi": 68.9
    },
    {
     "date": "2026-09-12",
     "value": 82.9,
     "lo": 53.10000000000001,
     "hi": 112.7
    },
    {
     "date": "2026-09-24",
     "value": 65.8,
     "lo": 36,
     "hi": 95.6
    },
    {
     "date": "2026-10-06",
     "value": 56.3,
     "lo": 26.499999999999996,
     "hi": 86.1
    },
    {
     "date": "2026-10-18",
     "value": 43.4,
     "lo": 13.599999999999998,
     "hi": 73.2
    }
   ],
   "sigma": 1,
   "noise_floor": 29.8
  }
 ],
 "checks": [
  {
   "id": "noise_floor",
   "status": "pass",
   "measurement": {
    "value": 29.8,
    "uncertainty": 0,
    "unit": "mm",
    "sigma": 1
   },
   "detail": {
    "template": "check.noise_floor",
    "params": {
     "noise": {
      "value": 29.8,
      "uncertainty": 0,
      "unit": "mm",
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
   "status": "pass",
   "measurement": null,
   "detail": {
    "template": "check.ionosphere.applied",
    "params": {}
   }
  },
  {
   "id": "unwrapping",
   "status": "pass",
   "measurement": null,
   "detail": {
    "template": "check.unwrapping.ok",
    "params": {}
   }
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
      "value": 57.5,
      "uncertainty": 0,
      "unit": "mm",
      "sigma": 1
     },
     "days": 121
    }
   },
   "url": null,
   "retrieved_at": "2026-11-14T13:21:44+00:00"
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
   "retrieved_at": "2026-11-14T13:21:44+00:00"
  }
 ],
 "layers": [
  {
   "id": "disp_GUNW_T095_F071_20261006_20261018",
   "kind": "displacement",
   "url": "/api/layers/disp_GUNW_T095_F071_20261006_20261018.png",
   "bounds": [
    -7.293371494310407,
    33.02338485888295,
    -3.3350541711330015,
    36.24446558061857
   ],
   "unit": "cm",
   "min": -5.761,
   "max": 5.761,
   "palette": "diverging_displacement",
   "sign_convention": "positive_toward_satellite",
   "period": {
    "start": "2026-11-14",
    "end": "2026-11-14"
   },
   "source": "Displacement (cm), descending, 20261006→20261018"
  }
 ],
 "earthquakes": [],
 "limits": [
  {
   "template": "backend.limit.slow_motion",
   "params": {},
   "text": {
    "fr": "Une tendance sur quelques mois ne permet pas de dater une rupture et n'est pas un verdict sur la sûreté d'un barrage ; une inspection sur place reste nécessaire.",
    "en": "A trend over a few months cannot date a failure and is not a dam-safety verdict; an on-site inspection is still needed.",
    "ar": "لا يكفي اتجاه بضعة أشهر لتحديد موعد انهيار؛ ولا يُعد حكمًا على سلامة سد؛ يبقى الفحص الميداني ضروريًا."
   }
  },
  {
   "template": "backend.limit.sign_unverified",
   "params": {},
   "text": {
    "fr": "Sens du mouvement non vérifié sur données réelles : le signe suit la convention documentée (ARIA-tools, MintPy), sans contrôle indépendant.",
    "en": "Direction of motion not yet verified on real data: the sign follows the documented convention (ARIA-tools, MintPy), without an independent check.",
    "ar": "اتجاه الحركة غير متحقَّق منه على بيانات حقيقية: الإشارة تتبع الاصطلاح الموثّق (ARIA-tools وMintPy) دون تحقق مستقل."
   }
  },
  {
   "template": "limit.los_only",
   "params": {}
  },
  {
   "template": "limit.no_prediction",
   "params": {}
  },
  {
   "template": "limit.short_history",
   "params": {
    "since": {
     "date": "2026-06-20"
    }
   }
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "step.classify",
    "params": {
     "recipe": {
      "term": "recipe.slow_motion"
     }
    }
   },
   "error": null
  },
  {
   "id": "s2",
   "kind": "search_scenes",
   "tool": "catalog.find",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "found 17 interferograms covering the point",
     "en": "found 17 interferograms covering the point",
     "ar": "found 17 interferograms covering the point"
    }
   },
   "error": null
  },
  {
   "id": "s3",
   "kind": "compute",
   "tool": "recipe.slow_motion",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 64289,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "time series (small-baseline inversion)",
     "en": "time series (small-baseline inversion)",
     "ar": "time series (small-baseline inversion)"
    }
   },
   "error": null
  },
  {
   "id": "s4",
   "kind": "compute",
   "tool": "recipe.slow_motion",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 3139,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "map of the latest pair",
     "en": "map of the latest pair",
     "ar": "map of the latest pair"
    }
   },
   "error": null
  },
  {
   "id": "s5",
   "kind": "cross_evidence",
   "tool": "evidence",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 374,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "rain over the period",
     "en": "rain over the period",
     "ar": "rain over the period"
    }
   },
   "error": null
  },
  {
   "id": "s6",
   "kind": "cross_evidence",
   "tool": "evidence",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 22516,
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
   "id": "s7",
   "kind": "verdict",
   "tool": "agent.template",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:44+00:00",
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
