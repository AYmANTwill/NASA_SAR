import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";
import { formatNumber, reducedMotion } from "../lib/format";
export function Count({
  value,
  digits = 0,
  locale = "en",
}: {
  value: number;
  digits?: number;
  locale?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const visible = useInView(ref);
  useEffect(() => {
    if (!visible) return;
    const controls = animate(0, value, {
      duration: reducedMotion() ? 0 : 0.8,
      onUpdate: (v) => {
        if (ref.current)
          ref.current.textContent = formatNumber(v, locale, digits);
      },
    });
    return () => controls.stop();
  }, [value, digits, locale, visible]);
  return <span ref={ref}>{formatNumber(value, locale, digits)}</span>;
}
