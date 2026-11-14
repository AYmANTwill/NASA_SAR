import type { Measurement } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";

/** "value ± uncertainty unit"; an uncertainty of exactly 0 means "not provided" and is not printed as ± 0. Digits stay LTR inside RTL text. */
export function MeasurementText({ m, className, size = "md" }: { m: Measurement; className?: string; size?: "md" | "lg" }) {
  const { measurement } = useText();
  const f = measurement(m);
  return (
    <bdi className={cn("num whitespace-nowrap", className)}>
      <span className={cn("font-semibold text-ink", size === "lg" && "text-2xl")}>{f.value}</span>
      {m.uncertainty > 0 && <span className={cn("text-ink-2", size === "lg" ? "text-base" : "text-[0.9em]")}> ± {f.uncertainty}</span>}
      {f.unit && <span className={cn("text-ink-2", size === "lg" ? "text-base" : "text-[0.9em]")}> {f.unit}</span>}
    </bdi>
  );
}
