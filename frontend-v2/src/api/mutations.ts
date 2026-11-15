import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApi } from "./ApiProvider";
import type { WatchLevel } from "./contract";

/** Every watch action re-reads the watches and notifications from the API afterwards. */
function useRefreshWatches() {
  const queries = useQueryClient();
  return () => Promise.all([queries.invalidateQueries({ queryKey: ["watches"] }), queries.invalidateQueries({ queryKey: ["notifications"] })]);
}

export function useCreateWatch() {
  const api = useApi();
  const refresh = useRefreshWatches();
  return useMutation({ mutationFn: (answerId: string) => api.createWatch(answerId), onSuccess: refresh });
}

export function useDeleteWatch() {
  const api = useApi();
  const refresh = useRefreshWatches();
  return useMutation({ mutationFn: (watchId: string) => api.deleteWatch(watchId), onSuccess: refresh });
}

export function useCheckWatches() {
  const api = useApi();
  const refresh = useRefreshWatches();
  return useMutation({ mutationFn: () => api.checkWatches(), onSettled: refresh });
}

export function useSimulateAlert() {
  const api = useApi();
  const refresh = useRefreshWatches();
  return useMutation({ mutationFn: ({ watchId, level }: { watchId: string; level: WatchLevel }) => api.simulateAlert(watchId, level), onSuccess: refresh });
}
