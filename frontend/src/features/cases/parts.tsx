import { CircleCheck, CircleDashed, CircleMinus, CircleX, FileWarning } from "lucide-react";
import type { CaseAgreement } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";

export function DraftBadge({ className }: { className?: string }) {
  const { t } = useText();
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-sm border border-[var(--level-yellow-ink)] bg-[var(--level-yellow)] px-1.5 py-0.5 text-xs font-semibold text-[var(--level-yellow-ink)]", className)}>
      <FileWarning className="size-3.5" aria-hidden />
      {t("cases.draftShort")}
    </span>
  );
}

/** A validated case: said in words with an icon, never by colour alone. */
export function FinalBadge({ className }: { className?: string }) {
  const { t } = useText();
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-sm border border-ok bg-surface px-1.5 py-0.5 text-xs font-semibold text-ok", className)}>
      <CircleCheck className="size-3.5" aria-hidden />
      {t("cases.finalShort")}
    </span>
  );
}

export function DraftBanner() {
  const { t } = useText();
  return (
    <p role="note" className="flex items-start gap-2 rounded-md border-2 border-[var(--level-yellow-ink)] bg-[var(--level-yellow)] px-4 py-3 font-semibold text-[var(--level-yellow-ink)]">
      <FileWarning className="mt-0.5 size-5 shrink-0" aria-hidden />
      {t("cases.draft")}
    </p>
  );
}

/** Agreement is never told by colour alone, and a disagreement is never green. */
const AGREEMENT = {
  agree: { icon: CircleCheck, cls: "border-ok text-ok" },
  partial: { icon: CircleDashed, cls: "border-warn text-warn" },
  disagree: { icon: CircleX, cls: "border-fail text-fail" },
  no_reference: { icon: CircleMinus, cls: "border-line-strong text-ink-2" },
} as const;

/** Neutral badge when the NISAR value is not measured yet: no agreement is shown for a placeholder. */
export function PendingAgreementBadge() {
  const { t } = useText();
  return (
    <span className="inline-flex items-center rounded-sm border border-line-strong bg-surface px-2 py-0.5 text-xs text-ink-2" title={t("cases.notMeasuredYet")}>
      <span aria-hidden>—</span>
      <span className="sr-only">{t("cases.notMeasuredYet")}</span>
    </span>
  );
}

export function AgreementBadge({ value }: { value: CaseAgreement }) {
  const { t } = useText();
  const { icon: Icon, cls } = AGREEMENT[value];
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-sm border bg-surface px-1.5 py-0.5 text-xs font-medium", cls)}>
      <Icon className="size-3.5" aria-hidden />
      {t(`cases.agreement.${value}`)}
    </span>
  );
}

/**
 * A reference can be the no-event baseline (random circles, same scene) instead of an independent measurement.
 * No contract field marks it: the source name says it (agreed convention, any of these words).
 */
const BASELINE = /baseline|ligne de base|no[- ]event|sans [ée]v[ée]nement/i;
export function isBaselineSource(source: { name: string } | null): boolean {
  return !!source && BASELINE.test(source.name);
}

/** Help under the badge when the reference is the no-event baseline: "agree" means "not different from no change". */
export function BaselineHelp() {
  const { t } = useText();
  return <p className="mt-1 max-w-56 text-xs leading-snug text-pretty text-ink-2">{t("cases.baselineHelp")}</p>;
}
