import type { CaseStatus, Measurement } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { measurementParts, measurementState } from "@/science/measurement";
import "./science.css";

/**
 * value ± uncertainty unit, exactly as the API sent them. The numbers stay
 * left to right; the unit follows the page direction. A draft placeholder is
 * "not measured yet", never 0 (src/science/measurement.ts).
 */
export function MeasurementView({ m, status }: { m: Measurement; status: CaseStatus | null }) {
  const { t, lang } = useText();
  const state = measurementState(m, status);
  if (state === "placeholder") return <span className="not-measured">{t("measure.notMeasured")}</span>;

  const p = measurementParts(m, lang);
  const unit = t(`unit.${m.unit}`);
  return (
    <span className="measure">
      <bdi dir="ltr" className="measure-number">
        {p.value}
        {p.uncertainty !== null && (
          <>
            {" "}
            <span aria-label={t("measure.plusMinus")}>±</span> {p.uncertainty}
          </>
        )}
      </bdi>
      {unit && <span className="measure-unit"> {unit}</span>}
      {p.sigma !== null && <span className="measure-note"> {t("measure.sigmaMultiple", { k: p.sigma })}</span>}
      {state === "exact" && <span className="measure-note"> {t("measure.noSigma")}</span>}
    </span>
  );
}
