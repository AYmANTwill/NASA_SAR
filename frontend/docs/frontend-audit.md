# Audit du frontend NISAR Pulse (Phase 0, aucune modification du code)

Date : 11 novembre 2026. Captures : `docs/screenshots/audit/` (desktop 1280 px et mobile 375 px, accueil et vue cas).

## 1. Constat principal : le code existant n'est pas le produit décrit dans le prompt

Le dépôt contient un **observatoire à globe de 8 cas de simulation**, pas l'« enquêteur radar » (Demander / Prouver / Surveiller).

| Prompt | Existant |
|---|---|
| FastAPI + agent LLM avec appels d'outils | **Aucun backend.** Seulement des fichiers statiques `public/data/*.json|png|geojson`. Aucun endpoint, aucun schéma Pydantic, aucun appel `/api/`. |
| Question libre FR/AR/EN | Aucune zone de saisie ni conversation. |
| Étapes de l'agent visibles | Absent. |
| Verdict, confiance Élevée/Moyenne/Faible, incertitude, « ce que le radar ne peut pas dire » | Absent. Il y a une « confiance du modèle » en % (classifieur simulé, 94 %) et aucune bande d'incertitude. |
| Accueil « Ce que NISAR a trouvé au Maroc » | Absent. L'accueil est un globe avec 8 cartes de cas (Venezuela, Souss-Massa, Bihar, Amazon, Mexico, mines…). |
| Veille (Jaune/Orange/Rouge, FR+AR) | Panneau d'alertes simulées (sévérité high/moderate, 28 alertes), pas de lieux suivis ni de prochain passage. |
| Bibliothèque mondiale (Panama M7.7 du 9 oct. 2026, etc.) | Absent. Pas de Panama. |
| Figure bande L contre bande C (Rif) | Partiel : un comparateur avant/après avec Sentinel-1 existe, hors Rif. |
| FR / AR (RTL) / EN | **EN + FR partiel** : dictionnaire clé = phrase anglaise (`src/lib/i18n.ts`), les textes scientifiques restent en anglais. **Pas d'arabe, pas de `dir`, pas de RTL.** `<html lang="en">` figé. |
| Mode hors ligne | Aucun service worker ni cache. Fonts Google, fond OpenFreeMap et GIBS exigent Internet. |
| Contrat API, TanStack Query | `fetch` brut dans `src/data/loader.ts`, `useState`/Zustand. Pas de TanStack Query. |

Les données sont **entièrement simulées** (README : « All observations… are simulated, including the Venezuela earthquake scenario »), ce qui contredit la règle « n'invente aucune donnée » si on les réutilise telles quelles dans les écrans finaux.

## 2. Ce qui existe et fonctionne

- Build, `tsc --noEmit` : OK. Aucune erreur console en navigation (accueil + cas, desktop et mobile).
- Carte MapLibre v5 + deck.gl `BitmapLayer`, curseur d'opacité, légende avec unité et plage, attribution OpenStreetMap/OpenFreeMap, série temporelle (Recharts), raccourcis clavier, dialogues Radix, reduced-motion.
- Chargement paresseux et découpage en chunks (maplibre, deck, charts).
- Rasters PNG + sidecar JSON (bounds, colormap, unit, min, max) : un bon format de base pour les couches déplacement/cohérence. `docs/DATA_CONTRACT.md` le documente.

## 3. Ce qui manque par rapport à la section 1

1. Backend/agent et tout son contrat (voir §5).
2. Écrans : Accueil Maroc, Enquête (conversation), Réponse, Veille, Bibliothèque, Preuve L/C Rif. Aucun n'existe sous la forme demandée.
3. i18n complète FR/AR/EN, RTL et propriétés CSS logiques.
4. Mode démo hors ligne (réponses Panama et Al Wahda précalculées).
5. Couches USGS (épicentre/répliques) : `events.geojson` existe mais simulé, sans Panama.
6. Vocabulaire « indication » (Fukuzono) : non traité.

## 4. Dette technique

