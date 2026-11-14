# NISAR Pulse v2: design

Status: decided (section 6). Direction C, IBM Plex, light only.

## 1. Who reads this screen, and what they decide

| reader | situation | what they must get in 10 seconds | what makes them distrust it |
|---|---|---|---|
| **Civil-protection officer** | ops room or a laptop in the field, the day after an earthquake or a flood, often projected, sometimes printed | where the ground changed, how big, how sure, who lives there, what the radar cannot see | a number with no source, a map with no legend, a confident colour on an unmeasured value |
| **Hackathon jury** (scientists, NASA staff) | 3-minute demo on a projector, then 5 minutes of clicking | that the numbers are NISAR's, checked against an independent reference, and honest about their limits | anything that looks typed by hand, hidden uncertainty, a "0" that is really "not done yet" |

Both read the same screen. The officer reads it top-down for the decision; the jury reads it bottom-up for the
evidence. The layout has to serve both without a mode switch.

## 2. What the real tools do well (research notes)

| tool | what makes it clear | what we take |
|---|---|---|
| **Copernicus EMS Rapid Mapping** (ready-to-print maps) | Every map is a *map frame + marginalia*. The legend lists only what is in the frame, except grading classes, which are always all listed. A *consequences table* (people, buildings, roads) sits next to the map, with `NA` where data is incomplete. Delineation and grading are distinct, named products. | Marginalia as a permanent column, never a hover. The exposure table with an explicit "not measured yet" in place of `NA`. Legends with the full class range. |
| **ARIA / JPL Damage Proxy Maps** (NASA Disasters portal) | One product per event, dated, sensor named (Sentinel-1, ALOS-2). The limits travel with the map: "less reliable over vegetated or mountainous terrain", "yellow-to-red pixels indicate surface change, not always building damage", "small-scale change may not be detected". | Limits written in plain words and attached to the map, not to a FAQ. The sensor and pair dates printed on the map itself. |
| **USGS earthquake event page** | One event = one page, fixed section order (summary, ShakeMap, PAGER, ground failure, interactive map, aftershocks). PAGER puts the alert at the top centre, then exposure, then a footer with the event id and an "automatically generated" disclaimer. | A fixed section order per case, the same for all four. The event id and source link in the case header. |
| **NASA Worldview** | The timeline is a first-class control at the bottom of the map; a *timeline availability* panel shows which layers have data on which dates; "hide unavailable" filters layers. Distraction-free mode hides all chrome. | A timeline strip under the map showing the event, every NISAR acquisition and every ASF publication date. A presentation mode for the projector. |
| **Felt, Windy** (map-first apps) | The map is the page. Panels float or dock and never cover the area of interest; one control layer at a time. Legends are compact and attached to the active layer. | Map first; panels dock to one side (the reading side, mirrored in Arabic); one active raster at a time with its legend. |

