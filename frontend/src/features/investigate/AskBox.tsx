import { useEffect, useId, useState } from "react";
import { MapPin, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getClient } from "@/api";
import { keys } from "@/api/queries";
import { Button } from "@/components/ui/button";
import { useText } from "@/i18n/useText";
import { formatCoord } from "@/lib/format";

interface AskBoxProps {
  initial?: string;
  location: { lat: number; lon: number } | null;
  onClearLocation: () => void;
  running: boolean;
  onAsk: (question: string) => void;
  onCancel: () => void;
  compact?: boolean;
}

export function AskBox({ initial = "", location, onClearLocation, running, onAsk, onCancel, compact }: AskBoxProps) {
  const { t, lang } = useText();
  const [question, setQuestion] = useState(initial);
  const id = useId();
  useEffect(() => setQuestion(initial), [initial]);

  // Example questions come from the backend demo bundle, never from this file.
  const demo = useQuery({ queryKey: keys.demo, queryFn: async ({ signal }) => (await getClient()).demoBundle(signal), staleTime: 30 * 60_000 });
  const examples = demo.data?.entries.map((e) => (e.questions.find((q) => q.lang === lang) ?? e.questions[0]).text) ?? [];

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (trimmed && !running) onAsk(trimmed);
  };

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        submit(question);
      }}
    >
      <label htmlFor={id} className="text-sm font-semibold">
        {t("ask.label")}
      </label>
      <div className="flex flex-col gap-2 rounded-md border border-line-strong bg-surface p-2 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/25">
        <textarea
          id={id}
          dir="auto"
          rows={compact ? 1 : 2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(question);
            }
          }}
          placeholder={t("ask.placeholder")}
          className="w-full resize-none bg-transparent px-1 text-base outline-none placeholder:text-muted"
        />
        <div className="flex flex-wrap items-center gap-2">
          {location ? (
            <span className="inline-flex items-center gap-1 rounded-sm bg-surface-2 px-2 py-0.5 text-xs text-ink-2">
              <MapPin className="size-3.5" aria-hidden />
              <bdi className="num">{t("ask.location", { lat: formatCoord(location.lat, lang), lon: formatCoord(location.lon, lang) })}</bdi>
              <button type="button" onClick={onClearLocation} className="rounded-sm p-0.5 hover:bg-line" aria-label={t("ask.clearLocation")}>
                <X className="size-3" aria-hidden />
              </button>
            </span>
          ) : (
            !compact && <span className="text-xs text-muted">{t("ask.noLocation")}</span>
          )}
          <span className="ms-auto flex gap-2">
            {running && (
              <Button type="button" variant="outline" size="sm" onClick={onCancel}>
                {t("ask.cancel")}
              </Button>
            )}
            <Button type="submit" size="sm" disabled={running || !question.trim()}>
              {t("ask.submit")}
            </Button>
          </span>
        </div>
      </div>
      {!compact && examples.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted">{t("ask.examples")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {examples.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  dir="auto"
                  disabled={running}
                  onClick={() => {
                    setQuestion(q);
                    submit(q);
                  }}
                  className="rounded-sm border border-line bg-surface px-2 py-1 text-start text-xs text-ink-2 hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
