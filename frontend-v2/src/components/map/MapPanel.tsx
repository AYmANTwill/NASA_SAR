import { lazy, Suspense, useId, useState } from "react";
import type { Bounds, Localized, RasterLayer, TemplatedText } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { MapBoundary } from "./MapBoundary";
import { RasterLegend } from "./RasterLegend";
import "./MapPanel.css";

/** MapLibre is large: it loads as its own chunk, after the page text. */
const RadarMap = lazy(() => import("./RadarMap"));

export interface MapEntry {
  layer: RasterLayer;
  title?: Localized;
  caption?: TemplatedText;
}

/**
 * Map + legend + layer choice. One raster at a time (DESIGN.md: map-first,
 * one control layer at a time). With no raster, the map still shows the study
 * area, and says that no radar map exists yet.
 */
export function MapPanel({
  frame,
  point,
  entries,
  label,
  onPick,
  showArea,
  emptyText,
}: {
  frame: Bounds;
  point?: { lat: number; lon: number };
  entries: MapEntry[];
  label: string;
  onPick?: (point: { lat: number; lon: number }) => void;
  showArea?: boolean;
  /** What the side panel says when there is no raster (default: no radar map yet). */
  emptyText?: string;
}) {
  const { t, lang, text, localized } = useText();
  const [index, setIndex] = useState(0);
  const name = useId();
  const active = entries[index] ?? entries[0] ?? null;

  return (
    <div className="map-panel">
      <MapBoundary fallback={<div className="radar-map-loading">{t("map.noWebgl")}</div>}>
        <Suspense fallback={<div className="radar-map-loading">{t("common.loading")}</div>}>
          {/* key: MapLibre sets its control labels once, so the map is rebuilt in a new language. */}
          <RadarMap key={lang} frame={frame} point={point} layer={active?.layer ?? null} label={label} onPick={onPick} showArea={showArea} />
        </Suspense>
      </MapBoundary>

      <div className="map-panel-side">
        {entries.length > 1 && (
          <fieldset className="layer-choice">
            <legend>{t("map.layers")}</legend>
            {entries.map((entry, i) => (
              <label key={entry.layer.id}>
                <input type="radio" name={name} checked={i === index} onChange={() => setIndex(i)} />
                {entry.title ? localized(entry.title) : t(`layerKind.${entry.layer.kind}`)}
              </label>
            ))}
          </fieldset>
        )}
        {active ? (
          <>
            <RasterLegend layer={active.layer} />
            {(active.title || active.caption) && (
              <p className="map-caption">
                {active.title && <strong>{localized(active.title)} </strong>}
                {active.caption && text(active.caption)}
              </p>
            )}
          </>
        ) : (
          <p className="map-empty">{emptyText ?? t("map.noRaster")}</p>
        )}
      </div>
    </div>
  );
}
