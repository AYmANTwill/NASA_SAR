import type { AskRequest } from "./contract";

const PREFIX = "nisar-v2-response:";
const MAX_AGE = 7 * 24 * 60 * 60 * 1000;
export function browserStorage(): Storage | null { try { return typeof localStorage === "undefined" ? null : localStorage; } catch { return null; } }
export function cacheRead(storage: Storage | null, key: string): unknown {
  try {
    const raw = storage?.getItem(PREFIX + key);
    if (!raw) return undefined;
    const entry = JSON.parse(raw) as { savedAt: number; body: unknown };
    return Number.isFinite(entry.savedAt) && Date.now() - entry.savedAt < MAX_AGE ? entry.body : undefined;
  } catch { return undefined; }
}
export function cacheWrite(storage: Storage | null, key: string, body: unknown): void {
  try { storage?.setItem(PREFIX + key, JSON.stringify({ savedAt: Date.now(), body })); } catch { /* Storage is optional. */ }
}
export function cacheRemove(storage: Storage | null, key: string): void { try { storage?.removeItem(PREFIX + key); } catch { /* Storage is optional. */ } }
export function questionKey(request: AskRequest): string {
  const normalized = request.question.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  return JSON.stringify([normalized, request.lang, request.location?.lat ?? null, request.location?.lon ?? null]);
}
export function announceCached(): void { if (typeof window !== "undefined") window.dispatchEvent(new Event("nisar-cache-fallback")); }
