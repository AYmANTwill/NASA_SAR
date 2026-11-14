import maplibregl, { type GeoJSONSource, type LngLatBoundsLike, type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { Bounds, RasterLayer } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { basemapStyle, loadBasemap } from "./basemap";
import "./RadarMap.css";

export interface RadarMapProps {
  /** The area to frame (the API's bbox). */
  frame: Bounds;
  /** The API's point of the event, drawn as a dot. */
  point?: { lat: number; lon: number };
  /** The raster shown, exactly as the API sent it (PNG + bounds), or none. */
  layer: RasterLayer | null;
  label: string;
  /** When set, a click (or Enter on the focused map, at its centre) picks a point. */
  onPick?: (point: { lat: number; lon: number }) => void;
  /** Whether to draw the study-area rectangle (off for a world view). */
  showArea?: boolean;
}

const RASTER_OPACITY = 0.88;
const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
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
export default function RadarMap({ frame, point, layer, label, onPick, showArea = true }: RadarMapProps) {
  const { t } = useText();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const pick = useRef(onPick);
  pick.current = onPick;
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState<"webgl" | "image" | null>(null);

  // Create the map once.
  useEffect(() => {
    let disposed = false;
    void loadBasemap().then((basemap) => {
      if (disposed || !container.current) return;
      try {
        const m = new maplibregl.Map({
          container: container.current,
          style: basemapStyle(basemap),
          bounds: toLngLat(frame),
          fitBoundsOptions: { padding: 32 },
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
        m.on("resize", () => container.current?.setAttribute("data-idle", "false"));
        m.on("error", (event) => {
          if ((event as { sourceId?: string }).sourceId === "radar") setFailure("image");
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
      m.fitBounds(toLngLat(frame), { padding: 32, duration: reducedMotion() ? 0 : 900 });
    }
    framed.current = key;
  }, [frame, point, ready, showArea]);

  // The radar raster.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("radar")) m.removeLayer("radar");
    if (m.getSource("radar")) m.removeSource("radar");
    setFailure(null);
    if (!layer) return;
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
    m.addLayer({ id: "radar", type: "raster", source: "radar", paint: { "raster-opacity": RASTER_OPACITY, "raster-fade-duration": 0 } }, "area");
  }, [layer, ready]);

  return (
    <div className="radar-map" role="region" aria-label={label}>
      <div ref={container} className="radar-map-canvas" />
      {failure === "webgl" && <p className="radar-map-failure">{t("map.noWebgl")}</p>}
      {failure === "image" && (
        <p className="radar-map-failure" role="alert">
          {t("map.imageFailed")}
        </p>
      )}
    </div>
  );
}
