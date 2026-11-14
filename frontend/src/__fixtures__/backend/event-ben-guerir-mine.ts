// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = {
 "id": "event-ben-guerir-mine",
 "created_at": "2026-11-14T13:21:45+00:00",
 "question": "Où la surface de la mine de Ben Guerir a-t-elle changé ?",
 "lang": "fr",
 "location": {
  "lat": 32.25825,
  "lon": -7.82355,
  "name": null,
  "name_i18n": {
   "fr": "Mine de phosphate de Ben Guerir (non validé : pas de polygone)",
   "en": "Ben Guerir phosphate mine (not validated: no polygon)",
   "ar": "منجم الفوسفاط بابن جرير (غير مؤكد: دون مضلع)"
  },
  "bbox": null
 },
 "recipe": "damage",
 "product": "GUNW",
 "product_status": "provisional",
 "period": {
  "start": "2026-11-14",
  "end": "2026-11-14"
 },
 "acquisitions": [],
 "tracks": [],
 "verdict": {
  "template": "backend.verdict.surface_change",
  "params": {},
  "text": {
   "fr": "Sans date d'événement, comparaison du dernier passage (03/10/2026 → 15/10/2026, 12 jours) (produit NISAR provisoire) au précédent : la perte de cohérence radar moyenne dans un rayon de 5 km est de 0.03, contre 0.04 pour toute la scène : un excès de -0.01, sous le niveau 0.11 que 1 % des cercles sans événement dépassent ; 0.19 km² ont perdu plus de 0.3 (0.26 km² dans la paire précédente). Pas de changement local net. La référence « sans événement » vient d'une seule géométrie de visée, d'une seule saison et de cercles placés au hasard dans la scène.",
   "en": "With no event date, the latest pass (2026-10-03 → 2026-10-15, 12 days) (provisional NISAR product) is compared with the one before: the mean radar coherence loss within 5 km is 0.03, against 0.04 for the whole frame: an excess of -0.01, below the 0.11 level that 1 % of no-event circles exceed; 0.19 km² lost more than 0.3 (0.26 km² in the previous pair). No clear local change. The no-event reference comes from one viewing geometry, one season and circles placed at random in the frame.",
   "ar": "دون تاريخ حدث، مقارنة آخر مرور (03/10/2026 ← 15/10/2026، 12 يومًا) (منتج NISAR مؤقت) بالمرور الذي سبقه: متوسط فقدان التماسك الراداري ضمن 5 كم هو 0.03، مقابل 0.04 للمشهد كله: فائض قدره -0.01، دون المستوى 0.11 الذي تتجاوزه 1% من الدوائر بلا حدث؛ و0.19 كم² فقدت أكثر من 0.3 (0.26 كم² في الزوج السابق). لا تغيّر محلي واضح. المرجع «بلا حدث» مأخوذ من هندسة رؤية واحدة وفصل واحد ودوائر موزعة عشوائيًا في المشهد."
  }
 },
 "confidence": "low",
 "stable_in_noise": true,
 "metrics": [
  {
   "id": "coherence_loss_area",
   "measurement": {
    "value": 0.19,
    "uncertainty": 0,
    "unit": "km2",
    "sigma": 1
   }
  }
 ],
 "series": [],
 "checks": [
  {
   "id": "noise_floor",
   "status": "not_applicable",
   "measurement": null,
   "detail": null
  },
  {
   "id": "coherence_mask",
   "status": "pass",
   "measurement": {
    "value": 0,
    "uncertainty": 0,
    "unit": "percent",
    "sigma": 1
   },
   "detail": {
    "template": "check.coherence_mask",
    "params": {
     "fraction": {
      "value": 0,
      "uncertainty": 0,
      "unit": "percent",
      "sigma": 1
     },
     "threshold": 0.3
    }
   }
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
      "value": 38.4,
      "uncertainty": 0,
      "unit": "mm",
      "sigma": 1
     },
     "days": 13
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
   "id": "sc_GUNW_T044_F018_20261003_20261015",
   "kind": "coherence_loss",
   "url": "/api/layers/sc_GUNW_T044_F018_20261003_20261015.png",
   "bounds": [
    -9.839956753822209,
    31.08355565988639,
    -6.034756030124037,
    34.23235925874663
   ],
   "unit": "coherence",
   "min": 0.1,
   "max": 0.8,
   "palette": "sequential_coherence_loss",
   "sign_convention": null,
   "period": {
    "start": "2026-11-14",
    "end": "2026-11-14"
   },
   "source": "Surface change (coherence loss), 20261003→20261015"
  }
 ],
 "earthquakes": [],
 "limits": [
  {
   "template": "backend.limit.surface_change",
   "params": {},
   "text": {
    "fr": "Une perte de cohérence montre que la surface a changé, pas pourquoi : eau, boue, éboulement, travaux ou végétation. Ce n'est ni une mesure de dégâts, ni de hauteur ou de durée d'inondation ; la fenêtre dure plusieurs jours.",
    "en": "Coherence loss shows that the surface changed, not why: water, mud, rock fall, earthworks or vegetation. It is not a measure of damage, flood depth or flood duration, and the window lasts several days.",
    "ar": "يدل فقدان التماسك على أن السطح تغيّر، لا على السبب: ماء أو وحل أو انهيار أو أشغال أو نباتات. وهو ليس قياسًا للأضرار ولا لعمق الفيضان أو مدته، والنافذة تمتد عدة أيام."
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
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "step.classify",
    "params": {
     "recipe": {
      "term": "recipe.damage"
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
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "found 26 interferograms covering the point",
     "en": "found 26 interferograms covering the point",
     "ar": "found 26 interferograms covering the point"
    }
   },
   "error": null
  },
  {
   "id": "s3",
   "kind": "compute",
   "tool": "recipe.damage",
   "status": "done",
   "params": {},
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 3077,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "surface change (coherence loss)",
     "en": "surface change (coherence loss)",
     "ar": "surface change (coherence loss)"
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
   "duration_ms": 950,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "rain over the change window (context only)",
     "en": "rain over the change window (context only)",
     "ar": "rain over the change window (context only)"
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
   "started_at": "2026-11-14T13:21:45+00:00",
   "duration_ms": 21855,
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
   "id": "s6",
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
