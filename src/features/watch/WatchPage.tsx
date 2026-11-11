import { useState } from "react";
import { Link } from "react-router-dom";
import { BellOff, Satellite } from "lucide-react";
import type { Watch, WatchNotification } from "@/api/contract";
import { useDeleteWatch, useNotifications, useWatches } from "@/api/queries";
import { ConfidenceBadge, LevelBadge } from "@/components/science/badges";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { useText } from "@/i18n/useText";
import { daysUntil } from "@/lib/dates";
import { formatDate, formatDateTime } from "@/lib/format";

export default function WatchPage() {
  const { t } = useText();
  const watches = useWatches();
  const notifications = useNotifications();

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-4 py-6">
      <header className="max-w-2xl space-y-1.5">
        <h1 className="text-2xl font-semibold sm:text-3xl">{t("watch.title")}</h1>
        <p className="text-ink-2">{t("watch.intro")}</p>
      </header>

      <section aria-labelledby="places" className="space-y-3">
        <h2 id="places" className="text-lg font-semibold">
          {t("watch.places")}
        </h2>
        {watches.isLoading && <Loading />}
        {watches.isError && <ErrorState error={watches.error} onRetry={() => void watches.refetch()} />}
        {watches.data?.length === 0 && (
          <EmptyState icon={<Satellite className="mt-0.5 size-5 shrink-0" aria-hidden />}>
            <p>{t("watch.empty")}</p>
          </EmptyState>
        )}
        {!!watches.data?.length && (
          <ul className="grid gap-3 md:grid-cols-2">
            {watches.data.map((w) => (
              <WatchCard key={w.id} watch={w} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="history" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="history" className="text-lg font-semibold">
            {t("watch.notifications")}
          </h2>
          <p className="text-sm text-ink-2">{t("watch.bilingual")}</p>
        </div>
        {notifications.isLoading && <Loading />}
        {notifications.isError && <ErrorState error={notifications.error} onRetry={() => void notifications.refetch()} />}
        {notifications.data?.length === 0 && (
          <EmptyState icon={<BellOff className="mt-0.5 size-5 shrink-0" aria-hidden />}>
            <p>{t("watch.notificationsEmpty")}</p>
          </EmptyState>
        )}
        {!!notifications.data?.length && (
          <ol className="space-y-3">
            {[...notifications.data].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((n) => (
              <NotificationItem key={n.id} n={n} />
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function WatchCard({ watch }: { watch: Watch }) {
  const { t, lang, place } = useText();
  const del = useDeleteWatch();
  const [confirming, setConfirming] = useState(false);
  const days = daysUntil(watch.next_pass);

  return (
    <li className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold">{place(watch.location)}</h3>
          <p dir="auto" className="text-sm text-ink-2">{watch.question}</p>
        </div>
        <LevelBadge level={watch.level} />
      </div>
      <p className="text-sm text-ink-2">{t(`level.desc.${watch.level ?? "none"}`)}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-ink-2">{t("watch.nextPass")}</dt>
        <dd>
          <span className="font-medium">{formatDate(watch.next_pass, lang)}</span>{" "}
          <span className="text-ink-2">({days < 0 ? t("watch.overdue") : days === 0 ? t("watch.today") : t("watch.inDays", { count: days })})</span>
        </dd>
        <dt className="text-ink-2">{t("watch.lastPass")}</dt>
        <dd>{watch.last_pass ? formatDate(watch.last_pass, lang) : t("common.none")}</dd>
        <dt className="text-ink-2">{t("answer.recipe")}</dt>
        <dd>{t(`recipe.${watch.recipe}`)}</dd>
        {watch.confidence && (
          <>
            <dt className="text-ink-2">{t("answer.confidence")}</dt>
            <dd>
              <ConfidenceBadge level={watch.confidence} withLabel={false} />
            </dd>
          </>
        )}
      </dl>
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        {watch.answer_id && (
          <Button asChild variant="outline" size="sm">
            <Link to={`/investigate/${encodeURIComponent(watch.answer_id)}`}>{t("watch.openAnswer")}</Link>
          </Button>
        )}
        {confirming ? (
          <>
            <Button variant="destructive" size="sm" disabled={del.isPending} onClick={() => del.mutate(watch.id)}>
              {t("watch.stopConfirm")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
              {t("watch.stopCancel")}
            </Button>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            {t("watch.stop")}
          </Button>
        )}
      </div>
      {del.isError && <ErrorState error={del.error} />}
    </li>
  );
}

function NotificationItem({ n }: { n: WatchNotification }) {
  const { t, lang } = useText();
  const fr = useText("fr");
  const ar = useText("ar");
  return (
    <li className="space-y-2 rounded-md border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <LevelBadge level={n.level} />
        {n.previous_level && <span className="text-sm text-ink-2">{t("watch.fromLevel", { level: t(`level.${n.previous_level}`) })}</span>}
        <time dateTime={n.created_at} className="ms-auto text-xs text-muted">
          {formatDateTime(n.created_at, lang)}
        </time>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <blockquote lang="fr" dir="ltr" className="rounded-sm bg-surface-2 p-3 text-sm">
          <span className="mb-1 block text-xs text-muted">{t("lang.fr")}</span>
          {fr.text(n.message)}
        </blockquote>
        <blockquote lang="ar" dir="rtl" className="rounded-sm bg-surface-2 p-3 text-sm">
          <span className="mb-1 block text-xs text-muted">{t("lang.ar")}</span>
          {ar.text(n.message)}
        </blockquote>
      </div>
      {n.answer_id && (
        <Link to={`/investigate/${encodeURIComponent(n.answer_id)}`} className="inline-block text-sm text-accent underline underline-offset-2">
          {t("watch.openAnswer")}
        </Link>
      )}
    </li>
  );
}
