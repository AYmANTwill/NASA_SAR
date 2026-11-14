import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ErrorPanel } from "./ErrorPanel";

/** Loading, error and data states of one query, the same way everywhere. */
export function QueryView<T>({ query, children }: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  const { t } = useTranslation();
  if (query.isPending) {
    return (
      <p className="loading" role="status">
        {t("common.loading")}
      </p>
    );
  }
  if (query.isError) return <ErrorPanel error={query.error} onRetry={() => void query.refetch()} />;
  return <>{children(query.data)}</>;
}
