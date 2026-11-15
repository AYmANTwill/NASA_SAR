import { Link } from "react-router-dom";
import { useCreateWatch } from "@/api/mutations";
import { ErrorPanel } from "@/components/ErrorPanel";
import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";

/** Keeps watching an answer's place at every NISAR pass (POST /api/watches). */
export function WatchButton({ answerId }: { answerId: string }) {
  const { t, lang } = useText();
  const create = useCreateWatch();

  if (create.isSuccess) {
    return (
      <p className="watch-created" role="status">
        {t("watch.created", { date: formatDate(create.data.next_pass, lang) })} <Link to={`/${lang}/watches`}>{t("watch.seeWatches")}</Link>
      </p>
    );
  }
  return (
    <>
      <button type="button" className="button" onClick={() => create.mutate(answerId)} disabled={create.isPending}>
        {t("watch.create")}
      </button>
      {create.isError && <ErrorPanel error={create.error} />}
    </>
  );
}
