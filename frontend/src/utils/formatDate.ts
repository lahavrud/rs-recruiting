const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
const DAYS_PER_MONTH = 30;

const rtf = new Intl.RelativeTimeFormat("he", { numeric: "auto" });

export function formatTimeAgo(iso: string): string {
  const diffMs = new Date(iso).getTime() - Date.now();
  const diffSecs = Math.round(diffMs / MS_PER_SECOND);
  const diffMins = Math.round(diffSecs / SECONDS_PER_MINUTE);
  const diffHours = Math.round(diffMins / MINUTES_PER_HOUR);
  const diffDays = Math.round(diffHours / HOURS_PER_DAY);
  if (Math.abs(diffMins) < 2) return rtf.format(diffSecs, "second");
  if (Math.abs(diffHours) < 2) return rtf.format(diffMins, "minute");
  if (Math.abs(diffDays) < 2) return rtf.format(diffHours, "hour");
  if (Math.abs(diffDays) < DAYS_PER_MONTH) return rtf.format(diffDays, "day");
  return rtf.format(Math.round(diffDays / DAYS_PER_MONTH), "month");
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateLong(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Compact day/month label for chart X-axis ticks (e.g. "5/6"). */
export function formatDateShort(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

/** Long Hebrew date for dashboard hero (e.g. "יום שני, 27 ביוני 2026"). */
export function formatTodayHebrew(): string {
  return new Date().toLocaleDateString("he-IL", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}
