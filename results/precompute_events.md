### haouz-flood-2026-10-10
- type: surface_change | status: ready | confidence: **low** | alert: **yellow**
- verdict (fr): Entre le 03/10/2026 et le 15/10/2026 (12 jours, fenêtre qui contient l'événement du 10/10/2026) (produit NISAR provisoire) : la cohérence radar dans un rayon de 5 km a baissé de 0.15 en moyenne, soit 0.12 de plus que la moyenne de toute la scène (0.03) : cas limite, cet excès est juste au-dessus du niveau 0.11 que 1 % des cercles sans événement dépassent, mais sous 0.15 ; 2.69 km² ont perdu plus de 0.3 (0.04 km² dans la paire précédente). Cela ne suffit pas pour dire que la surface a changé, et aucune cause ne peut être donnée. La référence « sans événement » vient d'une seule géométrie de visée, d'une seule saison et de cercles placés au hasard dans la scène.
- confidence reasons: mean coherence loss within 5 km 0.147 against 0.028 for the whole frame (excess 0.119; borderline from 0.11, local excess from 0.15) | 100% of the 5 km circle holds valid data, 99% of it was coherent before the event | 2.69 km² above the 0.3 loss, 0.04 km² in the previous pair | just above the level that 1% of no-event circles exceed: not a detection | the no-event reference is one viewing geometry (044/17), one season (June to September 2026), circles placed at random anywhere in the frame: its level is approximate | coherence loss says the surface changed, not why; no independent source tests it
- failed steps: none
- evidence: Open-Meteo=none (37.9 mm of rain between 2026-10-03 and 2026-10-15 (max 13.4 mm on 2026-10-09)); OpenStreetMap=unavailable (OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.)
- data_used: 30 products; steps: 5

### haouz-soil-moisture
- type: soil_moisture | status: ready | confidence: **low** | alert: **none**
- verdict (fr): Humidité du sol le 18/10/2026 : 0.174 m³/m³ (-0.027 par rapport à la moyenne de 7 passages). Cet écart est dans l'incertitude du produit (0.028) : il ne montre pas de changement réel.
- confidence reasons: the change from the mean of the passes (-0.027 m³/m³) is within the product's uncertainty (0.028) | NISAR Level-3 product, provisional calibration: never above medium | the baseline is the mean of passes from several tracks and dates, not one geometry | the retrieval quality flag is not used
- failed steps: none
- evidence: Open-Meteo=agrees (59.7 mm of rain between 2026-09-18 and 2026-10-18 (max 13.4 mm on 2026-10-09)); OpenStreetMap=unavailable (OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.)
- data_used: 15 products; steps: 4

### gharb-soil-moisture
- type: soil_moisture | status: ready | confidence: **low** | alert: **none**
- verdict (fr): Humidité du sol le 20/10/2026 : 0.219 m³/m³ (+0.025 par rapport à la moyenne de 6 passages). Cet écart est dans l'incertitude du produit (0.028) : il ne montre pas de changement réel.
- confidence reasons: the change from the mean of the passes (0.025 m³/m³) is within the product's uncertainty (0.028) | NISAR Level-3 product, provisional calibration: never above medium | the baseline is the mean of passes from several tracks and dates, not one geometry | the retrieval quality flag is not used
- failed steps: none
- evidence: Open-Meteo=none (34.6 mm of rain between 2026-09-20 and 2026-10-20 (max 11.4 mm on 2026-10-19)); OpenStreetMap=unavailable (OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.)
- data_used: 10 products; steps: 4

### ben-guerir-mine
- type: surface_change | status: not validated | confidence: **low** | alert: **none**
- verdict (fr): Sans date d'événement, comparaison du dernier passage (03/10/2026 → 15/10/2026, 12 jours) (produit NISAR provisoire) au précédent : la perte de cohérence radar moyenne dans un rayon de 5 km est de 0.03, contre 0.04 pour toute la scène : un excès de -0.01, sous le niveau 0.11 que 1 % des cercles sans événement dépassent ; 0.19 km² ont perdu plus de 0.3 (0.26 km² dans la paire précédente). Pas de changement local net. La référence « sans événement » vient d'une seule géométrie de visée, d'une seule saison et de cercles placés au hasard dans la scène.
- confidence reasons: mean coherence loss within 5 km 0.03 against 0.042 for the whole frame (excess -0.012; borderline from 0.11, local excess from 0.15) | 100% of the 5 km circle holds valid data, 99% of it was coherent before the event | 0.19 km² above the 0.3 loss, 0.26 km² in the previous pair | no event date: the two latest passes are compared | the no-event reference is one viewing geometry (044/17), one season (June to September 2026), circles placed at random anywhere in the frame: its level is approximate | coherence loss says the surface changed, not why; no independent source tests it
- failed steps: none
- evidence: Open-Meteo=none (38.4 mm of rain between 2026-10-03 and 2026-10-15 (max 19.0 mm on 2026-10-10)); OpenStreetMap=unavailable (OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.)
- data_used: 26 products; steps: 5

### al-wahda-surroundings
- type: slow_motion | status: ready | confidence: **low** | alert: **none**
- verdict (fr): Variation de ligne de visée non corrigée, signe non vérifié : du 20/06/2026 au 18/10/2026 (9 paires, 120 jours) (produit NISAR provisoire), 43.4 mm cumulés au point (bruit par paire ± 29.8 mm). Série trop courte pour donner une vitesse en mm/an : il faut au moins 365 jours. Ionosphère : écran du produit soustrait (non validé) ; troposphère : non corrigée. La série traverse la lacune de données du 27/07/2026 au 10/08/2026 (1 paire l'enjambe). La zone de référence est dans la même composante connexe que le point.
- confidence reasons: signal = 0.5× the noise floor | record of 120 days, shorter than 365: no rate, confidence capped at medium | ionosphere: the product's phase screen is subtracted, not validated; troposphere: not corrected | the reference area shares the point's connected component | the chain crosses the data gap 20260727 to 20260810: 1 pair(s) bridge it | LOS sign unverified (STATUS H4): the direction of the motion is not established; shown as an uncorrected line-of-sight change
- failed steps: none
- evidence: Open-Meteo=agrees (57.5 mm of rain between 2026-06-20 and 2026-10-18 (max 17.8 mm on 2026-09-28)); OpenStreetMap=unavailable (OpenStreetMap unreachable (406 Client Error: Not Acceptable for url: https://overpass-api.)
- data_used: 17 products; steps: 6
