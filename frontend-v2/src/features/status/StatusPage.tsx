import { useDocumentTitle } from "@/app/useDocumentTitle";
import { QueryView } from "@/components/QueryView";
import { useDiscoveries, useHealth, useLbandProof } from "@/api/queries";
import { useText } from "@/i18n/useText";
import "./StatusPage.css";

/** The region the backend's discovery service covers (docs/API_CONTRACT.md: Morocco). */
const DISCOVERY_REGION = "morocco";

export function StatusPage() {
  const { t } = useText();
  useDocumentTitle(t("nav.status"));
  const health = useHealth();
  const discoveries = useDiscoveries(DISCOVERY_REGION);
  const proof = useLbandProof();

  return (
    <section className="page">
      <h1>{t("nav.status")}</h1>

      <section className="status-block" aria-labelledby="status-backend">
        <h2 id="status-backend">{t("status.backend.title")}</h2>
        <QueryView query={health}>
          {(h) => (
            <dl className="status-facts">
              <dt>{t("status.backend.state")}</dt>
              <dd>{t("status.backend.ok")}</dd>
              <dt>{t("status.backend.data")}</dt>
              <dd>{t(`status.backend.mode.${h.data}`)}</dd>
              <dt>{t("status.backend.version")}</dt>
              <dd>
                <code dir="ltr">{h.version}</code>
              </dd>
            </dl>
          )}
        </QueryView>
      </section>

      <section className="status-block" aria-labelledby="status-discoveries">
        <h2 id="status-discoveries">{t("status.discoveries")}</h2>
        <QueryView query={discoveries}>{() => <p>{t("status.discoveriesOn")}</p>}</QueryView>
      </section>

      <section className="status-block" aria-labelledby="status-proof">
        <h2 id="status-proof">{t("status.proof")}</h2>
        <QueryView query={proof}>{() => <p>{t("status.proofReady")}</p>}</QueryView>
      </section>
    </section>
  );
}
