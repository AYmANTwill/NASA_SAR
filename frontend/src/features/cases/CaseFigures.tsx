import { useState } from "react";
import { ImageOff, Maximize2, X } from "lucide-react";
import type { CaseStudy } from "@/api/contract";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useText } from "@/i18n/useText";
import { cn } from "@/lib/utils";
import { localized } from "./CasesPage";

type Figure = CaseStudy["figures"][number];

/**
 * Image and chart figures of a case (before / after, validation, clouds vs radar...).
 * Each one is shown whole (never cropped), with its title and caption, and opens full screen.
 */
export function CaseFigures({ figures }: { figures: Figure[] }) {
  const { t } = useText();
  if (!figures.length) return null;
  return (
    <section aria-labelledby="case-figures" className="space-y-3">
      <h2 id="case-figures" className="font-semibold">{t("cases.figures")}</h2>
      <ul className={cn("grid gap-4", figures.length > 1 && "md:grid-cols-2")}>
        {figures.map((f) => (
          <li key={f.id}>
            <FigureCard f={f} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function FigureCard({ f }: { f: Figure }) {
  const { t, lang, text } = useText();
  const [broken, setBroken] = useState(false);
  const title = localized(f.title, lang);
  const caption = text(f.caption);
  return (
    <figure className="flex h-full flex-col gap-2 rounded-md border border-line bg-surface p-3">
      <p className="font-medium text-pretty">{title}</p>
      {broken ? (
        <p className="flex min-h-40 items-center justify-center gap-2 rounded-sm border border-dashed border-line-strong bg-surface-2 p-4 text-sm text-ink-2">
          <ImageOff className="size-4" aria-hidden />
          {t("cases.imageMissing")}
        </p>
      ) : (
        <Dialog>
          <DialogTrigger asChild>
            <button
              type="button"
              className="group relative block w-full cursor-zoom-in overflow-hidden rounded-sm bg-surface-2"
              aria-label={t("cases.enlarge", { title })}
            >
              <img src={f.url} alt={title} loading="lazy" decoding="async" onError={() => setBroken(true)} className="mx-auto max-h-[26rem] w-full object-contain" />
              <span aria-hidden className="absolute end-2 top-2 inline-flex items-center rounded-sm bg-ink/75 p-1.5 text-white opacity-80 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                <Maximize2 className="size-4" />
              </span>
            </button>
          </DialogTrigger>
          <DialogContent
            showCloseButton={false}
            className="flex max-h-[96dvh] w-[min(96vw,1600px)] max-w-none flex-col gap-3 border-line bg-surface p-3 sm:max-w-none sm:p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <DialogTitle className="text-base font-semibold text-pretty">{title}</DialogTitle>
              <DialogClose className="inline-flex shrink-0 items-center gap-1 rounded-sm border border-line px-2 py-1 text-sm text-ink-2 hover:text-ink">
                <X className="size-4" aria-hidden />
                {t("common.close")}
              </DialogClose>
            </div>
            <div className="min-h-0 flex-1 overflow-auto rounded-sm bg-surface-2">
              <img src={f.url} alt={title} className="mx-auto h-auto max-h-[78dvh] w-full object-contain" />
            </div>
            <DialogDescription className="max-w-prose text-sm leading-relaxed text-pretty text-ink-2">{caption}</DialogDescription>
          </DialogContent>
        </Dialog>
      )}
      <figcaption className="text-sm leading-relaxed text-pretty text-ink-2">{caption}</figcaption>
    </figure>
  );
}
