import React from "react";
import { ChevronDown, Clock, MapPin, Store } from "lucide-react";
import type { ActivityFeedEntry, ActivitySender } from "../../types";
import { StartBadge } from "./DailyStartRecognition";
import { gapDuration, previousDropLabel, reportTime } from "./activityFormat";
import { secondsSinceReport } from "./monitoring";

const initials = (name: string) => {
  const words = name.trim().split(/\s+/);
  return (Array.from(words[0] || "?")[0] + (words.length > 1 ? Array.from(words[words.length - 1])[0] : "")).toUpperCase();
};

export const RMActivityCard: React.FC<{
  sender: ActivitySender;
  latest: ActivityFeedEntry | null;
  fresh: number;
  unread: number;
  expanded: boolean;
  selected: boolean;
  referenceTime: number | null;
  isToday: boolean;
  reviewAfterMinutes: number;
  onToggle: () => void;
  children?: React.ReactNode;
}> = ({ sender, latest, fresh, unread, expanded, selected, referenceTime, isToday, reviewAfterMinutes, onToggle, children }) => {
  const total = latest?.daily_visit_count ?? sender.drop_count;
  const merchant = latest?.merchant_name ?? sender.last_drop_merchant_name;
  const lastTime = latest?.submitted_at ?? sender.last_drop_at;
  const hasGPS = latest ? !!latest.has_gps : sender.last_drop_has_gps;
  const elapsed = secondsSinceReport(lastTime, referenceTime);
  const longPause = elapsed !== null && elapsed > reviewAfterMinutes * 60;
  const interval = latest ?? { gap_seconds: sender.last_gap_seconds, overnight_gap: sender.last_gap_overnight };
  return <article data-sender-id={sender.sender_id} data-new-count={fresh} data-unread-count={unread}
    style={unread ? { borderColor: sender.color, boxShadow: `0 0 0 2px ${sender.color}40, 0 5px 20px -10px ${sender.color}45` } : undefined}
    className={`overflow-hidden rounded-[24px] border bg-gradient-to-br from-white via-white to-sky-50/50 shadow-[0_5px_20px_-10px_rgba(15,79,113,0.28)] transition-[border-color,box-shadow] duration-200 motion-reduce:transition-none ${fresh ? "sales-rm-new border-teal-400 ring-1 ring-teal-200" : selected ? "border-teal-400 ring-1 ring-teal-200" : "border-sky-100 hover:border-cyan-300"}`}>
    <button onClick={onToggle} aria-expanded={expanded} aria-pressed={selected} aria-label={`Expand activity for ${sender.sender_name}${unread ? `, ${unread} unread case drops` : ""}`}
      className="block w-full rounded-[23px] p-3.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-teal-700">
      <span className="flex items-start gap-2">
        <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-full border-2 text-[14px] font-bold" style={{ backgroundColor: sender.color + "12", borderColor: sender.color + "35", color: sender.color, boxShadow: unread ? `0 0 0 2px white, 0 0 0 4px ${sender.color}` : undefined }}>{initials(sender.sender_name)}
          {!!unread && <span aria-hidden="true" className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-white" style={{ backgroundColor: sender.color }} />}
        </span>
        <span className="min-w-0 flex-1 pt-0.5">
          <span className="flex items-start gap-1">
            <span title={sender.sender_name} className="line-clamp-2 min-w-0 break-words text-[13px] font-bold leading-[18px] tracking-tight text-[#071b45]">{sender.sender_name}</span>
            {!!unread && <span className="mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[8px] font-bold text-white" style={{ backgroundColor: sender.color }}>UNREAD {unread}</span>}
          </span>
          <span className="mt-1.5 block"><StartBadge sender={sender} prominent /></span>
          <span className="mt-1 block font-mono text-[10px] leading-4 tracking-wide text-slate-500">First {reportTime(sender.first_drop_at, true)}</span>
        </span>
        <span className="grid min-h-[62px] w-[50px] shrink-0 content-center justify-items-center rounded-2xl border border-cyan-100 bg-gradient-to-br from-cyan-50/60 to-sky-50 px-1 py-1.5">
          <span data-testid="rm-visit-count" className="block text-[28px] font-bold tabular-nums leading-8 tracking-tight text-[#071b45]">{total}</span>
          <span className="mt-0.5 block text-[9px] font-bold uppercase tracking-wide text-slate-500">Visits</span>
        </span>
        <ChevronDown className={`mt-3 h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`} />
      </span>

      <span className="mt-3 flex items-start gap-2 border-t border-sky-100 pt-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-cyan-50 text-teal-600"><Store className="h-4 w-4" strokeWidth={2.2} /></span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-1.5">
            <span title={merchant || undefined} className="min-w-0 truncate text-[12px] font-bold leading-5 text-[#071b45]">{merchant || (total ? "Latest report" : "No reports on this date")}</span>
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-cyan-50 bg-sky-50 px-1.5 py-1 font-mono text-[9px] font-semibold tabular-nums text-[#071b45]"><Clock className="h-3 w-3 text-slate-500" />{reportTime(lastTime, true)}</span>
          </span>
          <span data-testid="rm-report-age" className={`mt-1 block text-[10px] leading-4 ${longPause ? "font-medium text-amber-800" : "text-slate-500"}`}>{elapsed === null ? (lastTime ? "Review time unavailable" : "No drops on this date") : `${gapDuration(elapsed)} since report${isToday ? "" : " at review time"}`}</span>
        </span>
      </span>

      {total > 0 && <span className={`mt-3 flex items-center gap-2 rounded-2xl border p-2.5 ${latest?.above_threshold ? "border-amber-200 bg-amber-50/70" : "border-sky-100 bg-gradient-to-r from-cyan-50/70 to-sky-50/80"}`}>
        <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${latest?.above_threshold ? "bg-amber-100 text-amber-700" : "bg-cyan-100/70 text-teal-600"}`}><Clock className="h-4 w-4" strokeWidth={2.4} /></span>
        <span data-testid="rm-latest-gap" title={previousDropLabel(interval)} className="min-w-0 flex-1 text-[10px] leading-4 text-slate-500">
          <strong className={`block text-[15px] font-bold tabular-nums leading-5 ${latest?.above_threshold ? "text-amber-900" : "text-[#071b45]"}`}>{interval.gap_seconds === null ? "First report" : gapDuration(interval.gap_seconds)}</strong>
          <span className="block">{interval.gap_seconds === null ? "No earlier drop" : "since last drop"}{interval.overnight_gap ? " · across dates" : ""}</span>
        </span>
        <span className={`inline-flex shrink-0 items-center gap-1 border-l border-sky-200 pl-2 text-[10px] font-semibold ${hasGPS ? "text-slate-500" : "text-amber-800"}`}><MapPin className={`h-4 w-4 ${hasGPS ? "text-teal-600" : "text-amber-600"}`} strokeWidth={2.5} />{hasGPS ? "GPS" : "No GPS"}</span>
      </span>}
    </button>
    {children}
  </article>;
};
