import { test } from "@playwright/test";

const BACKEND = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

/** Live tests need the real backend; without it they are skipped with the reason, never faked. */
export async function requireBackend(): Promise<void> {
  let up = false;
  try {
    up = (await fetch(`${BACKEND}/api/health`, { signal: AbortSignal.timeout(3000) })).ok;
  } catch {
    up = false;
  }
  test.skip(!up, `backend not running on ${BACKEND} (start it: see frontend-v2/README.md)`);
}

export const LANGS = ["fr", "en", "ar"] as const;
