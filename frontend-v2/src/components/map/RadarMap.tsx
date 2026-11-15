import maplibregl, { type GeoJSONSource, type LngLatBoundsLike, type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { Bounds, RasterLayer } from "@/api/contract";
import { prefersReducedMotion } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { formatNumber } from "@/i18n/format";
import { basemapStyle, loadBasemap } from "./basemap";
import "./RadarMap.css";

export interface MapMarker { id: string; lat: number; lon: number; title: string; href?: string }

export interface RadarMapProps {
  /** The area to frame (the API's bbox). */
  frame: Bounds;
  /** The API's point of the event, drawn as a dot. */
  point?: { lat: number; lon: number };
  /** The raster shown, exactly as the API sent it (PNG + bounds), or none. */
  layer: Pick<RasterLayer, "url" | "bounds"> | null;
  label: string;
  /** When set, a click (or Enter on the focused map, at its centre) picks a point. */
  onPick?: (point: { lat: number; lon: number }) => void;
  /** Whether to draw the study-area rectangle (off for a world view). */
  showArea?: boolean;
  markers?: MapMarker[];
  earthquakes?: import("@/api/contract").Earthquake[];
  opacity?: number;
  resetKey?: number;
  activity?: boolean;
  background?: Pick<RasterLayer, "url" | "bounds">;
}

const RASTER_OPACITY = 0.88;
const toLngLat = (b: Bounds): LngLatBoundsLike => [
  [b[0], b[1]],
  [b[2], b[3]],
];

function areaFeature(b: Bounds): GeoJSON.Feature {
  const [w, s, e, n] = b;
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: [
        [w, s],
        [e, s],
        [e, n],
        [w, n],
        [w, s],
      ],
    },
  };
}

/**
 * The map of a case or an answer: an offline grey basemap, the study area,
 * the event point, and one radar raster (a PNG the backend rendered with the
 * canonical palette, placed at its bounds). North up and left to right in
 * every language. Keyboard: arrows pan, + / - zoom (MapLibre).
 */
