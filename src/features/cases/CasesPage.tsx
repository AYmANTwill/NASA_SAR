import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CloudRainWind, FlaskConical, Radio } from "lucide-react";
import type { CaseKind, CaseSummary, Localized } from "@/api/contract";
import { useCases } from "@/api/queries";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { useText } from "@/i18n/useText";
import { formatDate } from "@/lib/format";
import { CaseView } from "./CaseView";
import { DraftBadge } from "./parts";

export const KIND_ICON: Record<CaseKind, typeof Radio> = { earthquake: Radio, flood: CloudRainWind, method: FlaskConical };

/** "Case studies": the first page of the app. A list, or one case when the URL names it. */
export default function CasesPage() {
  const { caseId } = useParams();
  return caseId ? <CaseView id={caseId} /> : <CaseList />;
}

function CaseList() {
  const { t } = useText();
  const query = useCases();
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6">
      <header className="max-w-2xl space-y-1.5">
        <h1 className="text-2xl font-semibold text-balance sm:text-3xl">{t("cases.title")}</h1>
        <p className="text-ink-2">{t("cases.intro")}</p>
      </header>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data?.length === 0 && (
        <EmptyState>
          <p>{t("cases.noFindings")}</p>
        </EmptyState>
      )}
      {!!query.data?.length && (
        <ol aria-label={t("cases.list")} className="grid gap-4 sm:grid-cols-2">
          {query.data.map((c) => (
            <CaseCard key={c.id} c={c} />
          ))}
        </ol>
      )}
    </div>
  );
}

export function localized(v: Localized | string, lang: keyof Localized): string {
  return typeof v === "string" ? v : v[lang] || v.fr;
}

function CaseCard({ c }: { c: CaseSummary }) {
  const { t, lang } = useText();
  const Icon = KIND_ICON[c.kind];
  return (
    <li className="case-card relative flex flex-col gap-3 rounded-md border border-line bg-surface p-5 focus-within:border-accent hover:border-line-strong">
      {c.thumbnail_url && <img src={c.thumbnail_url} alt="" className="aspect-[16/9] w-full rounded-sm object-cover" />}
      <div className="flex items-center gap-2 text-sm text-ink-2">
        <Icon className="size-4 text-accent" aria-hidden />
        <span>{t(`cases.kind.${c.kind}`)}</span>
        <span aria-hidden>·</span>
        <time dateTime={c.date}>{formatDate(c.date, lang)}</time>
        {c.status === "draft" && <DraftBadge className="ms-auto" />}
      </div>
      <h2 className="text-lg font-semibold text-balance">
        <Link to={`/cases/${encodeURIComponent(c.id)}`} className="after:absolute after:inset-0 focus-visible:outline-none">
          {localized(c.title, lang)}
        </Link>
      </h2>
      <span className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-accent">
        {t("cases.open")}
        <ArrowRight className="size-4 rtl:rotate-180" aria-hidden />
      </span>
    </li>
  );
}

export function BackToCases() {
  const { t } = useText();
  return (
    <Link to="/" className="inline-flex items-center gap-1 rounded-sm text-sm text-ink-2 hover:text-ink">
      <ArrowLeft className="size-4 rtl:rotate-180" aria-hidden />
      {t("cases.back")}
    </Link>
  );
}
