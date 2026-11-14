import type { ApiClient } from "./client";
import { createHttpClient } from "./http";

export type ApiMode = "http" | "fixtures";

/** VITE_API_MODE=fixtures serves synthetic data; anything else talks to the FastAPI backend. */
export const API_MODE: ApiMode = import.meta.env.VITE_API_MODE === "fixtures" ? "fixtures" : "http";

let clientPromise: Promise<ApiClient> | null = null;

export function getClient(): Promise<ApiClient> {
  if (!clientPromise) {
    clientPromise =
      import.meta.env.VITE_API_MODE === "fixtures"
        ? import("./fixtures").then((m) => m.createFixtureClient())
        : Promise.resolve(createHttpClient());
  }
  return clientPromise;
}

export * from "./client";