export default function RadarMap({ frame, point, layer, background, label, onPick, showArea = true, markers = [], earthquakes = [], opacity = RASTER_OPACITY, resetKey = 0, activity = false }: RadarMapProps) {
  const { t, lang } = useText();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const pick = useRef(onPick);
  pick.current = onPick;
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<"webgl" | "image" | null>(null);
  const [backgroundFailed, setBackgroundFailed] = useState(false);
  const markerRefs = useRef<maplibregl.Marker[]>([]);
  const currentFrame = useRef(frame);
  currentFrame.current = frame;
  // Leave room for marker hit areas beside MapLibre's corner controls.
  const framePadding = useRef(32);
  framePadding.current = markers.length || earthquakes.length ? 64 : 32;

  // Create the map once.
  useEffect(() => {
    let disposed = false;
    void loadBasemap().then((basemap) => {
      if (disposed || !container.current) return;
      try {
        const m = new maplibregl.Map({
          container: container.current,
          canvasContextAttributes: { preserveDrawingBuffer: true },
          style: basemapStyle(basemap),
          bounds: toLngLat(frame),
          fitBoundsOptions: { padding: framePadding.current },
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
          attributionControl: { compact: true },
          locale: {
            "Map.Title": label,
            "NavigationControl.ZoomIn": t("map.zoomIn"),
            "NavigationControl.ZoomOut": t("map.zoomOut"),
            "AttributionControl.ToggleAttribution": t("map.attribution"),
          },
        });
        m.touchZoomRotate.disableRotation();
        m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
        m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
        // "idle" = everything drawn (tests and screenshots wait for it).
        m.on("idle", () => container.current?.setAttribute("data-idle", "true"));
        m.on("movestart", () => container.current?.setAttribute("data-idle", "false"));
        m.on("resize", () => {
          container.current?.setAttribute("data-idle", "false");
          m.fitBounds(toLngLat(currentFrame.current), { padding: framePadding.current, duration: 0 });
        });
        m.on("error", (event) => {
          if ((event as { sourceId?: string }).sourceId === "radar") setFailure("image");
          if ((event as { sourceId?: string }).sourceId === "optical") setBackgroundFailed(true);
        });
        m.on("click", (event) => pick.current?.({ lat: event.lngLat.lat, lon: event.lngLat.lng }));
        m.getCanvas().addEventListener("keydown", (event) => {
          if (event.key !== "Enter" || !pick.current) return;
          const centre = m.getCenter();
          pick.current({ lat: centre.lat, lon: centre.lng });
        });
        if (onPick) m.getCanvas().style.cursor = "crosshair";
        m.once("style.load", () => {
          m.addSource("area", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
          m.addLayer({ id: "area", type: "line", source: "area", paint: { "line-color": "#151a1e", "line-width": 1.5 } });
          m.addSource("point", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
          m.addLayer({
            id: "point",
            type: "circle",
            source: "point",
            paint: { "circle-radius": 5, "circle-color": "#151a1e", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
          });
          setReady(true);
        });
        map.current = m;
      } catch {
        setFailure("webgl");
      }
    });
    return () => {
      disposed = true;
      map.current?.remove();
      map.current = null;
    };
    // The map is created once; frame, point and layer changes are applied by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Frame and point. The map opens on the frame; a later change of frame moves the camera (the one motion).
  const framed = useRef<string | null>(null);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource("area") as GeoJSONSource).setData(showArea ? areaFeature(frame) : { type: "FeatureCollection", features: [] });
    (m.getSource("point") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: point ? [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [point.lon, point.lat] } }] : [],
    });
    const key = frame.join(",");
    if (framed.current !== null && framed.current !== key) {
      m.fitBounds(toLngLat(frame), { padding: framePadding.current, duration: prefersReducedMotion() ? 0 : 900 });
    }
    framed.current = key;
  }, [frame, point, ready, showArea]);

  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    markerRefs.current.forEach((marker) => marker.remove());
    const locations = [...markers, ...earthquakes.map((q) => ({ id: q.id, lat: q.lat, lon: q.lon, title: `${q.magnitude.type} ${formatNumber(q.magnitude.value, lang)}`, href: q.url ?? undefined }))];
    markerRefs.current = locations.map((location) => {
      const element = document.createElement(location.href ? "a" : "span");
      element.className = "map-location-marker";
      element.textContent = "●";
      element.title = location.title;
      element.setAttribute("aria-label", location.title);
      if (element instanceof HTMLAnchorElement && location.href) {
        element.href = location.href;
        if (/^https?:/.test(location.href)) { element.target = "_blank"; element.rel = "noreferrer"; }
      }
      return new maplibregl.Marker({ element }).setLngLat([location.lon, location.lat]).addTo(m);
    });
    return () => { markerRefs.current.forEach((marker) => marker.remove()); };
  }, [markers, earthquakes, ready, lang]);

  useEffect(() => {
    if (ready && map.current?.getLayer("radar")) map.current.setPaintProperty("radar", "raster-opacity", opacity);
  }, [opacity, ready, layer]);

  useEffect(() => {
    if (resetKey && ready) map.current?.fitBounds(toLngLat(frame), { padding: framePadding.current, duration: 0 });
  }, [resetKey, ready, frame]);

  // The API's optical background is below water, with its own bounds and no inferred scientific palette.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("optical")) m.removeLayer("optical");
    if (m.getSource("optical")) m.removeSource("optical");
    setBackgroundFailed(false);
    if (!background) return;
    const [w, s, e, n] = background.bounds;
    container.current?.setAttribute("data-idle", "false");
    m.addSource("optical", { type: "image", url: background.url, coordinates: [[w, n], [e, n], [e, s], [w, s]] });
    m.addLayer({ id: "optical", type: "raster", source: "optical", paint: { "raster-opacity": 1, "raster-fade-duration": 0 } }, m.getLayer("radar") ? "radar" : "area");
  }, [background, ready]);

  // The radar raster.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("radar")) m.removeLayer("radar");
    if (m.getSource("radar")) m.removeSource("radar");
    setFailure(null);
    if (!layer) return;
    container.current?.setAttribute("data-idle", "false");
    const [w, s, e, n] = layer.bounds;
    m.addSource("radar", {
      type: "image",
      url: layer.url,
      coordinates: [
        [w, n],
        [e, n],
        [e, s],
        [w, s],
      ],
    });
    m.addLayer({ id: "radar", type: "raster", source: "radar", paint: { "raster-opacity": opacity, "raster-fade-duration": 0 } }, "area");
    // Opacity is updated separately without refetching the PNG.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layer, ready]);

  return (
    <div className="radar-map" role="region" aria-label={label} data-background={background?.url ?? ""}>
      <div ref={container} className="radar-map-canvas" />
      {activity && <span className="map-sweep is-scanning" aria-hidden="true" />}
      {!activity && layer && ready && <span key={layer.url} className="map-sweep" aria-hidden="true" />}
      {failure === "webgl" && <p className="radar-map-failure">{t("map.noWebgl")}</p>}
      {backgroundFailed && <p className="radar-map-failure" role="status">{t("waterLayer.backgroundUnavailable")}</p>}
      {failure === "image" && (
        <p className="radar-map-failure" role="alert">
          {t("map.imageFailed")}
        </p>
      )}
    </div>
  );
}
