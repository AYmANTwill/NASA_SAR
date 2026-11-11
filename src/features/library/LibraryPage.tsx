import { Link } from "react-router-dom";
import { CircleCheck, CircleHelp, CircleX, Library, MinusCircle } from "lucide-react";
import type { LibraryEvent } from "@/api/contract";
import { useLibrary } from "@/api/queries";
import { MeasurementText } from "@/components/science/MeasurementText";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function LibraryPage() {
  const { t } = useText();
  const query = useLibrary();
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6">
      <header className="max-w-2xl space-y-1.5">
        <h1 className="text-2xl font-semibold sm:text-3xl">{t("library.title")}</h1>
        <p className="text-ink-2">{t("library.intro")}</p>
      </header>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data?.length === 0 && (
        <EmptyState icon={<Library className="mt-0.5 size-5 shrink-0" aria-hidden />}>
          <p>{t("library.empty")}</p>
        </EmptyState>
      )}
      {!!query.data?.length && (
        <ul className="grid gap-4 md:grid-cols-2">
          {[...query.data].sort((a, b) => b.date.localeCompare(a.date)).map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </ul>
      )}
    </div>
  );
}

const AGREE_ICON = { agrees: CircleCheck, disagrees: CircleX, inconclusive: CircleHelp, unavailable: MinusCircle } as const;

function EventCard({ event }: { event: LibraryEvent }) {
  const { t, lang, text, place } = useText();
  const ref = event.reference;
  const Icon = AGREE_ICON[ref.agreement];
  const body = (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{place(event.location)}</h2>
        <time dateTime={event.date} className="text-sm text-ink-2">
          {formatDate(event.date, lang)}
        </time>
      </div>
      <p className="text-sm text-ink-2">
        {t(`library.kind.${event.kind}`)}
        {event.magnitude && <> · <bdi className="num">{t("library.magnitude", { value: formatNumber(event.magnitude.value, lang, 1), type: event.magnitude.type })}</bdi></>}
      </p>
      <div className="space-y-1.5 border-t border-line pt-3 text-sm">
        <p className="flex items-center gap-1.5">
          <Icon className={cn("size-4", ref.agreement === "agrees" ? "text-ok" : ref.agreement === "disagrees" ? "text-fail" : "text-muted")} aria-hidden />
          <span className="font-medium">{t(`source.${ref.source}`)}</span>
          <span className="text-ink-2">· {t(`agreement.${ref.agreement}`)}</span>
        </p>
        <p className="text-ink-2">{text(ref.summary)}</p>
        {ref.comparison && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 rounded-sm bg-surface-2 p-2">
            <dt className="col-span-2 text-xs text-muted">{t(`metric.${ref.comparison.metric}`)}</dt>
            <dt className="text-ink-2">{t("library.nisar")}</dt>
            <dd>
              <MeasurementText m={ref.comparison.nisar} />
            </dd>
            <dt className="text-ink-2">{t("library.ref")}</dt>
            <dd>
              <MeasurementText m={ref.comparison.reference} />
            </dd>
          </dl>
        )}
      </div>
    </>
  );
  return (
    <li className="relative space-y-2 rounded-md border border-line bg-surface p-4 focus-within:border-accent hover:border-line-strong">
      {event.answer_id ? (
        <>
          {body}
          <Link to={`/investigate/${encodeURIComponent(event.answer_id)}`} className="inline-block text-sm text-accent underline underline-offset-2">
            {t("discover.open")}
          </Link>
        </>
      ) : (
        body
      )}
    </li>
  );
}
