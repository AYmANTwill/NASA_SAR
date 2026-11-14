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
