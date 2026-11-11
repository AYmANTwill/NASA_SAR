import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Bounds, Earthquake, RasterLayer } from "@/api/contract";
import { useOnline } from "@/api/queries";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";
import { buildStyle, labelField, LABEL_LAYERS } from "./basemap";
import { Legend, type LayerState } from "./Legend";

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
}

const EQ_SOURCE = "earthquakes";

export default function RadarMap({ ariaLabel, bounds, layers = [], earthquakes = [], markers = [], picked, onPick, legend = true, className, interactive = true }: RadarMapProps) {
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

  // Sync raster layers.
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
    const beforeId = map.getLayer("borders") ? "borders" : undefined;
    // Add in reverse so the first layer ends on top.
    for (const l of [...layers].reverse()) {
      const id = "r-" + l.id;
      const [w, s, e, n] = l.bounds;
      if (!map.getSource(id)) {
        map.addSource(id, { type: "image", url: l.url, coordinates: [[w, n], [e, n], [e, s], [w, s]] });
        map.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": 0.85, "raster-fade-duration": 0 } }, beforeId);
      }
      const st = state[l.id];
      if (st) {
        map.setPaintProperty(id, "raster-opacity", st.opacity);
        map.setLayoutProperty(id, "visibility", st.visible ? "visible" : "none");
      }
    }
  }, [layers, ready, state]);

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
      return new maplibregl.Marker({ element: el }).setLngLat([mk.lon, mk.lat]).addTo(map);
    });
    return () => created.forEach((m) => m.remove());
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
