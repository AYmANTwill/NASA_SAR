import type { CaseStatus } from "@/api/contract";
import { useText } from "@/i18n/useText";
import "./StatusTag.css";

/** Draft or final, as the API says. A draft is hatched so it cannot be mistaken for a result. */
export function StatusTag({ status }: { status: CaseStatus }) {
  const { t } = useText();
  return <span className={`status-tag status-${status}`}>{t(`caseStatus.${status}`)}</span>;
}
