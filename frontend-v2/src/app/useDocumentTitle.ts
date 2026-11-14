import { useEffect } from "react";

/** Sets the browser tab title; the product name always comes last. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} – NISAR Pulse` : "NISAR Pulse";
  }, [title]);
}
