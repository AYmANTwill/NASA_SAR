# NISAR Pulse

An independent NASA Space Apps 2026 front-end prototype by **Team The SAR**. All analytical observations, events, predictions, alert messages and raster values shipped here are **simulated**, including the Venezuela earthquake scenario. This is not a verified disaster monitoring service.

## Run

Requires Node.js 22+ and npm. No API keys.

    npm install
    npm run dev

Open the URL Vite prints (normally http://127.0.0.1:5173). Mock assets are committed/generated in public/data, so generation is not needed on first run.

    npm run generate   # overwrite mock data with deterministic fixtures
    npm run build      # TypeScript check + production output in dist
    npm run preview
    npm run lint
    npm run format

## Experience

- A rotating MapLibre v5 globe with five clickable case markers and a 75-second guided tour.
- Five accent-themed dashboards with deck.gl BitmapLayer rasters, context GeoJSON, classification, optional illustrative extrusion, opacity controls and provenance-aware legends.
- A shared acquisition timeline updates rasters, selected metrics and the chart cursor.
- Compare synchronizes two maps: earlier SAR vs selected SAR, or NASA GIBS optical vs selected SAR. Both dates are independently selectable.
- Accessible Radix dialogs for alerts, methodology and shortcuts; small-screen layers and analysis sheets.
- JSON snapshot export and share links containing the case and date.
- Keyboard: Space play/pause, left/right acquisition, 1–5 case, C compare, L layers, ? guide.
- English/French date and number formatting and selected navigation labels. Scientific descriptions remain English.

## Architecture

- src/data: typed contract, JSON loading and mock/real endpoint selection.
- src/store: Zustand state; no persistence or localStorage.
- src/components/MapScene.tsx: map ownership, camera, overlays and synchronized comparison.
- src/features/intro: landing and case selection.
- src/features/dashboard: layer explorer, analysis and acquisition timeline.
- src/features/compare: accessible swipe and dates.
- src/features/about: focus-trapped methodology, alerts and shortcuts dialogs.
- src/styles: Tailwind entry point and responsive dark theme.
- scripts/generate-data.mjs: reproducible PNG + sidecar and GeoJSON fixtures.
- docs/DATA_CONTRACT.md: handoff for SAR, ML and data engineering.

The intro, dashboard and map are lazy-loaded. MapLibre, deck.gl and Recharts are split into separate chunks. Raster loading is on demand with next-date prefetch. Reduced motion disables globe auto-rotation, CSS pulses and animated camera duration.

## Plug in real exports

Read docs/DATA_CONTRACT.md. Replace public/data files with exports in exactly the documented shape. Set VITE_DATA_MODE=real in .env.local and rebuild. Set VITE_DATA_URL only if the files live at another directory or CORS-enabled HTTPS endpoint. The UI has no dependency on a backend framework. In real mode, file loading failures are reported rather than silently replaced with mocks.

Never run npm run generate over real exports: it overwrites the matching data paths.

## Static deployment

Build with npm run build and publish dist to Vercel, Netlify, or any HTTPS static host. Build command: npm run build. Publish directory: dist. No server functions or secrets. Navigation uses query parameters, so no SPA path rewrite is needed. The app can be embedded in a Streamlit iframe; the hosting service must permit framing. This delivery is a local codebase; no hosting account or production deployment was created.

## Data / visual assumptions and limitations

- GCOV is a diverging dB field, GUNW uses illustrative cyclic displacement colors, coherence uses a viridis-like ramp. These are demonstration rasters, not scientifically processed satellite observations.
- GUNW colors are not claimed to be wrapped interferometric phase. LOS displacement is not vertical displacement.
- Raster metadata uses geographic [west,south,east,north] bounds; generated images are north-up.
- NDVI and rainfall are generated context, while the optional GIBS true-color layer loads actual remote imagery. Future/unavailable GIBS dates can have no image coverage.
- OpenFreeMap basemaps, fonts and GIBS require internet access. Map failures show an explanation; local panels continue to work. A WebGL-capable browser is required for the globe.
- The location inspector displays the case series, explicitly labeled. Hover readouts sample an optional numeric grid in each raster sidecar; the shipped values are generated, not measured. Classification extrusion is illustrative, not a terrain model.
- Affected area and context cards describe the full case; acquisition-dependent metrics come from the time series.
- No Sentinel-1 raster is supplied, so no C-band comparison is offered. No public source repository URL was supplied.
- French localization currently covers navigation and date/number formatting, not all scientific text.
- Performance and WCAG compliance require additional device/accessibility audits; no claim of universal 60fps is made.

## Dependency note

The fixed requested MapLibre v5 series has npm advisory GHSA-jrc7-96c5-q579 (patched upstream in v6.5+). This implementation uses fixed trusted map attributions, DOM textContent for case marker names, and does not render dataset HTML in popups. Upgrade MapLibre after approving a change to the fixed stack; these precautions do not claim to patch the dependency. Run npm audit when preparing a deployment.

## Basemap adjustment

CARTO now requires an API key (https://www.carto.com/basemaps/apikey/), so the zero-key requirement is met with an original dark vector style over OpenFreeMap (https://openfreemap.org/). The label toggle remains available.

## Verification

Run npm run test:data to validate generated fixtures. With npm run dev already running, run npm run test:browser for desktop/mobile workflows, screenshots, tour completion, shortcuts and deep links. Browser tests use Chrome; set CHROME_PATH to your browser executable outside the default Windows installation. Screenshots and console results are saved in artifacts. The tour test advances browser timers through all 75 seconds.

Build output is about 62 KB gzipped for the shell, with separately loaded map/deck and chart chunks. The production build reports large vendor chunks for the WebGL and chart libraries. npm audit currently reports 1 critical MapLibre advisory and 7 moderate transitive tooling advisories; compatible npm audit fix did not resolve them.
