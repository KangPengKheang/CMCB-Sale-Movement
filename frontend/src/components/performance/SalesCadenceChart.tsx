import React, { useState } from "react";
import { Activity, ChevronDown } from "lucide-react";
import type { ActivitySender } from "../../types";

const localTime = (value: string) => new Date(value).toLocaleTimeString("en-GB", {
  timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", second: "2-digit",
});
const position = (value: string) => {
  const parts = localTime(value).split(":").map(Number);
  return (parts[0] * 3600 + parts[1] * 60 + parts[2]) / 864;
};
const shortGap = (seconds: number) => seconds < 3600
  ? `${Math.round(seconds / 60)} min` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;

export const SalesCadenceChart: React.FC<{
  senders: ActivitySender[];
  selectedId: number | null;
  thresholdMinutes?: number;
  onSelect: (id: number) => void;
}> = ({ senders, selectedId, thresholdMinutes, onSelect }) => {
  const [expanded, setExpanded] = useState(false);
  const active = senders.filter((sender) => sender.drop_count > 0);
  const visible = expanded ? active : active.slice(0, 8);
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900"><Activity className="h-4 w-4 text-teal-600" />The rhythm of the day</h3>
        <p className="mt-1 text-xs text-slate-500">Every dot is a report drop, including those without GPS. Select a row to explore a salesperson.</p>
      </div>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-semibold text-slate-500">Cambodia time · 24 hours</span>
    </div>
    <div className="overflow-x-auto">
      <div className="min-w-[640px] px-5 pb-3 pt-5">
        <div className="mb-3 grid grid-cols-[155px_minmax(0,1fr)_48px] gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Salesperson</span>
          <div className="relative h-3">{[0, 6, 12, 18, 24].map((hour) => <span key={hour}
            className="absolute -translate-x-1/2 text-[10px] text-slate-400" style={{ left: `${hour / 24 * 100}%` }}>{String(hour).padStart(2, "0")}:00</span>)}</div>
          <span className="text-right text-[10px] text-slate-400">Drops</span>
        </div>
        {visible.map((sender) => <button key={sender.sender_id} onClick={() => onSelect(sender.sender_id)}
          aria-pressed={sender.sender_id === selectedId}
          className={`grid w-full grid-cols-[155px_minmax(0,1fr)_48px] items-center gap-3 rounded-lg px-1 py-2.5 text-left transition-colors hover:bg-slate-50 ${sender.sender_id === selectedId ? "bg-slate-50 ring-1 ring-inset ring-slate-200" : ""}`}>
          <span className="flex min-w-0 items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: sender.color }} />
            <span className="truncate text-xs font-medium text-slate-700">{sender.sender_name}</span>
          </span>
          <span className="relative block h-6">
            {[0, 6, 12, 18, 24].map((hour) => <span key={hour} className="absolute inset-y-0 border-l border-slate-100" style={{ left: `${hour / 24 * 100}%` }} />)}
            {sender.first_drop_at && sender.last_drop_at && <span className="absolute top-2.5 h-1 rounded-full opacity-15"
              style={{ left: `${position(sender.first_drop_at)}%`, width: `${position(sender.last_drop_at) - position(sender.first_drop_at)}%`, backgroundColor: sender.color }} />}
            {(sender.drop_times || []).map((time, index, times) => {
              const gap = index ? (Date.parse(time) - Date.parse(times[index - 1])) / 1000 : null;
              const flagged = thresholdMinutes && gap !== null && gap > thresholdMinutes * 60;
              return <React.Fragment key={`${time}-${index}`}>
                {!!flagged && <span className="absolute top-2 h-2 rounded bg-amber-200/70"
                  style={{ left: `${position(times[index - 1])}%`, width: `${position(time) - position(times[index - 1])}%` }}
                  title={`${shortGap(gap!)} between drops`} />}
                <span title={`${sender.sender_name} · Drop ${index + 1} · ${localTime(time)}${gap === null ? "" : ` · ${shortGap(gap)} since previous drop`}`}
                  className="absolute top-1.5 h-3 w-1.5 -translate-x-1/2 rounded-sm ring-1 ring-white"
                  style={{ left: `${position(time)}%`, backgroundColor: sender.color }} />
              </React.Fragment>;
            })}
          </span>
          <span className="text-right font-mono text-xs font-bold text-slate-700">{sender.drop_count}</span>
        </button>)}
        {!active.length && <p className="py-8 text-center text-xs text-slate-400">No report drops match these filters.</p>}
      </div>
    </div>
    {active.length > 8 && <button onClick={() => setExpanded((previous) => !previous)}
      className="flex w-full items-center justify-center gap-1 border-t border-slate-100 py-3 text-xs font-semibold text-slate-500 hover:bg-slate-50">
      {expanded ? "Show fewer salespeople" : `Show all ${active.length} salespeople`}<ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
    </button>}
  </section>;
};