- **Lint en échec** : `no-irregular-whitespace` dans `src/features/dashboard/Dashboard.tsx` (1 erreur).
- **Code minifié à la main** : `src/lib/i18n.ts`, `loader.ts`, `types.ts`, `vite.config.ts` en lignes très longues ; un seul fichier CSS de **2 491 lignes** (`src/styles/index.css`), `App.tsx` (424 lignes) et `MapScene.tsx` (577) monolithiques. `npm run format` n'est visiblement pas appliqué.
- **Non conforme à la section 2** : Tailwind **v3** (prompt : v4 + shadcn), pas de shadcn, pas de TanStack Query, composants maison. Aucun `.mcp.json`, aucun `.claude/`.
- **Pas un dépôt git** : impossible de créer la branche `feat/frontend-impeccable` sans `git init`.
- Chaînes de traduction indexées par la phrase anglaise : fragile, pas extensible à l'arabe (pluriels, RTL).
- Dépendance MapLibre 5.x avec advisory critique (README), à reporter dans le rapport final.
- Fonts via Google Fonts : cassent le hors ligne et ne couvrent pas l'arabe (Inter n'a pas de glyphes arabes).
- Port 5173 déjà occupé sur la machine au moment de l'audit (autre processus) ; j'ai utilisé 5174 et l'ai arrêté.

## 5. Écarts UI / API et chiffres codés en dur

Il n'y a pas d'API. Le « contrat » est `docs/DATA_CONTRACT.md` (fichiers). Pour l'UI cible il manque, **à proposer au backend, sans que je le modifie** :

- `POST /ask` (question, langue, lieu) → flux d'événements d'étapes `{tool, status, params, duration_ms}` puis réponse.
- Schéma de réponse : `verdict`, `confidence: high|medium|low`, `series[{date, value, lo, hi}]`, `components{vertical, east_west}`, `limits[]` (« ce que le radar ne peut pas dire »), `evidence[]`, `rasters[{url, unit, min, max, bounds}]`, `kind: indication` pour Fukuzono.
- `GET /discoveries?region=MA` (zones classées par vitesse et exposition), `GET /watches`, `POST /watch`, `GET /library`.

Chiffres/valeurs codés en dur trouvés dans `src` :
- `Intro.tsx` : « L-band », « 12 days », « 8 signals », « 8 phenomena » (aussi dans `i18n.ts`).
- `layers.ts`, `Compare.tsx`, `i18n.ts` : « C 5.6 cm », « L 24 cm ».
- `i18n.ts` : « ±3 dB », « >1 m », « ≥0.15 », seuils d'alerte, « 75 secondes » (visite guidée), seuils « Mock dam threshold ».
- Les KPI (`displacement_mm`, `affected_population`, etc.) viennent de `cases.json`, donc de la simulation.

## 6. Accessibilité (constats rapides, pas d'axe-core encore)

- 8 boutons sans libellé accessible en tête de page (nom vide) : rail d'icônes des cas.
- Aucun `dir`, `lang` fixe sur `en`.
- Palette arc-en-ciel cyclique pour le déplacement (colormap GUNW) : à remplacer par une palette divergente centrée sur zéro, comme demandé.
- Texte tout petit en majuscules espacées (mono) à faible contraste sur fond sombre : à mesurer en WCAG AA.

## 7. Décisions dont j'ai besoin avant la Phase 1

1. **Backend** : il n'y a pas de FastAPI dans ce dossier. Où est-il (autre dépôt, autre dossier) ? Sinon je construis le frontend contre un contrat typé + un mock servi par des fixtures `__fixtures__/` clairement nommées (Panama, Al Wahda, Gharb SME2), à remplacer par l'API réelle.
2. **Réécriture** : je recommande de **garder** la base MapLibre/deck.gl/rasters/légende et de **réécrire** la coquille (App, i18n, CSS monolithique, écrans), en migrant vers Tailwind v4 + shadcn. Cela implique de remplacer du code existant (3 écrans) : j'ai besoin de votre accord explicite.
3. **Git** : j'exécute `git init`, un commit de l'état actuel, puis la branche `feat/frontend-impeccable` ?
4. **Données simulées** : les 8 cas simulés sont à retirer du parcours final (ou à garder dans une vue « démo simulée » clairement étiquetée) ?
5. **Outils** : OK pour installer les 8 skills (je lirai chaque `SKILL.md` avant) et écrire `.mcp.json` (shadcn, playwright, context7) ?

