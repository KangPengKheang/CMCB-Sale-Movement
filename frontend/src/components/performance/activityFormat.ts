export const reportTime = (value: string | null, seconds = false) => value
  ? new Date(value).toLocaleTimeString("en-GB", {
      timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", ...(seconds ? { second: "2-digit" } : {}),
    }) : "—";

export function gapDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
}

export function previousDropLabel(drop: { gap_seconds: number | null; overnight_gap: boolean }): string {
  if (drop.gap_seconds === null) return "No earlier drop";
  return `${gapDuration(drop.gap_seconds)} since last drop${drop.overnight_gap ? " · across dates" : ""}`;
}
