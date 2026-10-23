import { startAutoRefresh } from "../../services/autoRefresh";
import React, { useEffect, useState } from "react";
import { ArrowUpRight, Clock, MapPin } from "lucide-react";
import { fetchActivityFeed } from "../../services/api";
import type { ActivityFeed, ActivityFeedEntry } from "../../types";
import { reportTime, previousDropLabel } from "./activityFormat";
import { channelLabel } from "./activityFilters";

export const RMRecentReports: React.FC<{
  date: string;
  senderId: number;
  thresholdMinutes?: number;
  refreshVersion: number;
  freshIds: Set<number>;
  onOpenDrop: (drop: ActivityFeedEntry) => void;
  onOpenTimeline: () => void;
}> = ({ date, senderId, thresholdMinutes, refreshVersion, freshIds, onOpenDrop, onOpenTimeline }) => {
  const [feed, setFeed] = useState<ActivityFeed | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    setFeed(null);
    setFailed(false);
    const load = async () => {
      const response = await fetchActivityFeed(date, thresholdMinutes, senderId);
      if (!alive) return;
      if (response) { setFeed(response); setFailed(false); }
      else setFailed(true);
    };
    const stop = startAutoRefresh(load);
    return () => { alive = false; stop(); };
  }, [date, senderId, thresholdMinutes, refreshVersion, retry]);
  const current = feed?.date === date && feed.sender_id === senderId ? feed : null;
  return <div className="border-t border-sky-100 bg-sky-50/50 px-3.5 pb-3.5 pt-3" data-testid="rm-recent-reports">
    <div className="mb-2 flex items-center justify-between gap-2 text-[10px]"><span className="font-semibold uppercase tracking-wide text-slate-600">Recent drops · newest first</span><button onClick={onOpenTimeline} className="inline-flex shrink-0 items-center gap-0.5 font-bold text-teal-800 hover:underline">Full timeline<ArrowUpRight className="h-2.5 w-2.5" /></button></div>
    {failed && <p role="status" className="mb-2 text-[10px] text-amber-700">Could not refresh reports. <button onClick={() => setRetry((value) => value + 1)} className="underline">Retry</button></p>}
    <div className="space-y-1.5">
      {current?.entries.slice(0, 5).map((drop) => <button key={drop.id} data-drop-id={drop.id} onClick={() => onOpenDrop(drop)}
        className={`block w-full rounded-2xl border bg-white p-3 text-left transition-colors hover:border-teal-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-700 ${freshIds.has(drop.id) ? "border-teal-600 ring-1 ring-teal-300" : "border-sky-100"}`}>
        <span className="flex items-center justify-between gap-2"><span data-testid="visit-number" className="font-mono text-[11px] font-bold tabular-nums text-slate-900">Visit #{drop.drop_number}<span data-testid="daily-visit-total" className="font-medium text-slate-600"> / {drop.daily_visit_count}</span></span><span className="font-mono text-[10px] font-semibold tabular-nums text-slate-700">{reportTime(drop.submitted_at, true)}</span></span>
        <span className="mt-1.5 block truncate text-xs font-semibold text-slate-900">{drop.merchant_name}</span>
        <span title={channelLabel(drop.source_channel?.trim() || "")} className="mt-1 block truncate text-[9px] text-slate-500">{channelLabel(drop.source_channel?.trim() || "")}</span>
        <span data-testid="drop-gap" className={`mt-1.5 flex items-center gap-1 text-[11px] font-medium ${drop.above_threshold ? "text-amber-800" : "text-slate-700"}`}><Clock className="h-2.5 w-2.5 shrink-0" />{previousDropLabel(drop)}</span>
        <span className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-600"><span className="inline-flex items-center gap-0.5"><MapPin className="h-2.5 w-2.5" />{drop.has_gps ? "GPS" : "No GPS"}</span>{drop.start_status === "late_start" && <span className="font-semibold text-sky-700">Late first drop · after 09:30</span>}{freshIds.has(drop.id) && <span className="rounded-full bg-teal-700 px-1 py-0.5 text-[9px] font-bold text-white">NEW</span>}</span>
      </button>)}
      {!current && !failed && <p className="py-4 text-center text-[10px] text-slate-400">Loading this RM's drops…</p>}
      {current && !current.total && <p className="py-4 text-center text-[10px] text-slate-400">No reports from this RM on this date.</p>}
    </div>
    {!!current?.total && <button onClick={onOpenTimeline} className="mt-2 w-full rounded-xl border border-sky-200 bg-white py-2 text-[11px] font-semibold text-slate-800 hover:border-teal-600 hover:text-teal-800">Open all {current.total} reported visits<ArrowUpRight className="ml-1 inline h-3 w-3" /></button>}
  </div>;
};
