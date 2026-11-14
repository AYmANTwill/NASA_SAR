import type { RasterLayer } from "@/api/contract";
import { formatDate, formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { paletteGradient } from "./palettes";

/**
 * The legend of the raster on the map: the canonical palette from min to max
 * with the API's min and max, the unit, the sign convention, the period and
 * the source. Like the map, the colour bar runs left to right in every language.
 * No other value is labelled (a diverging scale's centre is marked, not numbered).
 */
export function RasterLegend({ layer }: { layer: RasterLayer }) {
  const { t, lang } = useText();
  const unit = t(`unit.${layer.unit}`);
  const diverging = layer.palette === "diverging_displacement";
  const end = (v: number) => (
    <span>
      <bdi dir="ltr">{formatNumber(v, lang)}</bdi>
      {unit && ` ${unit}`}
    </span>
  );

  return (
    <figure className="legend" aria-labelledby={`legend-${layer.id}`}>
      <figcaption id={`legend-${layer.id}`} className="legend-title">
        {t(`layerKind.${layer.kind}`)}
        {unit && <span className="legend-unit"> ({unit})</span>}
      </figcaption>
      <div className="legend-scale">
        <div className="legend-bar" style={{ backgroundImage: paletteGradient(layer.palette) }} aria-hidden="true">
          {diverging && <span className="legend-centre" />}
        </div>
        <div className="legend-ends">
          {end(layer.min)}
          {end(layer.max)}
        </div>
        <p className="visually-hidden">{t("legend.range", { min: formatNumber(layer.min, lang), max: formatNumber(layer.max, lang), unit })}</p>
      </div>
      <dl className="legend-facts">
        {layer.sign_convention && (
          <>
            <dt>{t("legend.sign")}</dt>
            <dd>{t(`sign.${layer.sign_convention}`)}</dd>
          </>
        )}
        {layer.period && (
          <>
            <dt>{t("legend.period")}</dt>
            <dd>
              {formatDate(layer.period.start, lang)} → {formatDate(layer.period.end, lang)}
            </dd>
          </>
        )}
        <dt>{t("legend.source")}</dt>
        <dd dir="auto">{layer.source}</dd>
      </dl>
    </figure>
  );
}
