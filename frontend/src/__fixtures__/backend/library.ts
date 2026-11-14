// Recorded verbatim from the backend on 2026-11-14 (see index.ts). Do not edit by hand.
const data: unknown = [
 {
  "id": "haouz-flood-2026-10-10",
  "kind": "flood",
  "date": "2026-10-10",
  "location": {
   "lat": 31.25,
   "lon": -7.983,
   "name": "Crue éclair d'Al Haouz, 10 octobre 2026 (Asni)",
   "name_i18n": {
    "fr": "Crue éclair d'Al Haouz, 10 octobre 2026 (Asni)",
    "en": "Al Haouz flash flood, 10 October 2026 (Asni)",
    "ar": "سيول الحوز، 10 أكتوبر 2026 (أسني)"
   },
   "bbox": null
  },
  "magnitude": null,
  "answer_id": "event-haouz-flood-2026-10-10",
  "reference": {
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
   "comparison": null
  }
 },
 {
  "id": "panama-2026",
  "kind": "earthquake",
  "date": "2026-10-09",
  "location": {
   "lat": 7.59,
   "lon": -80.77,
   "name": "Validation (hors Maroc) : séisme M7.7 du Panama, 9 octobre 2026",
   "name_i18n": {
    "fr": "Validation (hors Maroc) : séisme M7.7 du Panama, 9 octobre 2026",
    "en": "Validation (outside Morocco): Panama M7.7 earthquake, 9 October 2026",
    "ar": "تحقق (خارج المغرب): زلزال بنما بقوة 7.7، 9 أكتوبر 2026"
   },
   "bbox": null
  },
  "magnitude": {
   "value": 7.7,
   "type": "Mww"
  },
  "answer_id": "event-panama-2026",
  "reference": {
   "source": "usgs",
   "agreement": "inconclusive",
   "summary": {
    "template": "library.usgs",
    "params": {
     "mag": 7.7,
     "date": {
      "date": "2026-10-09"
     }
    }
   },
   "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us6000u18k",
   "comparison": null
  }
 }
];
export default data;
