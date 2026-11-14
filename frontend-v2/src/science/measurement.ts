import type { CaseStatus, Lang, Measurement } from "@/api/contract";
import { formatNumber } from "@/i18n/format";

/**
 * How a measurement may be shown (PLAN.md section 4). This decides how a value
 * looks, never what it is: no number is created here.
 *
 * - "placeholder": a draft case's value with uncertainty 0. Drafts send their
 *   unmeasured values as {value: 0, uncertainty: 0} (API_REQUESTS.md #1), so the
 *   value is withheld and shown as "not measured yet", never as 0.
 * - "exact": uncertainty 0 outside a draft (an exact count, or a reference given
 *   without σ: the backend's value_only()). The value is shown with a label
 *   saying no uncertainty was given.
 * - "measured": value ± uncertainty.
 */
export type MeasurementState = "placeholder" | "exact" | "measured";

export function measurementState(m: Measurement, status: CaseStatus | null): MeasurementState {
  if (m.uncertainty === 0) return status === "draft" ? "placeholder" : "exact";
  return "measured";
}

export interface MeasurementParts {
  value: string;
  uncertainty: string | null;
  /** How many σ the uncertainty is, when it is not 1σ. */
  sigma: string | null;
}

export function measurementParts(m: Measurement, lang: Lang): MeasurementParts {
  return {
    value: formatNumber(m.value, lang),
    uncertainty: m.uncertainty === 0 ? null : formatNumber(m.uncertainty, lang),
    sigma: m.sigma === 1 ? null : formatNumber(m.sigma, lang),
  };
}
