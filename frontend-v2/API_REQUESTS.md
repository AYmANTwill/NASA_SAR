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

`CaseSummary` has no `location` or `bbox`, and `thumbnail_url` is `null` for all four cases.

- **Ask:** `bbox` (and `place`) in `CaseSummary`, or a filled `thumbnail_url`.
- **Until then:** the case list fetches each case to frame its map thumbnail.

## 3. A type for each timeline item

`timeline[]` items are `{label, at}`. The pass timeline needs to tell the event, a NISAR acquisition and an ASF
publication apart to draw them on separate rows.

- **Ask:** `kind: "event" | "acquisition" | "publication"` on each item.
- **Until then:** all items are drawn on one row with their labels.

## 4. English inside French and Arabic texts (answers)

Seen on live `/api/ask` and `/api/answers/*` (backend with no NISAR data on this machine):

- `verdict.text.fr` / `.ar` end with an English sentence from the agent, for example
  "… ne permet encore de répondre ici. needs an earlier pair and a pair of the same length on the same track …".
- Step summaries sent as `backend.step` carry the same English text in all three languages
  ("found 0 interferograms covering the point"), and the failed step's `error` is "failed" in all three.

- **Ask:** the reason in the page language (or a template id with parameters, like `step.search_scenes`, which the
  interface already renders in FR/EN/AR).
- **Until then:** the interface shows the backend's text as it is; it does not translate or hide it.

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
