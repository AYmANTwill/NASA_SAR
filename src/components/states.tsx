import type { ReactNode } from "react";
import { CircleAlert, CloudOff, FileWarning, Loader2 } from "lucide-react";
import { ApiError, ContractError, OfflineError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useText } from "@/i18n/useText";

export function Loading({ label }: { label?: string }) {
  const { t } = useText();
  return (
    <p role="status" className="flex items-center gap-2 py-8 text-ink-2">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label ?? t("common.loading")}
    </p>
  );
}

/** Explains what went wrong in the interface's voice; never shows a fallback value. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t, text } = useText();
  let Icon = CircleAlert;
  let message = t("errors.generic");
  if (error instanceof OfflineError) {
    Icon = CloudOff;
    message = t("errors.offline");
  } else if (error instanceof ContractError) {
    Icon = FileWarning;
    message = t("errors.contract");
  } else if (error instanceof ApiError) {
    message = error.body ? text(error.body) : t("errors.api");
  }
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-line-strong bg-surface p-4">
      <Icon className="mt-0.5 size-5 shrink-0 text-fail" aria-hidden />
      <div className="space-y-2">
        <p>{message}</p>
        {error instanceof ContractError && <p className="font-mono text-xs break-all text-muted">{error.message}</p>}
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ children, icon }: { children: ReactNode; icon?: ReactNode }) {
  return <div className="flex items-start gap-3 rounded-md border border-dashed border-line-strong bg-surface p-5 text-ink-2">{icon}{children}</div>;
}
