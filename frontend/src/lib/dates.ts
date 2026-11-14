const DAY = 86_400_000;

export function addDays(isoDate: string, days: number): string {
  return new Date(Date.parse(isoDate + "T00:00:00Z") + days * DAY).toISOString().slice(0, 10);
}

/** Whole days from `today` to `isoDate` (negative when past). */
export function daysUntil(isoDate: string, today = new Date()): number {
  const start = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.round((Date.parse(isoDate + "T00:00:00Z") - start) / DAY);
}
