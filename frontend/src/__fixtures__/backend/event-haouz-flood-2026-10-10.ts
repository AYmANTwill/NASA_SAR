// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = {
 "id": "event-haouz-flood-2026-10-10",
 "created_at": "2026-11-14T13:21:44+00:00",
 "question": "Le sol a-t-il changé à Asni lors de la crue éclair du 10 octobre 2026 ?",
 "lang": "fr",
 "location": {
  "lat": 31.25,
  "lon": -7.983,
  "name": null,
  "name_i18n": {
   "fr": "Crue éclair d'Al Haouz, 10 octobre 2026 (Asni)",
   "en": "Al Haouz flash flood, 10 October 2026 (Asni)",
   "ar": "سيول الحوز، 10 أكتوبر 2026 (أسني)"
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
   "fr": "Entre le 03/10/2026 et le 15/10/2026 (12 jours, fenêtre qui contient l'événement du 10/10/2026) (produit NISAR provisoire) : la cohérence radar dans un rayon de 5 km a baissé de 0.15 en moyenne, soit 0.12 de plus que la moyenne de toute la scène (0.03) : cas limite, cet excès est juste au-dessus du niveau 0.11 que 1 % des cercles sans événement dépassent, mais sous 0.15 ; 2.69 km² ont perdu plus de 0.3 (0.04 km² dans la paire précédente). Cela ne suffit pas pour dire que la surface a changé, et aucune cause ne peut être donnée. La référence « sans événement » vient d'une seule géométrie de visée, d'une seule saison et de cercles placés au hasard dans la scène.",
   "en": "Between 2026-10-03 and 2026-10-15 (12 days, a window that contains the event of 2026-10-10) (provisional NISAR product): radar coherence within 5 km fell by 0.15 on average, 0.12 more than the whole-frame average (0.03): borderline, this excess is just above the 0.11 level that 1 % of no-event circles exceed, but below 0.15; 2.69 km² lost more than 0.3 (0.04 km² in the previous pair). This is not enough to say the surface changed, and no cause can be given. The no-event reference comes from one viewing geometry, one season and circles placed at random in the frame.",
   "ar": "بين 03/10/2026 و15/10/2026 (12 يومًا، نافذة تتضمن حدث 10/10/2026) (منتج NISAR مؤقت): انخفض التماسك الراداري ضمن 5 كم بمعدل 0.15 في المتوسط، أي 0.12 أكثر من متوسط المشهد كله (0.03): حالة حدّية، هذا الفائض فوق المستوى 0.11 الذي تتجاوزه 1% من الدوائر بلا حدث بقليل، لكنه دون 0.15؛ و2.69 كم² فقدت أكثر من 0.3 (0.04 كم² في الزوج السابق). لا يكفي ذلك للقول إن السطح تغيّر، ولا يمكن تحديد سبب. المرجع «بلا حدث» مأخوذ من هندسة رؤية واحدة وفصل واحد ودوائر موزعة عشوائيًا في المشهد."
  }
 },
 "confidence": "low",
 "stable_in_noise": false,
 "metrics": [
  {
   "id": "coherence_loss_area",
   "measurement": {
    "value": 2.69,
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
      "value": 37.9,
      "uncertainty": 0,
      "unit": "mm",
      "sigma": 1
     },
     "days": 13
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
   "id": "sc_GUNW_T044_F017_20261003_20261015",
   "kind": "coherence_loss",
   "url": "/api/layers/sc_GUNW_T044_F017_20261003_20261015.png",
   "bounds": [
    -9.102778422622585,
    29.1074574892324,
    -5.383079595514234,
    32.26455186874061
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
   "started_at": "2026-11-14T13:21:44+00:00",
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "backend.step",
    "params": {},
    "text": {
     "fr": "found 36 interferograms covering the point",
     "en": "found 36 interferograms covering the point",
     "ar": "found 36 interferograms covering the point"
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 3306,
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 411,
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 395,
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
   "started_at": "2026-11-14T13:21:44+00:00",
   "duration_ms": 0,
   "summary": {
    "template": "step.verdict",
    "params": {}
   },
   "error": null
  }
 ],
 "x_alert_level": "yellow"
};
export default data;