## 8. Alignement avec le document « NISAR Pulse v2 — L'enquêteur radar »

Le prompt et le plan v2 sont cohérents sur l'essentiel : les 3 verbes, les 6 écrans, la confiance par règles, la veille J/O/R, Fukuzono affiché comme « indication », le hors ligne et la démo en 6 temps. Le plan v2 ajoute ou précise des points que le prompt ne couvre pas :

| Point du plan v2 | Conséquence pour le frontend |
|---|---|
| 4 contrôles d'incertitude (plancher de bruit, pixels masqués sous la cohérence, ionosphère, déroulement) | La réponse affiche un bloc « Contrôles » avec le résultat de chaque contrôle, fourni par l'API. |
| 7 types de question, chacun avec sa recette (dont inondation, déforestation, GOFF en mètres) | La réponse n'est pas propre au déplacement : un rendu par type (carte en cm, vitesse mm/an, surface inondée, hectares, vecteurs, humidité). |
| Classifieur de changement en bêta, avec précision et rappel mesurés | Badge « bêta » et scores affichés quand l'API les fournit. |
| Venezuela comme plan B du Panama | Le parcours de démo doit pouvoir basculer sur Venezuela sans changer de code. |
| Mines de Ben Guerir et Khouribga (si couvertes) | L'accueil découverte met en avant une zone si l'API la signale, sans rien coder en dur. |
| « Le verdict suit un gabarit » et « les chiffres viennent du code » | L'API renvoie `verdict = {template_id, params}` : le frontend traduit le gabarit en FR/AR/EN et y insère les chiffres. La notification arabe ne dépend donc pas du LLM. |
| Les produits ne sont calibrés que depuis le 17 juin 2026 (PROVISIONAL) | La réponse affiche la période couverte et le statut du produit. |
| Le v1 (17 zones, 12 modèles, données simulées) est abandonné | Les 8 cas simulés, les générateurs de données et le classifieur « 94 % » ne font plus partie du produit. |

## 9. Principe d'architecture : un frontend prêt à brancher

- `src/api/contract.ts` est la **source de vérité** : des schémas zod d'où dérivent les types TS. `docs/API_CONTRACT.md` les documente pour l'équipe FastAPI, qui écrira des modèles Pydantic équivalents. Une fois le backend en place, on régénère les types depuis son OpenAPI (`openapi-typescript`) et on compare.
- Un adaptateur choisi par `VITE_API_MODE` : `http` (FastAPI réel) ou `fixtures` (`src/__fixtures__/`). Les composants ne savent pas lequel est actif.
- Étapes de l'agent diffusées en **SSE** (`POST /api/ask` → `text/event-stream` : `step`, puis `answer`), ce que FastAPI fait nativement.
- En mode fixtures, un **bandeau permanent « Données de test, pas une mesure NISAR »** s'affiche. Les fixtures ne contiennent que des valeurs manifestement synthétiques et ne servent qu'à exercer l'UI. Les chiffres du jury viendront uniquement du backend.
- Le hors ligne réel (réponses Panama et Al Wahda en cache) passe par un service worker et la persistance de TanStack Query, alimentés par les réponses de l'API réelle.

## 10. Plan de travail proposé

1. Git init + branche ; correction du lint (1 erreur). 
2. Phase 1 : skills et MCP, PRODUCT.md, tokens (AA vérifié), Tailwind v4 + shadcn, polices avec arabe auto-hébergées, i18n FR/AR/EN avec RTL, couche TanStack Query + cache hors ligne (service worker), contrat typé et fixtures.
3. Phase 2 dans l'ordre de la démo : Enquête (Panama) → Accueil Maroc → Réponse (Al Wahda) → Veille → Preuve L/C → SME2 → Bibliothèque.
4. Phase 3 : captures 3 langues × 4 largeurs, axe-core, clavier, hors ligne, chasse aux chiffres codés.
5. Phase 4 : `e2e/demo.spec.ts` chronométré, `docs/frontend-report.md`.
