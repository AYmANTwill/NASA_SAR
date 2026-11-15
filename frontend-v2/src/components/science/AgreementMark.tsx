import type { CaseAgreement } from "@/api/contract";
import { useText } from "@/i18n/useText";
import "./science.css";

/** The agreement the API computed (2σ / 4σ rule), as a shape and words. Never a colour, never recomputed. */
export function AgreementMark({ agreement }: { agreement: CaseAgreement | "pending" }) {
  const { t } = useText();
  return (
    <span className={`agreement agreement-${agreement}`}>
      <AgreementIcon agreement={agreement} />
      <span>{t(`agreement.${agreement}`)}</span>
    </span>
  );
}

function AgreementIcon({ agreement }: { agreement: CaseAgreement | "pending" }) {
  return (
    <svg className="agreement-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {agreement === "agree" && <circle cx="8" cy="8" r="6" className="fill" />}
      {agreement === "partial" && (
        <>
          <circle cx="8" cy="8" r="6" className="line" />
          <path d="M8 2a6 6 0 0 1 0 12z" className="fill" />
        </>
      )}
      {agreement === "disagree" && (
        <>
          <circle cx="8" cy="8" r="6" className="line" />
          <path d="M3.8 12.2 12.2 3.8" className="line" />
        </>
      )}
      {(agreement === "no_reference" || agreement === "pending") && <circle cx="8" cy="8" r="6" className="line dashed" />}
    </svg>
  );
}
