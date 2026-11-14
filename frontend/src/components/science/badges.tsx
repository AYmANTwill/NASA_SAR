import { CircleDashed, Eye, OctagonAlert, TriangleAlert } from "lucide-react";
import type { Confidence, WatchLevel } from "@/api/contract";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";

const BARS: Record<Confidence, number> = { high: 3, medium: 2, low: 1 };

/** Signal-strength glyph: the number of filled bars encodes the level, not the colour. */
function Bars({ filled }: { filled: number }) {
  return (
    <svg viewBox="0 0 14 12" className="size-3.5 shrink-0" aria-hidden>
      {[0, 1, 2].map((i) => (
        <rect key={i} x={i * 5} y={8 - i * 4} width="3.5" height={4 + i * 4} rx="0.8" fill={i < filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1" />
      ))}
    </svg>
  );
}

export function ConfidenceBadge({ level, className, withLabel = true }: { level: Confidence; className?: string; withLabel?: boolean }) {
  const { t } = useText();
  const label = t(`confidence.${level}`);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-sm font-medium",
            level === "high" && "border-accent bg-accent text-accent-ink",
            level === "medium" && "border-accent bg-accent-soft text-accent",
            level === "low" && "border-dashed border-line-strong bg-surface text-ink-2",
            className,
          )}
        >
          <Bars filled={BARS[level]} />
          {withLabel ? t("confidence.badge", { level: label }) : label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-64">{t(`confidence.desc.${level}`)}</TooltipContent>
    </Tooltip>
  );
}

const LEVEL_ICON = { yellow: Eye, orange: TriangleAlert, red: OctagonAlert } as const;

export function LevelBadge({ level, className }: { level: WatchLevel | null; className?: string }) {
  const { t } = useText();
  const Icon = level ? LEVEL_ICON[level] : CircleDashed;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-sm font-semibold",
        level === "yellow" && "bg-[var(--level-yellow)] text-[var(--level-yellow-ink)]",
        level === "orange" && "bg-[var(--level-orange)] text-[var(--level-orange-ink)]",
        level === "red" && "bg-[var(--level-red)] text-[var(--level-red-ink)]",
        !level && "border border-dashed border-line-strong text-ink-2",
        className,
      )}
    >
      <Icon className="size-4" aria-hidden />
      {t(`level.${level ?? "none"}`)}
    </span>
  );
}
