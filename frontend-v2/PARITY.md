# Frontend parity and visual direction

Applies the repository skills `../frontend/.claude/skills/frontend-design/SKILL.md` and
`../frontend/.claude/skills/i18n-date-patterns/SKILL.md` to v2. The existing centralized Intl/i18next utilities
remain the formatting authority; the skill's unrelated example hooks and currencies are not introduced.

## Visual plan

An investigator's workspace: a quiet, dark navigation spine frames bright map sheets and evidence panels.
IBM Plex Sans and its Arabic companion remain the only families. Large, sentence-case page titles and generous
spacing establish hierarchy; outlines separate scientific evidence rather than decorate repeated tiles.

Tokens: paper `#eff3f4`, sheet `#ffffff`, ink `#172b36`, secondary ink `#4b5d68`, rule `#d0dadd`, navigation `#172b36`.
Color on maps remains the backend's palette; badges remain neutral except API watch levels. Layout is logical
and mirrors in Arabic. The map, numerical axes and uncertainty pairs stay left to right.

```
navigation spine | page title / purpose / primary action
                 | map or geographic locator | evidence and controls
                 | visible limitations and provenance
```

Critique: avoid turning this into another dashboard of decorative KPI cards. The memorable element is the
geographic evidence, with a navigation spine that gives the expanded product a clear home. No invented metrics,
selection-set accuracy, decorative alerts or synthetic scientific output is introduced.

## Porting scope

| frontend capability | v2 destination |
|---|---|
| Case list, details, sources, uncertainty, baseline help | Existing case ledger retained and styled |
| Full-size scientific figures | Accessible native dialog viewer with missing-image state |
| Discoveries, rank/exposure sorting, candidates and context | Dedicated Discover page, including disabled and empty states |
| L/C maps, coherence comparison by forest cover, explanation | Dedicated Proof page, including API not-available state |
| Point picker, earthquake and event markers, opacity/visibility | Shared map component, responsive recentering |
| Questions from links, cancellation, streamed steps, answers | Investigator and legacy URL aliases |
| Noise ruler and series | Signal/noise ruler and a shared scale for vertical/east components with matching units |
| Watches, next pass, deletion confirmation, notifications | Existing watch actions plus orbit clock |
| Offline query persistence, demo prefetch, offline shell | Validated response cache and production service worker |
| FR/EN/AR and RTL | Every original prose template/term retained; centralized formatters extended |
| Map sheet / presentation / export | Print stylesheet and report toolbar |

API features unavailable on the local backend remain explicitly unavailable. The original frontend fixture
adapter is not used as a substitute for real scientific data. Offline jury builds still refuse draft cases.

Decorative scan transitions accompany an investigation and a newly shown image. They do not alter the API's
PNG or represent a simulated satellite acquisition. Reduced-motion preferences disable the transitions.

The production worker caches the static shell and same-origin report images; only the client stores JSON after
contract validation. A first-visit image warm-up waits for worker control. Offline cache entries expire after a
week; health and writes remain live operations. The frozen jury demo keeps its separate snapshot/build gate.

## Validation

The live backend currently disables automatic discovery and does not supply the L/C comparison. These states
are checked against its real responses. Separate, explicitly synthetic UI scenarios exercise the available
branches, including forest bins, image layers, empty discovery lists and exposure sorting; they are never
imported by the production app. The template parity check covers all original FR/EN/AR template and term ids.

Browser checks cover the live case list, all five cases, linked answers, investigation, library, watches,
service status and new pages in FR/EN/AR at desktop and phone widths, with accessibility and image checks.
Captures were visually reviewed; corrections include clipped Arabic case titles, marker/control overlap,
responsive map framing and fixed spatial correspondence between C/L beam labels in Arabic.

The normal production offline check starts from an empty browser: it opens Bin El Ouidane once, waits for
the four figures and three RGBA overlays to be saved, disables the network, reloads, selects every overlay,
opens the case in Arabic and replays a prepared question. This is separate from snapshot-based jury checks.