Sources: [Copernicus EMS rapid mapping manual: map](https://mapping.emergency.copernicus.eu/about/rapid-mapping-manual/product-overview/what-is-delivered-in-a-product/map/),
[legend rules](https://mapping.emergency.copernicus.eu/about/rapid-mapping-manual/product-overview/what-is-delivered-in-a-product/map/map-marginalia/legend/),
[JRC 2020 rapid mapping manual (PDF)](https://emergency.copernicus.eu/mapping/sites/default/files/files/JRCTechnicalReport_2020_Manual%20for%20Rapid%20Mapping%20Products_final.pdf),
[ARIA DPM Türkiye 2023](https://data.amerigeoss.org/it/dataset/aria-damage-proxy-map-copernicus-sentinel-1-for-the-turkiye-earthquakes),
[ARIA DPM Peru 2021 item info](https://maps.disasters.nasa.gov/ags04/rest/services/peru_earthquake_202107/aria_dpm_sentinel1_20210802/ImageServer/info/iteminfo),
[USGS event page overview](https://www.usgs.gov/media/videos/usgs-earthquake-event-page-natural-hazards-mission-area),
[PAGER one-pager](https://earthquake.usgs.gov/data/pager/onepager.php),
[Worldview layer by layer](https://www.earthdata.nasa.gov/news/feature-articles/layer-layer-nasa-worldview-continues-improve),
[Worldview 3.7.0](https://www.earthdata.nasa.gov/news/blog/worldview-3.7.0-new-imagery),
[Felt vs Mapbox](https://felt.com/compare/mapbox).

## 3. Constraints that shape every direction

- **Colour belongs to the measurement.** The four map palettes are fixed by `backend/palettes.json`
  (displacement diverging blue–red centred on zero, coherence navy–yellow, coherence loss cream–brown, moisture
  sand–teal). They use most of the hue wheel already. Any interface colour that lands near them (a red badge, a teal
  accent, an orange warning) competes with the data. Watch levels (yellow, orange, red) come from the API.
- **"Not measured yet" is a first-class state.** Today all four cases are drafts whose NISAR values are
  placeholders `{value: 0, uncertainty: 0}`. The design must make that state impossible to read as a measurement,
  and must not show the Panama "disagree" badge for a placeholder Mw against USGS 7.7.
- **Three scripts, one layout.** Arabic mirrors the page (logical CSS properties). Numbers, number lines, charts and
  the map stay left to right; numbers keep Western digits (as written in Morocco) inside `<bdi dir="ltr">`.
- **Projector and print.** Light ground, AA contrast at projector gamma, every map exportable with its marginalia.
- **Offline demo.** Fonts self-hosted, the basemap works without tiles (bundled land and borders).

## 4. Three directions

### A. "Map sheet": the Copernicus way

The case is a map sheet: a large map frame and a fixed marginalia column (title block, legend, findings table,
exposure table, limits, sources, timeline). It reads like the product civil protection already receives, made
interactive.

```
+---------------------------------------------------------------+-----------------------+
|                                                               | PANAMA EARTHQUAKE     |
|                                                               | 9 Oct 2026 17:56 UTC  |
|                      MAP FRAME                                | USGS us6000u18k  [↗]  |
|              (one raster, north arrow, scale)                 |-----------------------|
|                                                               | Legend  [-cm ··· +cm] |
|                                                               |-----------------------|
|                                                               | Findings (table)      |
|                                                               | Exposure (table)      |
|                                                               | Limits                |
|                                                               | Sources · pairs       |
+---------------------------------------------------------------+-----------------------+
```

- Pros: instantly familiar to the officer; prints as-is; the marginalia make "always visible" structural.
- Cons: tables flatten the NISAR-vs-reference comparison into two columns of numbers; static, the timeline is a list;
  closest to the "broadsheet with hairlines" default; dense on a phone.

### B. "Radar console": the instrument way

The map is full-bleed on a dark basemap; the findings are instrument readouts docked along the edge; a live pass
track sweeps the map as the investigator works.

- Pros: rasters look vivid on dark; strong demo moment; feels like a NISAR ground station.
- Cons: the displacement palette's zero is near-white (`#f3f2ee`): on a dark ground the *unchanged* areas glow
  brightest, the opposite of what the map means. It is the "dark sci-fi chrome" that `frontend/PRODUCT.md` lists as
  an anti-reference, prints badly, and projects poorly in a lit room. Not recommended.

### C. "Evidence ledger": map + comparison strips (recommended)

Map first, docked to a ledger column. The ledger is the case's evidence in reading order: the headline, then one
**comparison strip** per finding, then exposure, then limits. Under the map, a **pass timeline** shows the event,
each NISAR acquisition and each ASF publication date; choosing a pair shows its raster.

The **comparison strip** is the one memorable element. One number line per finding, shared by NISAR and the
reference: two marks with their ±2σ and ±4σ extents, the gap between them, and the API's agreement in words
(`agrees within 2σ`, `partly`, `disagrees`, `no independent reference`). It shows *why* the backend said "agree"
without the interface computing anything: positions come from the API values, the word from the API's `agreement`.
A placeholder renders as an empty, hatched strip: "NISAR value not measured yet".

```
+-------------------------------------------------+------------------------------+
| ◂ Cases   Panama earthquake · DRAFT              |  FR  EN  AR     ⓘ offline    |
+-------------------------------------------------+------------------------------+
|                                                 | NISAR measured …  (headline) |
|                                                 |------------------------------|
|              MAP (one raster at a time)         | Moment magnitude             |
|      legend attached bottom-start, scale        |  NISAR  7.6 ± 0.1 Mw         |
|                                                 |  USGS   7.7 ± 0.1 Mw  [↗]   |
|                                                 |  ──────●──┼──○──────────     |
|                                                 |  agrees within 2σ            |
|                                                 |------------------------------|
|                                                 | Rupture length               |
|                                                 |  ░░░ not measured yet ░░░░   |
|-------------------------------------------------|------------------------------|
| ●event   ▲ ▲ ▲ acquisitions   ◆ ◆ published      | Exposure  people · buildings |
| Sep ───────────── Oct ───────────── Nov         |------------------------------|
+-------------------------------------------------+ What the radar cannot tell   |
                                                  |  · …   (always open)         |
                                                  +------------------------------+
```

(Values in the sketch are illustrative only, to show layout; no number will ever be typed in code.)

- Pros: the jury sees the validation, not just a claim; the officer reads headline → exposure → limits in one
  column; the timeline answers "which passes, published when"; one bold element, everything else quiet; adapts to
  the investigator (the same ledger holds an answer's metrics, evidence and limits).
- Cons: more custom drawing (the strip, the timeline) than tables; the strip needs a careful accessible
  equivalent (a text sentence and a data table for screen readers); on a phone the map and the ledger stack.

**Recommendation: C**, with A's discipline borrowed where it helps the officer: a legend that is always present and
lists the full range, an exposure table with explicit "not measured yet", and a print/export view laid out as a
map sheet.

## 5. Recommended direction in detail

### Type

- **Public Sans** (USWDS, the US government's public-service face; open licence) for Latin: sober, legible at
  projector distance, real tabular figures (`font-variant-numeric: tabular-nums`) for aligned values.
- **Noto Sans Arabic** for Arabic: a UI-grade naskh-sans with matching x-height and weights; one size step larger
  than Latin at the same role so both read with the same weight.
- Both self-hosted with `@fontsource` (offline demo). No monospace for data labels; numbers use the text face with
  tabular figures.
- Scale (1.25, base 16 px): 12.8 / 16 / 20 / 25 / 31 / 39. Headline 25–31 regular, not bold. Labels in sentence
  case; no all-caps eyebrows, no tracked-out labels. Line length ≤ 70 characters in the ledger.

### Colour: the interface has no hue

| token | value | use |
|---|---|---|
| `--paper` | `#f7f8f8` | page ground (cool, not cream) |
| `--sheet` | `#ffffff` | ledger, panels |
| `--ink` | `#151a1e` | text, marks, focus ring |
| `--ink-2` | `#4b555d` | secondary text (AA on both grounds) |
| `--rule` | `#d5dadd` | dividers, number-line axis |
| `--hatch` | `#151a1e` at 12 % | "not measured yet" and DRAFT hatching |

- Interaction is shown by weight, underline and a 2 px ink bar, never by a brand hue. Focus: 2 px ink ring with a
  2 px white halo, visible on the map and on any raster.
- The only hues on screen are the map palettes (from `backend/palettes.json`, verbatim, through the API's
  `palette` id) and the watch levels sent by the API. Agreement and confidence are words plus a shape
  (filled / half / hollow / dashed), never a colour, so they can never be confused with the displacement scale.
- DRAFT: a full-width band in ink with diagonal hatching and the word in the page language
  (`BROUILLON` / `DRAFT` / `مسودة`), repeated in the browser title. The demo build refuses to render a draft and says
  why.

### Layout

- Desktop ≥ 1200 px: map ~62 %, ledger ~38 % docked to the end side (right in FR/EN, left in AR), timeline under the
  map. 960–1200 px: ledger narrows, timeline collapses to the acquisitions row. < 960 px: map on top (50 vh), ledger
  below, timeline as a horizontal scroller.
- Fixed section order on every case (as on the USGS event page): header (title, date, place, source event id, status)
  → headline → findings → exposure → figures (charts, images) → limits → sources and NISAR products.
- Limits are never collapsible on a case or an answer. On a narrow screen they stay in the flow, not in a drawer.
- Case list: four large map thumbnails with title, date, kind and status; no KPI tiles.
- Presentation mode (`P`): hides navigation, enlarges type one step, keeps the DRAFT band and the limits.

### Motion

One orchestrated moment: when a case opens, the map frames the event's bbox and the pass timeline fills from the
event marker outward (acquisitions, then publication dates), then the first raster fades in. ~900 ms total, then
nothing moves on its own. Everything else is a response to an action (opening a pair, expanding a step), 150–200 ms.
`prefers-reduced-motion`: no camera flight, no fill, instant states. The investigator's live steps appear as they
arrive from the SSE stream; that is data, not decoration.

### Accessibility

- Every page reachable and usable with the keyboard (map included: `+`/`-`, arrows to pan, a "skip the map" link).
- Each comparison strip has a sentence equivalent (`aria-describedby`) and the ledger has a data table view.
- Contrast AA everywhere, checked in CI on the token pairs; legend labels on the map have a halo.
- Status, agreement, confidence and alert level always carry text, never colour or shape alone.
- `lang` and `dir` set on `<html>` on every language switch, without a reload.

## 6. Decisions (14 Nov 2026)

Adam asked for the most recommendable choice on each open question. Decided:

1. **Direction: C, "Evidence ledger"**, with three things taken from A: the legend is always present and lists the
   full range, the exposure table states "not measured yet" explicitly, and every case has a print / export view laid
   out as a map sheet. B is rejected (the palette's zero glows on a dark ground).
2. **Type: IBM Plex Sans + IBM Plex Sans Arabic**, not Public Sans + Noto. Plex Sans Arabic was drawn together with
   Plex Sans (matched weights, x-height and rhythm), which no Public Sans + Noto pairing gives; it has tabular
   figures; it is already self-hosted for the team's offline demo; and two interfaces of one product should share a
   typeface. v2 is distinct through its layout, the comparison strip and the hue-less chrome, not through the font.
   The section 5 type scale and rules stay; only the families change.
3. **Dark mode: not now.** Light only (projector in a lit room, print). Colours are tokens from the first commit, so a
   dark theme can be added later without touching components.
4. **Plugins:** `pr-review-toolkit` (claude-plugins-official) recommended, to be installed by Adam
   (`/plugin install pr-review-toolkit@claude-plugins-official`). No community skill installed.
   Accessibility is tested with `@axe-core/playwright` as a dev dependency of `frontend-v2/`.
