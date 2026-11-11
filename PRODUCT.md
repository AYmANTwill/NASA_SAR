# NISAR Pulse: product brief

**The radar investigator.** Point at a place, ask in French, Arabic or English, and get back what the NISAR L-band radar measured, how confident it is, and what to do next. Three verbs carry the product: **Ask**, **Prove**, **Watch**.

## Audience

- **Scientific jury** (NASA Space Apps, 14 November 2026). Needs to see real calibrated data, honest uncertainty, and an answer that says what it does not know.
- **Civil-protection officer.** "Which villages were affected by the earthquake?" Decides where to send teams first.
- **Dam or mine engineer.** "Is this embankment moving, and is it accelerating?" Decides when to schedule an inspection.

## Voice

Sober, precise, honest about uncertainty. Plain verbs, sentence case, no hype. "Stable within noise" is a valid answer and gets the same care as an alert. Errors say what happened and how to fix it. They never apologise and never guess.

## Anti-references

- Generic SaaS dashboards: KPI cards, gradient washes, identical rounded tiles.
- Purple gradients.
- Neon "cyberpunk satellite" aesthetics: glowing globes, dark sci-fi chrome, scanning lines.

## Design principles

1. **The measurement is the hero.** Every number appears as `value ± uncertainty unit`. The signature element is the *noise ruler*: a number line centred on zero, showing the noise band, the ±σ whisker and the value.
2. **Colour has a job.** The ground is light so the rasters carry the colour. There is one ink and one accent (L-band blue-teal). Displacement uses a diverging scale centred on zero, coherence a sequential one. Watch levels differ in lightness and always come with an icon and a word.
3. **Order is meaning.** In an answer, the agent's steps come first, then the verdict, then the evidence. "What the radar cannot tell here" always comes last.
4. **Three languages, one layout.** Arabic mirrors the layout (logical CSS properties). Number lines, charts and code stay left to right.

## Product rules (non-negotiable)

- No number is hard-coded in the interface; every number comes from the API. If data is missing, the UI shows an explicit empty state (checked by `npm run check:numbers`).
- Every measurement shown carries its uncertainty (bar, band or explicit ±). The contract requires it.
- Every answer ends with "What the radar cannot tell here".
- Confidence (High, Medium, Low) is displayed as received from the API, never recomputed.
- Watch levels (Yellow, Orange, Red) are never conveyed by colour alone.
- No promise of prediction. Fukuzono windows are labelled "indication", never "forecast".
- FR (default), AR (full RTL) and EN. Switching language does not reload the page.
- Offline demo mode: the demo path works without the Internet, served from cache, with a discreet offline indicator.

## Design tokens (summary)

| Token | Value | Use |
|---|---|---|
| `--ground` | `#eef1f3` | page |
| `--surface` | `#ffffff` | panels |
| `--ink` | `#14212b` | text |
| `--accent` | `#0d5873` | actions, high confidence |
| `--series-1/2` | `#1a6ea8` / `#c2582b` | chart series (validated for CVD, chroma and contrast) |
| level yellow, orange, red | `#f4cf45` / `#d9650f` / `#9f1f15` | watch levels (with icon + text) |

Type: **IBM Plex Sans** and **IBM Plex Sans Arabic** (one family designed for both scripts), self-hosted for offline use. IBM Plex Mono is used only for tool names and parameters in the agent steps. All contrast pairs pass WCAG AA (`npm run check:contrast`).
