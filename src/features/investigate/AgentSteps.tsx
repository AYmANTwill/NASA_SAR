import { useEffect, useState } from "react";
import { Check, ChevronDown, Loader2, Minus, X, Circle } from "lucide-react";
import type { AgentStep } from "@/api/contract";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useText } from "@/i18n/useText";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const ICON = { pending: Circle, running: Loader2, done: Check, failed: X, skipped: Minus } as const;

/** While the agent runs, every step is shown as it arrives; once done, the list folds into one summary line. */
export function AgentSteps({ steps, live }: { steps: AgentStep[]; live: boolean }) {
  const { t, lang } = useText();
  const [open, setOpen] = useState(live);
  useEffect(() => setOpen(live), [live]);
  const total = steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const failed = steps.some((s) => s.status === "failed");

  return (
    <section aria-labelledby="steps-title" className="space-y-2">
      <h2 id="steps-title" className="text-sm font-semibold text-ink-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls="steps-list"
          disabled={live}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex w-full items-center gap-2 rounded-sm text-start disabled:cursor-default"
        >
          {!live && (failed ? <X className="size-4 text-fail" aria-hidden /> : <Check className="size-4 text-accent" aria-hidden />)}
          <span>{t("steps.title")}</span>
          {!live && (
            <span className="font-normal text-muted">
              {t("steps.summary", { count: steps.length, seconds: formatNumber(total / 1000, lang, 1) })}
            </span>
          )}
          {!live && <ChevronDown className={cn("ms-auto size-4 transition-transform", open && "rotate-180")} aria-hidden />}
        </button>
      </h2>
      <ol id="steps-list" hidden={!open} className="relative space-y-1" aria-live={live ? "polite" : undefined} aria-relevant="additions text">
        {steps.map((s, i) => (
          <StepItem key={s.id} step={s} last={i === steps.length - 1} />
        ))}
      </ol>
    </section>
  );
}

function StepItem({ step, last }: { step: AgentStep; last: boolean }) {
  const { t, text, lang } = useText();
  const Icon = ICON[step.status];
  const params = Object.entries(step.params);
  return (
    <li className="relative flex gap-3 ps-0">
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "z-10 grid size-6 shrink-0 place-items-center rounded-full border",
            step.status === "done" && "border-accent bg-accent text-white",
            step.status === "running" && "border-accent bg-surface text-accent",
            step.status === "failed" && "border-fail bg-fail text-white",
            (step.status === "pending" || step.status === "skipped") && "border-line-strong bg-surface text-muted",
          )}
        >
          <Icon className={cn("size-3.5", step.status === "running" && "animate-spin")} aria-hidden />
        </span>
        {!last && <span aria-hidden className="w-px flex-1 bg-line-strong" />}
      </div>
      <div className="min-w-0 flex-1 pb-3">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-medium">{t(`steps.kind.${step.kind}`)}</span>
          <code dir="ltr" className="font-mono text-xs text-muted">{step.tool}</code>
          <span className="ms-auto text-xs text-ink-2">
            <span className="sr-only">{t(`steps.status.${step.status}`)}</span>
            {step.duration_ms != null ? (
              <bdi className="num">{t("steps.seconds", { value: formatNumber(step.duration_ms / 1000, lang, 2) })}</bdi>
            ) : (
              <span aria-hidden>{t(`steps.status.${step.status}`)}</span>
            )}
          </span>
        </div>
        {step.summary && <p className="text-sm text-ink-2">{text(step.summary)}</p>}
        {step.error && <p className="text-sm text-fail">{text(step.error)}</p>}
        {params.length > 0 && (
          <Collapsible>
            <CollapsibleTrigger className="group mt-0.5 inline-flex items-center gap-1 rounded-sm text-xs text-muted hover:text-ink">
              {t("steps.params")}
              <ChevronDown className="size-3 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <dl dir="ltr" className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 rounded-sm bg-surface-2 px-2 py-1.5 font-mono text-xs">
                {params.map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-muted">{k}</dt>
                    <dd className="break-all text-ink">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </li>
  );
}
