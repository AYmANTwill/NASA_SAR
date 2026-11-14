import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type CanvasSource, type GeoJSONSource, type Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Bounds, Earthquake, RasterLayer } from "@/api/contract";
import { useOnline } from "@/api/queries";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";
import { buildStyle, labelField, LABEL_LAYERS } from "./basemap";
import { Legend, type LayerState } from "./Legend";
import { drawReveal, loadRaster, type RevealRaster } from "@/motion/rasterReveal";
import { alongOf, drawEcho, drawPass, passCovering, type PassGeometry, type PassStyle, type Pt } from "@/motion/swath";
import { prefersReducedMotion, STAGE, type PassDirection } from "@/motion/motion";

/**
 * Staging drawn over the map:
 * - scan: the agent is working; passes sweep over the point being investigated, in a loop;
 * - pass: a new answer; one pass in the acquisition's flight direction reveals the rasters;
 * - intro: one pass over the whole view; each marker echoes as the beam crosses it.
 */
export type MapMotion =
  | { kind: "scan"; key: string }
  | { kind: "pass"; key: string; direction: PassDirection }
  | { kind: "intro"; key: string }
  | null;

export interface MapMarker {
  id: string;
  lat: number;
  lon: number;
  label: string;
  title: string;
  onSelect?: () => void;
  active?: boolean;
}

export interface RadarMapProps {
  ariaLabel: string;
  bounds?: Bounds | null;
  layers?: RasterLayer[];
  earthquakes?: Earthquake[];
  markers?: MapMarker[];
  picked?: { lat: number; lon: number } | null;
  onPick?: (lat: number, lon: number) => void;
  legend?: boolean;
  className?: string;
  /** Fixed view for small static figures (no pan/zoom). */
  interactive?: boolean;
  motion?: MapMotion;
}

const EQ_SOURCE = "earthquakes";

/** MapLibre's CanvasSource reports type "image" (it extends ImageSource): detect it by its playback API. */
const isCanvasSource = (src: unknown): src is CanvasSource => !!src && typeof (src as CanvasSource).play === "function";

