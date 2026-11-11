import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type Map as GLMap } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { BitmapLayer, GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { FeatureCollection } from "geojson";
import { Crosshair, Minus, Plus, LocateFixed, Mountain } from "lucide-react";
import { loadJSON, loadMeta, rasterURL, isMock } from "../data/loader";
import type { CaseStudy, Product, RasterMeta, Sample } from "../data/types";
import { relevantLayers, relevantRasters, dataPath, layerDefinitions } from "../data/layers";
import { caseText, classLabel, translate, useI18n } from "../lib/i18n";
import { useStore } from "../store/useStore";
import { reducedMotion } from "../lib/format";
import "maplibre-gl/dist/maplibre-gl.css";
import { mapStyle } from "../lib/mapStyle";

const style = mapStyle;
const context = [
  "classification",
  "events",
  "fires",
  "floodExtent",
  "infrastructure",
] as const;
function optical(map: GLMap, date: string, opacity: number) {
  const url =
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/" +
    date +
    "/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg";
  if (!map.getSource("optical")) {
    map.addSource("optical", {
      type: "raster",
      tiles: [url],
      tileSize: 256,
      maxzoom: 9,
      attribution: "NASA GIBS",
    });
    map.addLayer(
      {
        id: "optical",
        type: "raster",
        source: "optical",
        paint: { "raster-opacity": opacity },
      },
      "labels",
    );
  } else {
    (map.getSource("optical") as maplibregl.RasterTileSource).setTiles([url]);
    map.setPaintProperty("optical", "raster-opacity", opacity);
  }
}
export default function MapScene({
  cases,
  current,
  series,
}: {
  cases: CaseStudy[];
  current: CaseStudy;
  series: Sample[];
}) {
  const container = useRef<HTMLDivElement>(null),
    compareContainer = useRef<HTMLDivElement>(null),
    mapRef = useRef<GLMap | null>(null),
    overlayRef = useRef<MapboxOverlay | null>(null);
  const [ready, setReady] = useState(false),
    [failure, setFailure] = useState(""),
    [hover, setHover] = useState<{ lng: number; lat: number } | null>(null),
    [pin, setPin] = useState<{ lng: number; lat: number } | null>(null);
  const [metadata, setMetadata] = useState<
      Partial<Record<Product, RasterMeta>>
    >({}),
    [geo, setGeo] = useState<
      Partial<Record<(typeof context)[number], FeatureCollection>>
    >({}),
    [loading, setLoading] = useState(false);
  const {
    screen,
    layers,
    date,
    compare,
    compareDate,
    compareKind,
    swipe,
    extruded,
    focus,
    selectCase,
    set,
  } = useStore();
  const {locale,t}=useI18n();
  const products=useMemo(()=>relevantRasters(current),[current]);
  const path=dataPath(current);
  const visibleProducts=useMemo(()=>compare&&(compareKind==="sentinel1"||compareKind==="alos2")?products.filter(p=>p==="gcov"):products,[products,compare,compareKind]);
  const enabledKey=visibleProducts.filter(p=>layers[p]>0||compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov").join(",");
  const [ps,setPs]=useState<FeatureCollection|null>(null);
  const intro = screen === "intro",
    dateString = current.dates[Math.min(date, current.dates.length - 1)];
  useEffect(() => {
    if (!container.current) return;
    let map: GLMap;
    try {
      map = new maplibregl.Map({
        container: container.current,
        style,
        center: [-35, 16],
        zoom: 1.6,
        attributionControl: { compact: true },
        maxPitch: 65,
        canvasContextAttributes: { antialias: true },
      });
    } catch {
      setFailure(translate("WebGL is unavailable. Explore case data using the controls.",useStore.getState().locale));
      return;
    }
    mapRef.current = map;
    map.on("load", () => {
      map.setProjection({ type: "globe" });
      const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
      map.addControl(overlay);
      overlayRef.current = overlay;
      setReady(true);
    });
    map.on("error", () =>
      setFailure(translate("Some map imagery is unavailable. Data panels remain usable.",useStore.getState().locale)),
    );
    map.on("mousemove", (e) =>
      setHover({ lng: e.lngLat.lng, lat: e.lngLat.lat }),
    );
    map.on("click", (e) => {
      if (useStore.getState().screen === "dashboard")
        setPin({ lng: e.lngLat.lng, lat: e.lngLat.lat });
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    setPin(null);
    if (intro) {
      map.setProjection({ type: "globe" });
      map.flyTo({
        center: [-35, 16],
        zoom: 1.6,
        pitch: 0,
        bearing: 0,
        padding: {
          left: window.innerWidth > 900 ? 360 : 0,
          right: 0,
          top: 0,
          bottom: 0,
        },
        duration: reducedMotion() ? 0 : 2200,
      });
    } else {
      map.setProjection({ type: "mercator" });
      map.flyTo({
        center: [current.center[1], current.center[0]],
        zoom: current.zoom,
        pitch: current.pitch,
        bearing: current.bearing,
        padding: {
          left: window.innerWidth > 1100 ? 290 : 0,
          right: window.innerWidth > 1100 ? 310 : 0,
          top: 60,
          bottom: 180,
        },
        duration: reducedMotion() ? 0 : 2400,
        curve: 1.5,
      });
    }
  }, [ready, intro, current]);
  useEffect(() => {
    if (!ready || !intro || reducedMotion()) return;
    const id = window.setInterval(() => {
      const map = mapRef.current;
      if (map && !map.isMoving() && !map.isZooming())
        map.easeTo({
          center: [map.getCenter().lng + 0.6, map.getCenter().lat],
          duration: 1000,
          easing: (t) => t,
        });
    }, 1100);
    return () => clearInterval(id);
  }, [ready, intro]);
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const markers = (intro ? cases : [current]).map((c) => {
      const button = document.createElement("button");
      button.className = "map-beacon";
      button.style.setProperty("--marker", c.accentColor);
      button.setAttribute("aria-label", t("Explore")+" "+caseText(c,"name",locale));
      const dot = document.createElement("span"),
        ring = document.createElement("i"),
        label = document.createElement("b");
      label.textContent = caseText(c,"name",locale);
      const detail = document.createElement("div");
      detail.className = "beacon-detail";
      detail.textContent = caseText(c,"subtitle",locale)+" · "+c.dates.at(-1)+" · "+Number(c.kpis.affected_area_km2).toLocaleString(locale)+" km²";
      button.append(dot,ring,label,detail);
      button.title=caseText(c,"subtitle",locale)+" · "+Math.round(c.confidence*100)+"% "+t("model confidence");
      button.onclick = (e) => {
        e.stopPropagation();
        selectCase(c.id);
      };
      return new maplibregl.Marker({ element: button })
        .setLngLat([c.center[1], c.center[0]])
        .addTo(mapRef.current!);
    });
    const spread=()=>{
      if(!intro||!mapRef.current)return;
      const placed:{x:number;y:number}[]=[];
      markers.forEach(marker=>{
        const projected=mapRef.current!.project(marker.getLngLat());
        const candidates:[[number,number],...[number,number][]]=[[0,0],[-48,-36],[48,-36],[-48,40],[48,40],[0,-78],[0,78]];
        const offset=candidates.find(([x,y])=>placed.every(p=>Math.hypot(p.x-projected.x-x,p.y-projected.y-y)>48))??candidates[6];
        marker.setOffset(offset);placed.push({x:projected.x+offset[0],y:projected.y+offset[1]});
      });
    };
    spread();mapRef.current.on("move",spread);
    return () => {mapRef.current?.off("move",spread);markers.forEach(m=>m.remove());};
  }, [ready, intro, cases, current, selectCase,locale,t]);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all(
      context.map(
        async (key) =>
          [
            key,
            await loadJSON<FeatureCollection>(
              key + ".geojson",
              controller.signal,
            ),
          ] as const,
      ),
    )
      .then((result) => setGeo(Object.fromEntries(result)))
      .catch((e) => {
        if (e.name !== "AbortError")
          setFailure(translate("Context data could not be loaded.",useStore.getState().locale));
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (intro) return;
    const controller = new AbortController();
    setLoading(true);
    Promise.all(
      (enabledKey?enabledKey.split(",") as Product[]:[])
        .map(
          async (p) =>
            [
              p,
              await loadMeta(path, p, dateString, controller.signal),
            ] as const,
        ),
    )
      .then((rows) => {
        setMetadata((previous) => ({
          ...previous,
          ...Object.fromEntries(rows),
        }));
        setLoading(false);
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setLoading(false);
          setFailure(e.message);
        }
      });
    return () => controller.abort();
  }, [intro, path, dateString, enabledKey]);
  useEffect(() => {
    if (intro) return;
    products
      .filter((p) => layers[p] > 0)
      .forEach((p) => {
        const image = new Image();
        image.src = rasterURL(
          path,
          p,
          current.dates[(date + 1) % current.dates.length],
        );
      });
  }, [intro, current, date, layers,products,path]);
  useEffect(()=>{
    if(intro||layers.ps_insar<=0||!relevantLayers(current).some(l=>l.id==="ps_insar")){setPs(null);return;}
    const controller=new AbortController();
    loadJSON<FeatureCollection>(path+"/ps_insar/"+dateString+".geojson",controller.signal).then(setPs).catch(e=>{if(e.name!=="AbortError")setFailure(e.message);});
    return()=>controller.abort();
  },[intro,current,path,dateString,layers.ps_insar]);
  const deckLayers = useMemo(() => {
    if (intro) return [];
    return [
      new ScatterplotLayer({id:"ps-insar",data:ps?.features??[],visible:layers.ps_insar>0,opacity:layers.ps_insar,getPosition:f=>f.geometry.type==="Point"?f.geometry.coordinates as [number,number]:[0,0],getRadius:4,radiusUnits:"pixels",getFillColor:f=>{const v=Number(f.properties?.velocity_mm_year??0);return v<0?[70,150,255,220]:[255,95,125,220];},pickable:true,transitions:{opacity:400}}),
      ...visibleProducts.flatMap((p) =>
        metadata[p]
          ? [
              new BitmapLayer({
                id: "raster-" + p,
                image: rasterURL(path, p, dateString),
                bounds: metadata[p]!.bounds,
                opacity: compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov"?.85:layers[p],
                transitions: { opacity: 400 },
              }),
            ]
          : [],
      ),
      ...context.map(
        (key) =>
          new GeoJsonLayer({
            id: key,
            data: geo[key]
              ? {
                  ...geo[key],
                  features: geo[key]!.features.filter(
                    (f) => f.properties?.caseId === current.id && (f.properties?.siteId??current.sites?.[0].id??null)===(current.siteId??current.sites?.[0].id??null),
                  ),
                }
              : undefined,
            opacity: layers[key],
            visible: layers[key] > 0 && relevantLayers(current).some(l=>l.id===key),
            filled: true,
            stroked: true,
            getFillColor:
              key === "fires"
                ? [255, 107, 53, 180]
                : key === "floodExtent"
                  ? [59, 167, 255, 100]
                  : [181, 123, 255, 90],
            getLineColor: [220, 225, 240, 180],
            getLineWidth: 1,
            lineWidthUnits: "pixels",
            getPointRadius: 5,
            pointRadiusUnits: "pixels",
            extruded: extruded && key === "classification",
            getElevation: (f) => Number(f.properties?.height || 0) * 50,
            transitions: { opacity: 400 },
          }),
      ),
    ];
  }, [intro, metadata, current, dateString, layers, geo, extruded,visibleProducts,path,ps,compare,compareKind]);
  useEffect(() => {
    if (ready) overlayRef.current?.setProps({ layers: deckLayers });
  }, [ready, deckLayers]);
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    mapRef.current.setPaintProperty(
      "labels",
      "text-opacity",
      intro ? 0 : layers.labels * 0.65,
    );
    if (!intro && (layers.optical>0||mapRef.current.getSource("optical"))) optical(mapRef.current, dateString, layers.optical);
    else if (mapRef.current.getLayer("optical"))
      mapRef.current.setPaintProperty("optical", "raster-opacity", 0);
  }, [ready, intro, layers.labels, layers.optical, dateString]);
  useEffect(() => {
    if (focus && mapRef.current) {
      mapRef.current.flyTo({
        center: [focus[1], focus[0]],
        zoom: current.zoom + 1,
        duration: reducedMotion() ? 0 : 1200,
      });
      setPin({ lng: focus[1], lat: focus[0] });
    }
  }, [focus, current.zoom]);
  useEffect(() => {
    const primary = mapRef.current;
    if (!compare || !compareContainer.current || !primary || !ready) return;
    const before = new maplibregl.Map({
      container: compareContainer.current,
      style,
      center: primary.getCenter(),
      zoom: primary.getZoom(),
      bearing: primary.getBearing(),
      pitch: primary.getPitch(),
      interactive: false,
      attributionControl: false,
    });
    const controller = new AbortController();
    let overlay: MapboxOverlay | undefined;
    const sync = () =>
      before.jumpTo({
        center: primary.getCenter(),
        zoom: primary.getZoom(),
        bearing: primary.getBearing(),
        pitch: primary.getPitch(),
        padding: primary.getPadding(),
      });
    primary.on("move", sync);
    before.on("load", async () => {
      sync();
      if (compareKind === "optical") {
        optical(before, current.dates[compareDate], 1);
        return;
      }
      overlay = new MapboxOverlay({ interleaved: false, layers: [] });
      before.addControl(overlay);
      try {
        const list = await Promise.all(
          (compareKind==="sentinel1"||compareKind==="alos2"?[compareKind as Product]:visibleProducts.filter(p=>layers[p]>0))
            .map(async (p) => {
              const meta = await loadMeta(
                path,
                p,
                current.dates[compareDate],
                controller.signal,
              );
              return new BitmapLayer({
                id: "before-" + p,
                image: rasterURL(path, p, current.dates[compareDate]),
                bounds: meta.bounds,
                opacity:compareKind==="sentinel1"||compareKind==="alos2"?.85:layers[p],
              });
            }),
        );
        if (!controller.signal.aborted) overlay.setProps({ layers: list });
      } catch (e) {
        if (!controller.signal.aborted) setFailure(String(e));
      }
    });
    return () => {
      controller.abort();
      primary.off("move", sync);
      before.remove();
    };
  }, [compare, compareDate, compareKind, current, layers, ready,path,visibleProducts]);
  const active = visibleProducts.find((p) => layers[p] > 0 || compare&&["sentinel1","alos2"].includes(compareKind)&&p==="gcov"),
    meta = active ? metadata[active] : undefined;
  let sampled: number | null = null;
  if (hover && meta?.sampleGrid) {
    const [w, s, e, n] = meta.bounds;
    const grid = meta.sampleGrid;
    const x = Math.floor(((hover.lng - w) / (e - w)) * grid.width),
      y = Math.floor(((n - hover.lat) / (n - s)) * grid.height);
    if (x >= 0 && y >= 0 && x < grid.width && y < grid.height)
      sampled = grid.values[y * grid.width + x];
  }
  return (
    <>
      <div
        ref={container}
        className={"map-canvas " + (intro ? "is-intro" : "")}
        aria-label={t("Interactive Earth surface map")}
      />
      {compare && (
        <div
          className="comparison-canvas"
          style={{ clipPath: "inset(0 " + (100 - swipe) + "% 0 0)" }}
        >
          <div ref={compareContainer} />
        </div>
      )}
      {(!ready || loading) && (
        <div className="map-loading">
          <span className="radar-loader" />
          {t(!ready ? "Connecting to Earth" : "Loading acquisition")}
        </div>
      )}
      {failure && (
        <button className="map-warning" onClick={() => setFailure("")}>
          {failure} ×
        </button>
      )}
      {!intro && (
        <>
          <div className="map-tools">
            <button
              aria-label={t("Zoom in")}
              onClick={() => mapRef.current?.zoomIn()}
            >
              <Plus size={18} />
            </button>
            <button
              aria-label={t("Zoom out")}
              onClick={() => mapRef.current?.zoomOut()}
            >
              <Minus size={18} />
            </button>
            <button
              aria-label={t("Recenter case")}
              onClick={() =>
                mapRef.current?.flyTo({
                  center: [current.center[1], current.center[0]],
                  zoom: current.zoom,
                })
              }
            >
              <LocateFixed size={18} />
            </button>
            <button
              aria-label={t("Toggle illustrative 3D classification")}
              aria-pressed={extruded}
              className={extruded ? "active" : ""}
              onClick={() =>
                set({
                  extruded: !extruded,
                  layers: { ...layers, classification: extruded ? 0 : 0.7 },
                })
              }
            >
              <Mountain size={18} />
            </button>
          </div>
          <div className="coordinates">
            <Crosshair size={12} />
            {(hover?.lat ?? current.center[0]).toFixed(4)}° &nbsp;{" "}
            {(hover?.lng ?? current.center[1]).toFixed(4)}°{" "}
            <span>
              {sampled !== null
                ? sampled.toFixed(2) +
                  " " +
                  meta?.unit +
                  " · " +
                  classLabel(current.predictedClass,locale)
                : isMock
                  ? t("SIMULATED FIELD")
                  : t("RASTER VIEW")}
            </span>
          </div>
          {meta && active && (
            <div className="map-legend glass">
              <small>
                {layerDefinitions.find(l=>l.id===active)?.label[locale]} · {meta.unit}
              </small>
              <div
                style={{
                  background:
                    "linear-gradient(90deg," + meta.colormap.join(",") + ")",
                }}
              />
              <span>
                {meta.min}
                <em>{meta.unit === "dB" ? "0" : t("RANGE")}</em>
                {meta.max} {meta.unit}
              </span>
              {active==="gcov"&&<div className="legend-thresholds"><i style={{left:((-3-meta.min)/(meta.max-meta.min)*100)+"%"}}>-3</i><i style={{left:((3-meta.min)/(meta.max-meta.min)*100)+"%"}}>+3</i><small>{t("Change threshold")} ±3 dB</small></div>}
              {active==="goff"&&<small>{t(current.phenomenon==="tailingsInstability"?"Mock dam threshold":"Large offsets")} · {current.phenomenon==="tailingsInstability"?"0.10 m":"1 m"}</small>}
            </div>
          )}
          {layers.ps_insar>0&&ps&&<div className="ps-legend glass">PS-InSAR · mm/{locale==="fr"?"an":"yr"}<span><i style={{background:"#4696ff"}}/> −250 <i style={{background:"#ff5f7d"}}/> +100</span></div>}
          {pin && (
            <div className="pin-card glass">
              <button
                className="close-small"
                aria-label={t("Close location")}
                onClick={() => setPin(null)}
              >
                ×
              </button>
              <small>{t("LOCATION INSPECTOR")}</small>
              <strong>
                {pin.lat.toFixed(4)}, {pin.lng.toFixed(4)}
              </strong>
              <svg viewBox="0 0 220 42">
                <polyline
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="2"
                  points={series
                    .map(
                      (s, i) =>
                        i * 30 + "," + (30 - Math.abs(s.backscatter_db) * 2),
                    )
                    .join(" ")}
                />
              </svg>
              <p>
                {t(isMock ? "Case-level simulated series. No pixel-level measurement." : "Case-level series; pixel sampling unavailable.")}
              </p>
            </div>
          )}
        </>
      )}
    </>
  );
}
