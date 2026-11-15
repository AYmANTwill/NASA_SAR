import type { AgentStep } from "@/api/contract";
import { formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";

/**
 * "How I found this": the agent's steps as the stream delivers them. Status
 * is a word and a glyph; durations are the API's. Tool names stay as code,
 * left to right.
 */
export function StepList({ steps, live }: { steps: AgentStep[]; live: boolean }) {
  const { t, lang, text } = useText();
  return (
    <ol className="steps" aria-live={live ? "polite" : "off"} aria-busy={live}>
      {steps.map((step) => (
        <li key={step.id} className={`step step-${step.status}`}>
          <span className="step-glyph" aria-hidden="true" />
          <div className="step-body">
            <p className="step-head">
              <strong>{t(`stepKind.${step.kind}`)}</strong>
              <span className="step-status">{t(`stepStatus.${step.status}`)}</span>
              {step.duration_ms !== null && (
                <span className="step-duration">
                  <bdi dir="ltr">{formatNumber(step.duration_ms, lang)}</bdi> {t("steps.ms")}
                </span>
              )}
            </p>
            <p className="step-tool">
              <code dir="ltr">{step.tool}</code>
            </p>
            {step.summary && <p className="step-summary">{text(step.summary)}</p>}
            {step.error && (
              <p className="step-error">
                <span className="visually-hidden">{t("stepStatus.failed")}: </span>
                {text(step.error)}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
