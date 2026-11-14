import { RotateCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useText } from "@/i18n/useText";

/** Replaces React Router's default error screen with a translated, actionable one. */
export default function RouteError() {
  const { t } = useText();
  return (
    <div className="mx-auto flex max-w-lg flex-col items-start gap-3 px-4 py-16" role="alert">
      <TriangleAlert className="size-6 text-fail" aria-hidden />
      <h1 className="text-xl font-semibold">{t("errors.screen")}</h1>
      <p className="text-ink-2">{t("errors.screenHint")}</p>
      <Button onClick={() => window.location.reload()}>
        <RotateCw aria-hidden />
        {t("common.reload")}
      </Button>
    </div>
  );
}