export default function RadarMap({ ariaLabel, bounds, layers = [], earthquakes = [], markers = [], picked, onPick, legend = true, className, interactive = true, motion = null }: RadarMapProps) {
  const { t, lang } = useText();
  const online = useOnline();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [startedOffline] = useState(() => !online);
  const [state, setState] = useState<Record<string, LayerState>>({});
  const [showQuakes, setShowQuakes] = useState(true);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const overlay = useRef<HTMLCanvasElement>(null);
  const rasters = useRef(new Map<string, RevealRaster>());
  const markerEls = useRef<{ el: HTMLElement; lon: number; lat: number }[]>([]);
  const stateRef = useRef(state);
  stateRef.current = state;
  /** Raster ids that still wait for their reveal pass. */
  const pendingReveal = useRef(new Set<string>());

  // Create the map once.
  useEffect(() => {
    if (!container.current) return;
    let map: MlMap;
    try {
      map = new maplibregl.Map({
        container: container.current,
        style: buildStyle(lang, online),
        center: [-5.5, 33.5],
        zoom: 4,
        attributionControl: false,
        interactive,
        dragRotate: false,
        pitchWithRotate: false,
        cooperativeGestures: false,
        locale: {
          "NavigationControl.ZoomIn": t("map.zoomIn", { defaultValue: "+" }),
          "NavigationControl.ZoomOut": t("map.zoomOut", { defaultValue: "−" }),
        },
      });
    } catch {
      setFailed(true);
      return;
    }
    mapRef.current = map;
    if (import.meta.env.DEV) (window as unknown as { __nisarMaps?: MlMap[] }).__nisarMaps = [...((window as unknown as { __nisarMaps?: MlMap[] }).__nisarMaps ?? []), map];
    map.on("error", () => {
      /* Tile or glyph failures (e.g. offline) are expected; the local basemap remains. */
    });
    if (interactive) map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    // style.load fires once the style is parsed; "load" would wait for remote tiles (never offline).
    map.once("style.load", () => setReady(true));
    map.on("click", (e) => onPickRef.current?.(e.lngLat.lat, e.lngLat.lng));
    return () => {
      map.remove();
      mapRef.current = null;
      setReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Localize labels and control names.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const id of LABEL_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "text-field", labelField(lang));
    const el = container.current;
    el?.querySelector(".maplibregl-ctrl-zoom-in")?.setAttribute("aria-label", t("map.zoomIn"));
    el?.querySelector(".maplibregl-ctrl-zoom-in")?.setAttribute("title", t("map.zoomIn"));
    el?.querySelector(".maplibregl-ctrl-zoom-out")?.setAttribute("aria-label", t("map.zoomOut"));
    el?.querySelector(".maplibregl-ctrl-zoom-out")?.setAttribute("title", t("map.zoomOut"));
    el?.querySelector(".maplibregl-ctrl-attrib-button")?.setAttribute("aria-label", t("map.attribution"));
    el?.querySelector(".maplibregl-ctrl-attrib-button")?.setAttribute("title", t("map.attribution"));
  }, [lang, ready, t]);

  // Default visibility/opacity for new layers.
  const layerKey = layers.map((l) => l.id).join("|");
  useEffect(() => {
    setState((prev) => {
      const next: Record<string, LayerState> = {};
      layers.forEach((l, i) => (next[l.id] = prev[l.id] ?? { visible: i === 0 || l.kind !== "coherence_loss", opacity: 0.85 }));
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layerKey]);

  // Sync raster layers. Each PNG is drawn into a canvas source so a pass can reveal it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const wanted = new Set(layers.map((l) => "r-" + l.id));
    for (const layer of map.getStyle().layers ?? []) {
      if (layer.id.startsWith("r-") && !wanted.has(layer.id)) {
        map.removeLayer(layer.id);
        if (map.getSource(layer.id)) map.removeSource(layer.id);
      }
    }
    for (const id of [...rasters.current.keys()]) if (!wanted.has(id)) rasters.current.delete(id);
    const beforeId = map.getLayer("borders") ? "borders" : undefined;
    const reorder = () => {
      // The first layer ends on top.
      for (const l of [...layers].reverse()) if (map.getLayer("r-" + l.id)) map.moveLayer("r-" + l.id, beforeId);
    };
    const applyState = (l: RasterLayer) => {
      const id = "r-" + l.id;
      const st = stateRef.current[l.id];
      if (!st || !map.getLayer(id)) return;
      map.setPaintProperty(id, "raster-opacity", st.opacity);
      map.setLayoutProperty(id, "visibility", st.visible ? "visible" : "none");
    };
    for (const l of layers) {
      const id = "r-" + l.id;
      if (rasters.current.has(id)) {
        applyState(l);
        continue;
      }
      const [w, s, e, n] = l.bounds;
      const coordinates: [[number, number], [number, number], [number, number], [number, number]] = [[w, n], [e, n], [e, s], [w, s]];
      const r = loadRaster(l.url);
      rasters.current.set(id, r);
      if (motion?.kind === "pass" && !prefersReducedMotion()) pendingReveal.current.add(id);
      void r.loaded.then((ok) => {
        const m = mapRef.current;
        if (!m || m.getSource(id) || rasters.current.get(id) !== r) return;
        if (ok) {
          drawReveal(r, null, pendingReveal.current.has(id) ? 0 : 1);
          m.addSource(id, { type: "canvas", canvas: r.canvas, coordinates, animate: false });
        } else {
          // The image could not be read into a canvas (e.g. cross-origin without CORS): show it as is.
          pendingReveal.current.delete(id);
          m.addSource(id, { type: "image", url: l.url, coordinates });
        }
        m.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": 0.85, "raster-fade-duration": 0 } }, beforeId);
        reorder();
        applyState(l);
      });
    }
    reorder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layers, ready, state]);

  // Staging over the map (scan while the agent works, pass on a new answer, intro on the home map).
  const motionKey = motion ? `${motion.kind}:${motion.key}` : "";
  useEffect(() => {
    const map = mapRef.current;
    const canvas = overlay.current;
    if (!map || !ready || !canvas || !motion) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = prefersReducedMotion();
    const pendingSet = pendingReveal.current;
    const rasterMap = rasters.current;
    const css = getComputedStyle(document.documentElement);
    const triplet = (hex: string, fallback: string) => {
      const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex.trim());
      return m ? `${parseInt(m[1], 16)} ${parseInt(m[2], 16)} ${parseInt(m[3], 16)}` : fallback;
    };
    const style: PassStyle = { ink: triplet(css.getPropertyValue("--ink"), "20 33 43"), accent: triplet(css.getPropertyValue("--accent"), "13 88 115") };
    let raf = 0;
    let cancelled = false;
    const size = () => {
      const dpr = window.devicePixelRatio || 1;
      const { clientWidth: w, clientHeight: h } = canvas;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w, h };
    };
    const clear = () => {
      const { w, h } = size();
      ctx.clearRect(0, 0, w, h);
    };
    const project = (lon: number, lat: number): Pt => {
      const p = map.project([lon, lat]);
      return { x: p.x, y: p.y };
    };
    const runPass = (g: PassGeometry, duration: number, onFrame?: (t: number, front: number, now: number) => void) =>
      new Promise<void>((resolve) => {
        const start = performance.now();
        const tick = (now: number) => {
          if (cancelled) return resolve();
          const t = Math.min(1, (now - start) / duration);
          clear();
          const fade = t > 0.85 ? (1 - t) / 0.15 : t < 0.08 ? t / 0.08 : 1;
          const front = drawPass(ctx, g, t, style, now, fade);
          onFrame?.(t, front, now);
          if (t < 1) raf = requestAnimationFrame(tick);
          else {
            clear();
            resolve();
          }
        };
        raf = requestAnimationFrame(tick);
      });
    const afterCamera = () =>
      new Promise<void>((resolve) => {
        if (!map.isMoving()) return resolve();
        map.once("moveend", () => resolve());
      });
    const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r(null)));

    void (async () => {
      if (motion.kind === "scan") {
        if (reduced) return;
        const dirs: PassDirection[] = ["ascending", "descending"];
        for (let i = 0; !cancelled; i++) {
          const { w, h } = size();
          const focus = picked ? [project(picked.lon, picked.lat)] : [];
          await runPass(passCovering(dirs[i % 2], w, h, focus), 2200);
        }
        return;
      }

      if (motion.kind === "pass") {
        const ids = layers.map((l) => "r-" + l.id);
        await Promise.all(ids.map((id) => rasters.current.get(id)?.loaded));
        // Wait for the load handlers to create the sources, then for the camera to settle on the answer.
        for (let i = 0; i < 120 && !cancelled && ids.some((id) => pendingReveal.current.has(id) && !map.getSource(id)); i++) await nextFrame();
        await nextFrame();
        await afterCamera();
        if (cancelled) return;
        const pending = ids.filter((id) => pendingReveal.current.has(id));
        const targets = pending.filter((id) => isCanvasSource(map.getSource(id)));
        const sources = targets.map((id) => map.getSource(id) as CanvasSource);
        const reveal = (t: number) => pending.forEach((id) => { const r = rasters.current.get(id); if (r) drawReveal(r, motion.direction, t); });
        const finish = () => {
          reveal(1);
          sources.forEach((src) => src.play());
          void nextFrame().then(nextFrame).then(() => sources.forEach((src) => src.pause()));
          pending.forEach((id) => pendingReveal.current.delete(id));
        };
        if (reduced || !targets.length) return finish();
        // The pass spans the top raster's footprint, so the beam front matches the reveal line.
        const top = layers.find((l) => targets.includes("r-" + l.id)) ?? layers[0];
        const [w0, s0, e0, n0] = top.bounds;
        const corners = [project(w0, n0), project(e0, n0), project(e0, s0), project(w0, s0)];
        const { w, h } = size();
        const g = passCovering(motion.direction, w, h, corners);
        const along = corners.map((c) => alongOf(g, c));
        g.along = [Math.min(...along), Math.max(...along)];
        sources.forEach((src) => src.play());
        await runPass(g, STAGE.reveal, (t) => reveal(t));
        return finish();
      }

      // intro
      if (reduced) return;
      await afterCamera();
      await nextFrame();
      if (cancelled) return;
      const pts = markerEls.current.map((m) => ({ ...m, p: project(m.lon, m.lat) }));
      const { w, h } = size();
      const g = passCovering("descending", w, h, pts.map((m) => m.p));
      const crossed = new Map<number, number>();
      await runPass(g, STAGE.intro, (_t, front, now) => {
        pts.forEach((m, i) => {
          if (!crossed.has(i) && alongOf(g, m.p) <= front) {
            crossed.set(i, now);
            m.el.classList.add("marker-echo");
          }
          const at = crossed.get(i);
          if (at != null) drawEcho(ctx, m.p, now - at, style);
        });
      });
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      clear();
      // An interrupted reveal never leaves a raster hidden: show it whole.
      for (const id of pendingSet) {
        const r = rasterMap.get(id);
        const src = mapRef.current?.getSource(id) as CanvasSource | undefined;
        if (r) drawReveal(r, null, 1);
        if (isCanvasSource(src)) {
          src.play();
          requestAnimationFrame(() => requestAnimationFrame(() => src.pause()));
        }
      }
      pendingSet.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [motionKey, ready]);

  // Earthquakes overlay.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const data: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: earthquakes.map((q) => ({ type: "Feature", geometry: { type: "Point", coordinates: [q.lon, q.lat] }, properties: { mag: q.magnitude.value, role: q.role } })),
    };
    const source = map.getSource(EQ_SOURCE) as GeoJSONSource | undefined;
    if (source) source.setData(data);
    else {
      map.addSource(EQ_SOURCE, { type: "geojson", data });
      map.addLayer({
        id: "eq-after", type: "circle", source: EQ_SOURCE, filter: ["==", ["get", "role"], "aftershock"],
        paint: { "circle-radius": ["interpolate", ["linear"], ["get", "mag"], 4, 3, 6, 7], "circle-color": "rgba(255,255,255,0.6)", "circle-stroke-color": "#14212b", "circle-stroke-width": 1.2 },
      });
      map.addLayer({
        id: "eq-main", type: "circle", source: EQ_SOURCE, filter: ["==", ["get", "role"], "mainshock"],
        paint: { "circle-radius": 9, "circle-color": "#14212b", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 },
      });
    }
    for (const id of ["eq-after", "eq-main"]) map.setLayoutProperty(id, "visibility", showQuakes ? "visible" : "none");
  }, [earthquakes, ready, showQuakes]);

  // HTML markers (keyboard reachable).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const created = markers.map((mk) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className =
        "grid size-7 place-items-center rounded-full border-2 text-xs font-semibold shadow-sm transition-transform hover:scale-110 " +
        (mk.active ? "border-white bg-[var(--accent)] text-white" : "border-[var(--accent)] bg-white text-[var(--accent)]");
      el.textContent = mk.label;
      el.setAttribute("aria-label", mk.title);
      el.title = mk.title;
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        mk.onSelect?.();
      });
      return { marker: new maplibregl.Marker({ element: el }).setLngLat([mk.lon, mk.lat]).addTo(map), el, mk };
    });
    markerEls.current = created.map(({ el, mk }) => ({ el, lon: mk.lon, lat: mk.lat }));
    return () => {
      created.forEach(({ marker }) => marker.remove());
      markerEls.current = [];
    };
  }, [markers, ready]);

  // Picked point.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !picked) return;
    const el = document.createElement("div");
    el.className = "size-4 rounded-full border-[3px] border-white bg-[var(--ink)] shadow ring-1 ring-[var(--ink)]";
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", t("map.picked"));
    const marker = new maplibregl.Marker({ element: el }).setLngLat([picked.lon, picked.lat]).addTo(map);
    return () => void marker.remove();
  }, [picked, ready, t]);

  // Fit to bounds.
  const boundsKey = bounds ? bounds.join(",") : "";
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !bounds) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Keep the measured area clear of the legend (bottom, inline-end).
    const wide = map.getContainer().clientWidth >= 768;
    const rtl = document.documentElement.dir === "rtl";
    const side = legend && wide && layers.length > 0 ? 320 : 40;
    const padding = { top: 40, bottom: 40, left: rtl ? side : 40, right: rtl ? 40 : side };
    map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], { padding, duration: reduced ? 0 : 700, maxZoom: 11 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boundsKey, ready]);

  const legendLayers = useMemo(() => layers, [layers]);

  return (
    <div className={cn("relative isolate overflow-hidden bg-[#d9e3e9]", className)}>
      {/* Inline position: maplibre-gl.css forces .maplibregl-map to position:relative. */}
      <div ref={container} style={{ position: "absolute", inset: 0 }} role="region" aria-label={ariaLabel} />
      <canvas ref={overlay} aria-hidden className="pointer-events-none absolute inset-0 z-[1] size-full" />
      {failed && <p className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-ink-2">{t("map.noWebgl")}</p>}
      {startedOffline && !failed && (
        <p className="absolute start-2 top-2 rounded-sm bg-white/90 px-2 py-1 text-xs text-ink-2 shadow-sm">{t("map.offlineBase")}</p>
      )}
      {legend && (legendLayers.length > 0 || earthquakes.length > 0) && (
        <Legend
          layers={legendLayers}
          state={state}
          onChange={(id, next) => setState((s) => ({ ...s, [id]: { ...s[id], ...next } }))}
          earthquakes={earthquakes.length > 0 ? { visible: showQuakes, onToggle: () => setShowQuakes((v) => !v) } : null}
        />
      )}
    </div>
  );
}
