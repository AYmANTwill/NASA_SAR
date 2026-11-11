import { useI18n } from "../../lib/i18n";
﻿import LayerPanel from "./LayerPanel";
import Analysis from "./Analysis";
import Timeline from "./Timeline";
import type { CaseStudy, Sample } from "../../data/types";
import { useStore } from "../../store/useStore";
import { Layers, ChartNoAxesCombined } from "lucide-react";
export default function Dashboard({
  cases,
  current,
  series,
}: {
  cases: CaseStudy[];
  current: CaseStudy;
  series: Sample[];
}) {
  const { set, sheet } = useStore();
  const {t}=useI18n();
  return (
    <main className="dashboard">
      <LayerPanel cases={cases} current={current} />
      <Analysis current={current} series={series} />
      <Timeline current={current} series={series} />
      <div className="mobile-tabs glass">
        <button
          onClick={() => set({ sheet: sheet === "layers" ? null : "layers" })}
        >
          <Layers size={16} />{t("Layers")}</button>
        <button
          onClick={() =>
            set({ sheet: sheet === "analysis" ? null : "analysis" })
          }
        >
          <ChartNoAxesCombined size={16} />{t("Analysis")}</button>
      </div>
    </main>
  );
}
