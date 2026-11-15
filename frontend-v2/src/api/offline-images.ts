/** Warm a visited report's images after the first production worker takes control. */
export function saveOfflineImages(urls: string[], signal?: AbortSignal): void {
  if (!import.meta.env.PROD || typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  const worker = navigator.serviceWorker;
  const warm = () => {
    if (signal?.aborted) return;
    const local = [...new Set(urls)].filter((url) => {
      try { return new URL(url, window.location.href).origin === window.location.origin; } catch { return false; }
    });
    void Promise.allSettled(local.map((url) => fetch(url, { signal, cache: "reload" })));
  };
  void worker.ready.then(() => {
    if (worker.controller) warm();
    else worker.addEventListener("controllerchange", warm, { once: true });
  }).catch(() => {});
}
