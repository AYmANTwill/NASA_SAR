import { useId, useState } from "react";
import { ChevronDown, Layers } from "lucide-react";
import type { RasterLayer } from "@/api/contract";
import { Slider } from "@/components/ui/slider";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/lib/format";
import { gradient, isDiverging } from "./palettes";

export interface LayerState {
  visible: boolean;
  opacity: number;
}

interface LegendProps {
  layers: RasterLayer[];
  state: Record<string, LayerState>;
  onChange: (id: string, next: Partial<LayerState>) => void;
  earthquakes: { visible: boolean; onToggle: () => void } | null;
}

export function Legend({ layers, state, onChange, earthquakes }: LegendProps) {
  const { t, lang, unit } = useText();
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.matchMedia("(min-width: 768px)").matches);
  const panelId = useId();

  return (
    <section aria-label={t("layer.title")} className="absolute bottom-8 end-2 z-10 w-[min(18.5rem,calc(100%-1rem))] rounded-md border border-line-strong bg-surface/95 text-sm shadow-md backdrop-blur-sm">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 font-medium"
      >
        <Layers className="size-4 text-muted" aria-hidden />
        <span className="flex-1 text-start">{t("layer.title")}</span>
        <ChevronDown className={"size-4 transition-transform " + (open ? "rotate-180" : "")} aria-hidden />
      </button>
      <div id={panelId} hidden={!open} className="max-h-[50vh] space-y-4 overflow-y-auto border-t border-line px-3 pb-3 pt-3">
        {layers.map((layer) => {
          const st = state[layer.id] ?? { visible: true, opacity: 0.85 };
          const name = t(`layer.kind.${layer.kind}`);
          const u = unit(layer.unit) || t(`unitName.${layer.unit}`, { defaultValue: "" });
          const checkboxId = `${panelId}-${layer.id}`;
          return (
            <div key={layer.id} className="space-y-1.5">
              <div className="flex items-center gap-2">
                <input
                  id={checkboxId}
                  type="checkbox"
                  checked={st.visible}
                  onChange={(e) => onChange(layer.id, { visible: e.target.checked })}
                  className="size-4 accent-[var(--accent)]"
                />
                <label htmlFor={checkboxId} className="flex-1 font-medium">
                  {name} <span className="font-normal text-muted">({u})</span>
                </label>
              </div>
              <div dir="ltr" aria-hidden className="space-y-0.5">
                <div className="h-2.5 rounded-sm ring-1 ring-black/10" style={{ background: gradient(layer.palette) }} />
                <div className="num flex justify-between text-xs text-ink-2">
                  <span>{formatNumber(layer.min, lang)}</span>
                  {isDiverging(layer.palette) && <span>{formatNumber(0, lang)}</span>}
                  <span>{formatNumber(layer.max, lang)}</span>
                </div>
              </div>
              <p className="sr-only">
                {t("common.range", { from: formatNumber(layer.min, lang), to: formatNumber(layer.max, lang) })} {u}
              </p>
              {layer.sign_convention && <p className="text-xs text-ink-2">{t(`layer.sign.${layer.sign_convention}`)}</p>}
              <p className="text-xs text-muted">
                {layer.period && t("layer.period", { start: formatDate(layer.period.start, lang, "medium"), end: formatDate(layer.period.end, lang, "medium") })}
                {layer.period && " · "}
                {t("layer.source", { source: layer.source })}
              </p>
              <Slider
                aria-label={t("layer.opacity", { layer: name })}
                value={[Math.round(st.opacity * 100)]}
                min={0}
                max={100}
                step={5}
                disabled={!st.visible}
                onValueChange={([v]) => onChange(layer.id, { opacity: v / 100 })}
                className="pt-1"
              />
            </div>
          );
        })}
        {earthquakes && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <input id={`${panelId}-eq`} type="checkbox" checked={earthquakes.visible} onChange={earthquakes.onToggle} className="size-4 accent-[var(--accent)]" />
              <label htmlFor={`${panelId}-eq`} className="flex-1 font-medium">
                {t("layer.earthquakes")}
              </label>
            </div>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="inline-block size-3.5 rounded-full border-2 border-white bg-ink ring-1 ring-ink" />
                {t("layer.mainshock")}
              </li>
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="inline-block size-2.5 rounded-full border border-ink bg-white/60" />
                {t("layer.aftershock")}
              </li>
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
