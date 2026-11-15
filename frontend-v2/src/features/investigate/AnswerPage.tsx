import { Link, useParams } from "react-router-dom";
import { useAnswer } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { QueryView } from "@/components/QueryView";
import { useText } from "@/i18n/useText";
import { AnswerView } from "./AnswerView";

/** A stored answer at its own address (/:lang/answers/:id). */
export function AnswerPage() {
  const { id = "" } = useParams();
  const { t, lang } = useText();
  useDocumentTitle(t("answer.title"));
  const query = useAnswer(id);
  return (
    <div className="case-view">
      <p className="case-back">
        <Link to={`/${lang}/ask`}>{t("answer.back")}</Link>
      </p>
      <h1 className="visually-hidden">{t("answer.title")}</h1>
      <QueryView query={query}>{(answer) => <AnswerView answer={answer} />}</QueryView>
    </div>
  );
}
