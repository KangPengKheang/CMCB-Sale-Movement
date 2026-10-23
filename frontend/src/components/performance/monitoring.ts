import type { ActivitySender, SalesActivityOverview } from "../../types";

export function cambodiaDay(now: number): string {
  const parts = new Intl.DateTimeFormat("en", { timeZone: "Asia/Phnom_Penh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const part = (type: string) => parts.find((item) => item.type === type)?.value || "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

// Historical review stops at the team's last report on the selected day.
export function monitorReference(data: SalesActivityOverview | null, now: number): number | null {
  if (!data) return null;
  const today = cambodiaDay(now);
  if (data.date === today) return now;
  if (data.date > today) return null;
  const times = data.senders.map((sender) => sender.last_drop_at ? Date.parse(sender.last_drop_at) : NaN).filter(Number.isFinite);
  return times.length ? Math.max(...times) : null;
}

export function secondsSinceReport(timestamp: string | null, reference: number | null): number | null {
  if (!timestamp || reference === null) return null;
  const submitted = Date.parse(timestamp);
  return Number.isFinite(submitted) ? Math.max(0, (reference - submitted) / 1000) : null;
}

export function hasLongPause(sender: ActivitySender, reference: number | null, minutes: number): boolean {
  const elapsed = secondsSinceReport(sender.last_drop_at, reference);
  return sender.drop_count > 0 && elapsed !== null && elapsed > minutes * 60;
}
