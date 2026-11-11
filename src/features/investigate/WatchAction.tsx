import { Link } from "react-router-dom";
import { BellRing, Eye } from "lucide-react";
import type { Answer, Lang, Watch } from "@/api/contract";
import { useCreateWatch, useWatches } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/states";
import { useText } from "@/i18n/useText";
import { formatDate } from "@/lib/format";
import { daysUntil } from "@/lib/dates";

/** "Veiller sur ce lieu": creates a watch, then shows next pass and the FR + AR notification text. */
export function WatchAction({ answer }: { answer: Answer }) {
  const { t, lang } = useText();
  const watches = useWatches();
  const create = useCreateWatch();
  const watch = create.data ?? watches.data?.find((w) => w.answer_id === answer.id);

  if (!watch) {
    return (
      <div className="space-y-2">
        <Button onClick={() => create.mutate(answer.id)} disabled={create.isPending} className="w-full sm:w-auto">
          <Eye aria-hidden />
          {t("answer.watch")}
        </Button>
        {create.isError && <ErrorState error={create.error} onRetry={() => create.mutate(answer.id)} />}
      </div>
    );
  }

  const days = daysUntil(watch.next_pass);
  return (
    <section aria-labelledby="watch-created" className="space-y-3 rounded-md border border-accent bg-accent-soft/60 p-4" role="status">
      <h3 id="watch-created" className="flex items-center gap-2 font-semibold text-accent">
        <BellRing className="size-4" aria-hidden />
        {t("answer.watching")}
      </h3>
      <p>
        {t("answer.watchNext", { date: formatDate(watch.next_pass, lang) })}{" "}
        <span className="text-ink-2">({days <= 0 ? t("watch.today") : t("watch.inDays", { count: days })})</span>
      </p>
      <div className="space-y-2">
        <p className="text-xs text-ink-2">{t("answer.watchPreview")}</p>
        <div className="grid gap-2 sm:grid-cols-2">
          <NotificationPreview watch={watch} forLang="fr" />
          <NotificationPreview watch={watch} forLang="ar" />
        </div>
      </div>
      <Link to="/watch" className="inline-block text-sm text-accent underline underline-offset-2">
        {t("answer.watchOpen")}
      </Link>
    </section>
  );
}

function NotificationPreview({ watch, forLang }: { watch: Watch; forLang: Lang }) {
  const { text, t } = useText(forLang);
  const message = text({
    template: "notify.watch_created",
    params: { place: { localized: { ...(watch.location.name_i18n ?? {}), fr: watch.location.name_i18n?.fr ?? watch.location.name ?? "" } }, next_pass: { date: watch.next_pass } },
  });
  return (
    <blockquote lang={forLang} dir={forLang === "ar" ? "rtl" : "ltr"} className="rounded-sm border border-line bg-surface p-3 text-sm">
      <span className="mb-1 block text-xs text-muted">{t(`lang.${forLang}`)}</span>
      {message}
    </blockquote>
  );
}
