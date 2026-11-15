import { useText } from "@/i18n/useText";

export function ReportTools({ data, name }: { data: unknown; name: string }) {
  const { t } = useText();
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `${name}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <div className="report-tools"><button type="button" className="button" onClick={() => window.print()}>{t("parity.print")}</button><button type="button" className="button" onClick={download}>{t("parity.download")}</button></div>;
}
