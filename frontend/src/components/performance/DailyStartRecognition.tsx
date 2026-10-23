import React from "react";
import { Flame, Moon, Clock, Trophy, ArrowRight } from "lucide-react";
import type { ActivitySender, SalesActivityOverview } from "../../types";
import { reportTime } from "./activityFormat";

export const StartBadge: React.FC<{ sender: ActivitySender; prominent?: boolean }> = ({ sender, prominent = false }) => {
  const layout = prominent
    ? "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide"
    : "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase";
  const LateIcon = prominent ? Clock : Moon;
  return sender.is_early_bird
    ? <span className={`${layout} border-rose-200 bg-rose-50 text-rose-700`}><Flame className={prominent ? "h-3 w-3" : "h-2.5 w-2.5"} />Early Bird</span>
    : sender.start_status === "late_start"
      ? <span title="First report drop after 09:30 Cambodia time" className={`${layout} ${prominent ? "border-sky-200 bg-sky-100/80 text-sky-600" : "border-sky-200 bg-sky-50 text-sky-700"}`}><LateIcon className={prominent ? "h-3 w-3" : "h-2.5 w-2.5"} />Late Start</span>
      : null;
};

export const DailyStartRecognition: React.FC<{
  data: SalesActivityOverview | null;
  onSelect: (id: number) => void;
  onShowLate: () => void;
  compact?: boolean;
}> = ({ data, onSelect, onShowLate, compact = false }) => {
  const late = (data?.senders || []).filter((sender) => sender.start_status === "late_start")
    .sort((first, second) => (first.first_drop_at || "").localeCompare(second.first_drop_at || ""));
  const champions = data?.recognition.early_birds || [];
  return <div className={compact ? "space-y-1.5" : "grid gap-3 md:grid-cols-2"}>
    <div className="overflow-hidden rounded-xl border border-rose-500/30 bg-gradient-to-r from-red-950 via-rose-900 to-red-950 text-white shadow-sm">
      {champions.length ? champions.map((champion) => <button key={champion.id} onClick={() => onSelect(champion.sender_id)} data-testid="early-bird-card"
        className="flex w-full items-center justify-between gap-2 p-2.5 text-left hover:bg-white/5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-rose-400/30 bg-rose-500/20"><Flame className="h-3.5 w-3.5 fill-rose-400 text-rose-200" /></span>
          <span className="min-w-0"><span className="block font-mono text-[10px] font-bold uppercase tracking-wider text-rose-300">Early Bird · {reportTime(champion.submitted_at)}</span>
            <span className="block truncate text-xs font-bold">{champion.sender_name}<span className="font-normal text-rose-200"> @ {champion.merchant_name}</span></span></span>
        </div>
        <span className="flex shrink-0 items-center gap-1 rounded border border-rose-400/30 bg-rose-500/20 px-2 py-1 text-[9px] font-bold uppercase text-rose-200"><Trophy className="h-3 w-3" />First to drop</span>
      </button>) : <div className="flex items-center gap-2 p-2.5"><Trophy className="h-5 w-5 text-rose-300" /><div><p className="text-xs font-bold">Early Bird</p><p className="mt-1 text-[10px] text-rose-200">{data ? "No first drop at or before 09:30 on this date." : "Waiting for the daily reports."}</p></div></div>}
    </div>
    <div className="overflow-hidden rounded-xl border border-sky-500/30 bg-gradient-to-r from-slate-950 via-sky-950 to-blue-950 text-white shadow-sm">
      {late.length ? <div className="flex h-full items-center justify-between gap-2 p-2.5" data-testid="late-start-card">
        <button onClick={() => onSelect(late[0].sender_id)} className="flex min-w-0 items-center gap-2.5 text-left">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-sky-400/30 bg-sky-500/20"><Moon className="h-3.5 w-3.5 text-sky-200" /></span>
          <span className="min-w-0"><span className="block font-mono text-[10px] font-bold uppercase tracking-wider text-sky-300">Late Drop · {reportTime(late[0].first_drop_at, true)}</span>
            <span className="block truncate text-xs font-bold">{late[0].sender_name}<span className="font-normal text-sky-200"> @ {late[0].first_drop_merchant_name}</span></span>
            <span className="mt-0.5 block text-[9px] text-sky-300">{late.length} RM{late.length === 1 ? "" : "s"} with a first drop after 09:30</span>
          </span>
        </button>
        <button onClick={onShowLate} className="flex shrink-0 items-center gap-1 rounded border border-sky-400/30 bg-sky-500/20 px-2 py-1 text-[9px] font-bold uppercase text-sky-200">View RMs<ArrowRight className="h-3 w-3" /></button>
      </div> : <div className="flex items-center gap-2 p-2.5"><Moon className="h-5 w-5 text-sky-300" /><div><p className="text-xs font-bold">Late Start</p><p className="mt-1 text-[10px] text-sky-200">No first drops after 09:30 on this date.</p></div></div>}
    </div>
    {!compact && <p className="text-[10px] text-slate-500 md:col-span-2">Early Bird recognizes the earliest first report at or before 09:30. Late Start marks each RM's first report after 09:30. These are report times, not arrival times. Cambodia time.</p>}
  </div>;
};
