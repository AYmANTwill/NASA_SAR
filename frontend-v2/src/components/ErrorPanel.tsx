import { ApiError, ContractError, INFORMATION_CODES, OfflineError } from "@/api/errors";
import { useText } from "@/i18n/useText";
import "./ErrorPanel.css";

const MAX_ISSUES = 8;

/**
 * Explains why data is not shown. A contract mismatch lists the fields that
 * failed: the response is rejected whole, never patched or partly shown.
 */
export function ErrorPanel({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t, text } = useText();

  if (error instanceof ApiError && INFORMATION_CODES.has(error.code)) {
    return (
      <section className="notice notice-info" role="status">
        <p>{error.body ? text(error.body) : t("errors.api.title")}</p>
      </section>
    );
  }

  let title: string;
  let body: string;
  let detail: React.ReactNode = null;

  if (error instanceof ContractError) {
    title = t("errors.contract.title");
    body = t("errors.contract.body");
    detail = (
      <details className="notice-detail" open>
        <summary>{t("errors.contract.fields", { endpoint: error.endpoint })}</summary>
        <ul lang="en" dir="ltr">
          {error.issues.slice(0, MAX_ISSUES).map((issue, i) => (
            <li key={i}>
              <code>{issue.path.join(".") || "(root)"}</code> {issue.message}
            </li>
          ))}
          {error.issues.length > MAX_ISSUES && <li>…</li>}
        </ul>
      </details>
    );
  } else if (error instanceof OfflineError) {
    title = t("errors.offline.title");
    body = t("errors.offline.body");
  } else if (error instanceof ApiError) {
    title = error.status === 404 ? t("errors.api.notFound") : t("errors.api.title");
    body = error.body ? text(error.body) : t("errors.api.noBody");
    detail = (
      <p className="notice-code" dir="ltr">
        <code>
          {error.endpoint} · {error.code}
        </code>
      </p>
    );
  } else {
    title = t("errors.unexpected.title");
    body = t("errors.unexpected.body");
  }

  return (
    <section className="notice notice-error" role="alert">
      <h2 className="notice-title">{title}</h2>
      <p>{body}</p>
      {detail}
      {onRetry && (
        <button type="button" className="button" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </section>
  );
}
