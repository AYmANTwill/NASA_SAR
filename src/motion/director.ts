import { prefersReducedMotion } from "./motion";

/**
 * Paces a stream of updates so a viewer can follow the agent's reasoning:
 * updates that arrive faster than `gapMs` (a precomputed answer, a cached
 * replay) are queued and released one by one; slower ones pass straight
 * through. Values are never altered, only their display is spaced in time.
 * With reduced motion, everything passes through immediately.
 */
export function createPacer<T>(emit: (value: T) => void, gapMs: number, signal?: AbortSignal) {
  const reduced = prefersReducedMotion();
  const queue: T[] = [];
  let last = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let idle: (() => void) | null = null;
  signal?.addEventListener("abort", () => {
    if (timer) clearTimeout(timer);
    idle?.();
  });

  const pump = () => {
    timer = null;
    if (signal?.aborted) return;
    const value = queue.shift();
    if (value === undefined) {
      idle?.();
      idle = null;
      return;
    }
    emit(value);
    last = performance.now();
    if (queue.length) timer = setTimeout(pump, gapMs);
    else {
      idle?.();
      idle = null;
    }
  };

  return {
    push(value: T) {
      if (reduced) return emit(value);
      queue.push(value);
      if (timer) return;
      const wait = Math.max(0, last + gapMs - performance.now());
      timer = setTimeout(pump, wait);
    },
    /** Resolves once every queued update has been shown. */
    drained(): Promise<void> {
      if (reduced || (!queue.length && !timer)) return Promise.resolve();
      return new Promise((resolve) => {
        idle = resolve;
      });
    },
  };
}
