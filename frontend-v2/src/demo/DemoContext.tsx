import { createContext, useContext } from "react";

/** Set in an offline build: "demo" (no draft allowed) or "rehearsal" (drafts kept, never for the jury). */
export interface DemoInfo {
  kind: "demo" | "rehearsal";
  /** When the snapshot of the live backend was taken (ISO). */
  generatedAt: string;
}

export const DemoContext = createContext<DemoInfo | null>(null);

export function useDemo(): DemoInfo | null {
  return useContext(DemoContext);
}
