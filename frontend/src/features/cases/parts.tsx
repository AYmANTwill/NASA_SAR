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
