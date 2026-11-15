import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** Live backend responses saved by scripts/record-fixtures.mjs. Vitest runs from frontend-v2/. */
export const RECORDED_DIR = join(process.cwd(), "src/test/recorded");

export interface Recorded {
  path: string;
  status: number;
  body: unknown;
}

export function recorded(name: string): Recorded {
  return JSON.parse(readFileSync(join(RECORDED_DIR, name), "utf8")) as Recorded;
}

export function recordedText(name: string): string {
  return readFileSync(join(RECORDED_DIR, name), "utf8");
}

export function recordedNames(prefix: string): string[] {
  return readdirSync(RECORDED_DIR).filter((f) => f.startsWith(prefix) && f.endsWith(".json"));
}

/** A fetch that answers from recorded responses (and records what it was asked). */
export function recordedFetch(routes: Record<string, Recorded | (() => Response)>) {
  const calls: string[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push(`${init?.method ?? "GET"} ${url}`);
    const route = routes[url];
    if (!route) throw new TypeError(`network error: no route for ${url}`);
    if (typeof route === "function") return route();
    return new Response(JSON.stringify(route.body), { status: route.status, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return { fetcher, calls };
}
