import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useState, type ReactNode } from "react";
import { createHttpClient, type ApiClient } from "./client";
import { ApiError, ContractError } from "./errors";

const ApiContext = createContext<ApiClient | null>(null);

export function useApi(): ApiClient {
  const client = useContext(ApiContext);
  if (!client) throw new Error("useApi() outside <ApiProvider>");
  return client;
}

/** Retrying cannot fix a contract mismatch or an explicit refusal: only network failures are retried. */
function retry(failureCount: number, error: unknown): boolean {
  if (error instanceof ContractError || error instanceof ApiError) return false;
  return failureCount < 2;
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry, staleTime: 60_000, refetchOnWindowFocus: false } },
  });
}

export function ApiProvider({ client, children }: { client?: ApiClient; children: ReactNode }) {
  const [api] = useState(() => client ?? createHttpClient());
  const [queries] = useState(makeQueryClient);
  return (
    <ApiContext.Provider value={api}>
      <QueryClientProvider client={queries}>{children}</QueryClientProvider>
    </ApiContext.Provider>
  );
}
