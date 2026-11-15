import { useQueries, useQuery } from "@tanstack/react-query";
import { useApi } from "./ApiProvider";

/** One hook per read endpoint. Every value they return has passed the zod contract. */

export function useHealth() {
  const api = useApi();
  return useQuery({ queryKey: ["health"], queryFn: ({ signal }) => api.health(signal), staleTime: 15_000 });
}

export function useCases() {
  const api = useApi();
  return useQuery({ queryKey: ["cases"], queryFn: ({ signal }) => api.cases(signal) });
}

export function useCaseStudy(id: string) {
  const api = useApi();
  return useQuery({ queryKey: ["case", id], queryFn: ({ signal }) => api.caseStudy(id, signal) });
}

/** Only the reservoir case requests these optional RGBA images. */
export function useWaterRasterIndex(enabled: boolean) {
  const api = useApi();
  return useQuery({ queryKey: ["water-raster-index"], queryFn: ({ signal }) => api.waterRasterIndex(signal), enabled });
}

/** Several cases at once, sharing the cache of useCaseStudy. */
export function useCaseStudies(ids: string[]) {
  const api = useApi();
  return useQueries({
    queries: ids.map((id) => ({ queryKey: ["case", id], queryFn: ({ signal }: { signal: AbortSignal }) => api.caseStudy(id, signal) })),
  });
}

export function useAnswer(id: string) {
  const api = useApi();
  return useQuery({ queryKey: ["answer", id], queryFn: ({ signal }) => api.answer(id, signal) });
}

/** Several answers at once (a case's linked answers), sharing the cache of useAnswer. */
export function useAnswers(ids: string[]) {
  const api = useApi();
  return useQueries({
    queries: ids.map((id) => ({ queryKey: ["answer", id], queryFn: ({ signal }: { signal: AbortSignal }) => api.answer(id, signal) })),
  });
}

export function useLibrary() {
  const api = useApi();
  return useQuery({ queryKey: ["library"], queryFn: ({ signal }) => api.library(signal) });
}

export function useDiscoveries(region: string) {
  const api = useApi();
  return useQuery({ queryKey: ["discoveries", region], queryFn: ({ signal }) => api.discoveries(region, signal) });
}

export function useLbandProof() {
  const api = useApi();
  return useQuery({ queryKey: ["lband-proof"], queryFn: ({ signal }) => api.lbandProof(signal) });
}

export function useWatches() {
  const api = useApi();
  return useQuery({ queryKey: ["watches"], queryFn: ({ signal }) => api.watches(signal) });
}

export function useNotifications() {
  const api = useApi();
  return useQuery({ queryKey: ["notifications"], queryFn: ({ signal }) => api.notifications(signal) });
}
