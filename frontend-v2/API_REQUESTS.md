# Requests to the backend (for Ayman)

From the v2 interface (Adam). Nothing here blocks v2: each item says what the interface does until then.

## 1. Mark placeholder values explicitly in draft cases

Draft cases send their placeholder NISAR values as `{value: 0, uncertainty: 0}`. Panama's placeholder moment
magnitude then gets `agreement: "disagree"` against USGS Mww 7.7 ± 0.1, which reads as "NISAR disagrees with USGS".

- **Ask:** a public marker for a placeholder, for example `nisar: null` in a draft finding (and `agreement:
  "no_reference"` or a new `"not_measured"`), or a `placeholder: true` flag on the measurement.
- **Until then:** in a `draft` case, a NISAR value with `uncertainty: 0` is shown as "not measured yet" and its
  agreement badge is hidden. Nothing is computed; the value is withheld.

## 2. Map extent in the case list

**Delivered in main, 15 Nov:** optional `bbox` and `place` in `CaseSummary`. The list draws its locator from the
summary and only fetches details when either field is missing. Older responses remain supported.

## 3. A type for each timeline item

**Delivered in main, 15 Nov:** optional `kind: "event" | "acquisition" | "publication"`. The timeline draws separate
tracks, sharing the same time axis. Dates without a kind stay on an "Other dates" track; no kind is inferred.

## 4. English inside French and Arabic texts (answers)

Seen on live `/api/ask` and `/api/answers/*` (backend with no NISAR data on this machine):

- `verdict.text.fr` / `.ar` end with an English sentence from the agent, for example
  "… ne permet encore de répondre ici. needs an earlier pair and a pair of the same length on the same track …".
- Step summaries sent as `backend.step` carry the same English text in all three languages
  ("found 0 interferograms covering the point"), and the failed step's `error` is "failed" in all three.

- **Delivered in main, 15 Nov:** `backend.verdict.no_data`, `reason.*`, `backend.step.*`, `backend.limit.no_sigma`
  and `backend.limit.no_catalog` provide language-specific text fallbacks. The interface already reads these.
- **Existing caches:** JSON answers generated before this update keep their old text until they are regenerated
  by the backend adapter. Restarting the API alone does not migrate `backend/cache/answers_v2/`.

## 5. Answer period when no data was used

An answer with no NISAR product (`acquisitions: []`, `tracks: []`) has `period: {start: <today>, end: <today>}`.
Shown as is, it reads as "measured today".

- **Ask:** `period: null` when nothing was measured (the contract would need `period` nullable), or the period
  actually searched.
- **Until then:** the period is shown as sent, next to "Acquisitions: none".

## 6. Alert level is not in the contract

The answers carry `x_alert_level`, which the contract's `Answer` does not have (zod drops unknown keys), so the
interface cannot show it. Watches have `level`, answers do not.

- **Ask (contract change, Ayman + Houssam):** add `alert_level: "yellow" | "orange" | "red" | null` to `Answer`.
- **Until then:** no alert level is shown on an answer; the interface never derives one.

## 7. Schemas for the watch actions

`POST /api/watches/check` (`{changed: [...]}`) and `POST /api/watches/{id}/simulate` (`{simulated, watch_id, level}`)
have no schema in the contract.

- **Ask:** add their response shapes to `contract.ts` (or answer 204), so they can be validated like the rest.
- **Until then:** the interface never reads these bodies. After either action it re-reads `GET /api/watches` and
  `GET /api/notifications`, which are validated.

## 8. Backend features that /api does not expose

The legacy routes (`backend/api.py`) offer features that have no `/api` route and no schema in the contract, so
no interface may use them (every response must be validated):

| legacy route / field | what it gives | why an interface wants it |
|---|---|---|
| `GET /places` | the named places the agent understands, with FR/EN/AR aliases | suggest place names in the question box |
| `GET /next-pass?lat=&lon=` | next NISAR passes over any point | "next pass" before a question is asked |
| `GET /catalog?level=GUNW` | the products on the server | "what data does this server have" on the status page |
| `GET /events?include_validation=true` | all events, the Morocco ones included | the four Moroccan sites stay out of `/api/library` (team decision, 14 Nov) |
| `POST /ask` field `date` | the event date of a question | ask about a dated event without writing the date in the question |
| answer fields `profile`, `facts`, `event_time`, `data_used` | west–east profile, every number behind the verdict, event instant, product ids | detail panels, provenance |

- **Ask:** decide which of these the demo needs; for each, an `/api` route or `Answer` field with its schema in
  `contract.ts` (Ayman + Houssam).

## 9. English questions without a known place type

`POST /api/ask` with `{"question": "Is the ground moving here?", "lang": "en", "location": {…}}` returns the error
`unclear_question`, while the French "Le terrain bouge-t-il ici ?" at the same point is understood (slow motion).

- **Ask:** the same question vocabulary in EN and AR as in FR (agent classifier).
- **Until then:** the interface shows the backend's "unclear question" text in the page language.
