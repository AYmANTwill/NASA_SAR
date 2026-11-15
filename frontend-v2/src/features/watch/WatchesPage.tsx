import { useId, useState } from "react";
import { Link } from "react-router-dom";
import type { Watch, WatchLevel, WatchNotification } from "@/api/contract";
import { useCheckWatches, useDeleteWatch, useSimulateAlert } from "@/api/mutations";
import { useNotifications, useWatches } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { ErrorPanel } from "@/components/ErrorPanel";
import { QueryView } from "@/components/QueryView";
import { LevelMark } from "@/components/science/LevelMark";
import { formatDate, formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import "@/features/cases/CasesPage.css";
import "@/features/investigate/investigate.css";
import "@/features/status/StatusPage.css";
import "./WatchesPage.css";
import { OrbitClock } from "./OrbitClock";

const LEVELS: WatchLevel[] = ["yellow", "orange", "red"];

export function WatchesPage() {
  const { t, lang } = useText();
  useDocumentTitle(t("nav.watches"));
  const watches = useWatches();
  const notifications = useNotifications();
  const check = useCheckWatches();

  return (
    <section className="page">
      <header className="cases-intro">
        <h1>{t("nav.watches")}</h1>
        <p className="page-lede">{t("watch.lede")}</p>
      </header>

      <section className="status-block" aria-labelledby="watches-title">
        <div className="watch-toolbar">
          <h2 id="watches-title">{t("watch.listTitle")}</h2>
          <button type="button" className="button" onClick={() => check.mutate()} disabled={check.isPending}>
            {check.isPending ? t("watch.checking") : t("watch.checkNow")}
          </button>
        </div>
        {check.isError && <ErrorPanel error={check.error} />}
        <QueryView query={watches}>
          {(list) =>
            list.length === 0 ? (
              <p className="not-measured">
                {t("watch.empty")} <Link to={`/${lang}/ask`}>{t("watch.emptyAction")}</Link>
              </p>
            ) : (
              <ul className="watch-list">
                {list.map((w) => (
                  <li key={w.id}>
                    <WatchCard watch={w} />
                  </li>
                ))}
              </ul>
            )
          }
        </QueryView>
      </section>

      <section className="status-block" aria-labelledby="notes-title">
        <h2 id="notes-title">{t("watch.notifications")}</h2>
        <QueryView query={notifications}>
          {(notes) =>
            notes.length === 0 ? (
              <p className="not-measured">{t("watch.notificationsNone")}</p>
            ) : (
              <ol className="note-list">
                {[...notes].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((n) => (
                  <li key={n.id}>
                    <NotificationRow note={n} />
                  </li>
                ))}
              </ol>
            )
          }
        </QueryView>
      </section>
    </section>
  );
}

function WatchCard({ watch }: { watch: Watch }) {
  const { t, lang } = useText();
  const remove = useDeleteWatch();
  const simulate = useSimulateAlert();
  const [level, setLevel] = useState<WatchLevel>("orange");
  const [confirming, setConfirming] = useState(false);
  const selectId = useId();
  const place = watch.location.name_i18n?.[lang] ?? watch.location.name ?? "";

  return (
    <article className="watch-card" aria-labelledby={`watch-${watch.id}`}>
      <div className="watch-card-header"><OrbitClock last={watch.last_pass} next={watch.next_pass} /><h3 id={`watch-${watch.id}`}>{place || t("answer.thePoint")}</h3></div>
      <p dir="auto">
        <q>{watch.question}</q>
      </p>
      <dl className="legend-facts">
        <dt>{t("watch.level")}</dt>
        <dd>
          <LevelMark level={watch.level} />
        </dd>
        {watch.confidence && (
          <>
            <dt>{t("watch.confidence")}</dt>
            <dd>{t(`confidenceLevel.${watch.confidence}`)}</dd>
          </>
        )}
        <dt>{t("watch.lastPass")}</dt>
        <dd>{watch.last_pass ? formatDate(watch.last_pass, lang) : t("answer.none")}</dd>
        <dt>{t("watch.nextPass")}</dt>
        <dd>{formatDate(watch.next_pass, lang)}</dd>
        {watch.track && (
          <>
            <dt>{t("answer.tracks")}</dt>
            <dd>{t("answer.track", { number: formatNumber(watch.track.number, lang), direction: t(`direction.${watch.track.direction}`) })}</dd>
          </>
        )}
      </dl>
      <p className="watch-actions">
        {watch.answer_id && <Link to={`/${lang}/answers/${encodeURIComponent(watch.answer_id)}`}>{t("watch.openAnswer")}</Link>}
        {!confirming && <button type="button" className="link-button" onClick={() => setConfirming(true)} disabled={remove.isPending}>
          {t("watch.delete")}
        </button>}
      </p>
      {confirming && <div className="watch-confirm"><p>{t("parity.confirmDelete")}</p><button type="button" className="button" disabled={remove.isPending} onClick={() => remove.mutate(watch.id)}>{t("watch.delete")}</button><button type="button" className="button" onClick={() => setConfirming(false)}>{t("parity.cancel")}</button></div>}
      {remove.isError && <ErrorPanel error={remove.error} />}

      <details className="watch-demo">
        <summary>{t("watch.demoTitle")}</summary>
        <p className="measure-note">{t("watch.demoNote")}</p>
        <p className="watch-demo-row">
          <label htmlFor={selectId}>{t("watch.demoLevel")}</label>
          <select id={selectId} value={level} onChange={(e) => setLevel(e.target.value as WatchLevel)}>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {t(`level.${l}`)}
              </option>
            ))}
          </select>
          <button type="button" className="button" onClick={() => simulate.mutate({ watchId: watch.id, level })} disabled={simulate.isPending}>
            {t("watch.demoRun")}
          </button>
        </p>
        {simulate.isError && <ErrorPanel error={simulate.error} />}
      </details>
    </article>
  );
}

function NotificationRow({ note }: { note: WatchNotification }) {
  const { t, lang, text } = useText();
  return (
    <article className="note">
      <p className="note-head">
        <LevelMark level={note.level} />
        {note.previous_level && (
          <span className="measure-note">
            {t("watch.previously")} {t(`level.${note.previous_level}`)}
          </span>
        )}
        <time dateTime={note.created_at} className="measure-note">
          {formatDate(note.created_at, lang)}
        </time>
      </p>
      <p>{text(note.message)}</p>
      {note.answer_id && <Link to={`/${lang}/answers/${encodeURIComponent(note.answer_id)}`}>{t("watch.openAnswer")}</Link>}
    </article>
  );
}
