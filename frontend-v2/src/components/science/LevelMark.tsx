import type { WatchLevel } from "@/api/contract";
import { useText } from "@/i18n/useText";
import "./science.css";

/**
 * A watch level exactly as the API gives it: a word, a shape and the level's
 * colour (never the colour alone). No level is "no level yet", not green.
 */
export function LevelMark({ level }: { level: WatchLevel | null }) {
  const { t } = useText();
  if (level === null) return <span className="level level-none">{t("level.none")}</span>;
  return (
    <span className={`level level-${level}`}>
      <svg className="level-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        {level === "yellow" && <circle cx="8" cy="8" r="6" />}
        {level === "orange" && <path d="M8 1.5 14.5 14h-13z" />}
        {level === "red" && <path d="M5 1.5h6L14.5 5v6L11 14.5H5L1.5 11V5z" />}
      </svg>
      {t("level.label", { level: t(`level.${level}`) })}
    </span>
  );
}
