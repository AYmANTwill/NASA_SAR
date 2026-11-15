import { useRef, useState } from "react";
import type { Figure } from "@/api/contract";
import { useText } from "@/i18n/useText";

export function FigureViewer({ figure }: { figure: Figure }) {
  const { t, text, localized } = useText();
  const [broken, setBroken] = useState(false);
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const title = localized(figure.title);
  return <figure className="figure"><button className="figure-open" type="button" onClick={() => { setOpen(true); dialog.current?.showModal(); }} aria-label={t("parity.enlarge", { title })} disabled={broken}>
    {broken ? <span className="empty-panel">{t("map.imageFailed")}</span> : <img src={figure.url} alt={title} loading="lazy" onError={() => setBroken(true)} />}
    {!broken && <span className="figure-zoom" aria-hidden="true">↗</span>}</button>
    <figcaption><strong>{title}</strong> {text(figure.caption)}</figcaption>
    <dialog className="figure-dialog" ref={dialog} aria-label={title} onClose={() => setOpen(false)} onClick={(e) => { if (e.target === e.currentTarget) dialog.current?.close(); }}>
      <header><h2>{title}</h2><button className="button" type="button" onClick={() => dialog.current?.close()}>{t("parity.close")}</button></header>
      {open && <img src={figure.url} alt={title} />}<p>{text(figure.caption)}</p>
    </dialog></figure>;
}
