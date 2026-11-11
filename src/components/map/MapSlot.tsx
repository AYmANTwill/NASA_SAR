import { lazy, Suspense } from "react";
import { MapPinOff } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useText } from "@/i18n/useText";
import type { RadarMapProps } from "./RadarMap";

const RadarMap = lazy(() => import("./RadarMap"));

function MapUnavailable() {
  const { t } = useText();
  return (
    <div role="note" className="absolute inset-0 grid place-items-center bg-[#d9e3e9] p-6 text-center text-sm text-ink-2">
      <span className="flex max-w-xs flex-col items-center gap-2">
        <MapPinOff className="size-5" aria-hidden />
        {t("map.unavailable")}
      </span>
    </div>
  );
}

/** Lazy map with a placeholder while loading and an explicit message if it cannot load. */
export function MapSlot(props: RadarMapProps) {
  return (
    <ErrorBoundary fallback={<MapUnavailable />}>
      <Suspense fallback={<div className="absolute inset-0 bg-[#d9e3e9]" />}>
        <RadarMap {...props} />
      </Suspense>
    </ErrorBoundary>
  );
}
