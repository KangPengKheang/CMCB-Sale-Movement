import { startAutoRefresh } from "../../services/autoRefresh";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowUpRight, Bell, CheckCircle2, LocateFixed, Search, SlidersHorizontal, X } from "lucide-react";
import { fetchActivityFeed } from "../../services/api";
import type { ActivityFeed, ActivityFeedEntry, ActivitySender, SalesActivityOverview } from "../../types";
import { DailyStartRecognition } from "./DailyStartRecognition";
import { RMRecentReports } from "./RMRecentReports";
import { reportTime, previousDropLabel } from "./activityFormat";
import { RMActivityCard } from "./RMActivityCard";
import { channelLabel } from "./activityFilters";
import { useSession } from "../../context/SessionContext";

export const RMActivityPanel: React.FC<{
  date: string;
  overview: SalesActivityOverview | null;
  senders: ActivitySender[];
  selectedId: number | null;
  onSelectRM: (id: number) => void;
  followLatest: boolean;
  onFollowLatest: () => void;
  onOpenDrop: (drop: ActivityFeedEntry) => void;
  onOpenTimeline: (id: number) => void;
  channel: string | null;
  onChannel: (value: string | null) => void;
  search: string;
  onSearch: (value: string) => void;
  filter: string;
  onFilter: (value: string) => void;
  sort: string;
  onSort: (value: string) => void;
  showAll: boolean;
  onShowAll: (value: boolean) => void;
  thresholdMinutes?: number;
  refreshVersion: number;
  isLoading: boolean;
  referenceTime: number | null;
  isToday: boolean;
  reviewAfterMinutes: number;
  onReviewAfter: (value: number) => void;
}> = ({ date, overview, senders, selectedId, onSelectRM, followLatest, onFollowLatest, onOpenDrop, onOpenTimeline, channel, onChannel, search, onSearch, filter, onFilter, sort, onSort, showAll, onShowAll, thresholdMinutes, refreshVersion, isLoading, referenceTime, isToday, reviewAfterMinutes, onReviewAfter }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [onlyRecent, setOnlyRecent] = useState(false);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [feed, setFeed] = useState<ActivityFeed | null>(null);
  const [failed, setFailed] = useState(false);
  const [newDrops, setNewDrops] = useState<ActivityFeedEntry[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const session = useSession();
  const readKey = "cmcb-rm-read:" + JSON.stringify([session?.username || "anonymous", session?.allowed_sources, date]);
  type ReadMark = { count: number; at: string | null };
  const [readState, setReadState] = useState<{ key: string; marks: Record<string, ReadMark> }>({ key: "", marks: {} });
  useEffect(() => {
    let marks: Record<string, ReadMark> = {};
    try {
      const stored = JSON.parse(sessionStorage.getItem(readKey) || "{}");
      if (stored && typeof stored === "object" && !Array.isArray(stored)) marks = stored;
    } catch { /* Keep unread tracking available if browser storage is unavailable. */ }
    setReadState({ key: readKey, marks });
  }, [readKey]);
  useEffect(() => {
    if (readState.key !== readKey) return;
    try { sessionStorage.setItem(readKey, JSON.stringify(readState.marks)); } catch { /* In-memory tracking still works. */ }
  }, [readState, readKey]);
  const readMarks = readState.key === readKey ? readState.marks : {};
  const seen = useRef<{ date: string; ids: Set<number>; initialized: boolean }>({ date: "", ids: new Set(), initialized: false });
  useEffect(() => {
    let alive = true;
    if (seen.current.date !== date) {
      seen.current = { date, ids: new Set(), initialized: false };
      setFeed(null);
      setNewDrops([]);
      setExpandedId(null);
    }
    if (!date) return;
    const load = async () => {
      const response = await fetchActivityFeed(date, thresholdMinutes);
      if (!alive) return;
      if (!response) { setFailed(true); return; }
      const fresh = seen.current.initialized ? response.entries.filter((drop) => !seen.current.ids.has(drop.id)) : [];
      response.entries.forEach((drop) => seen.current.ids.add(drop.id));
      seen.current.initialized = true;
      if (fresh.length) setNewDrops(fresh);
      setFeed(response);
      setFailed(false);
    };
    const stop = startAutoRefresh(load);
    return () => { alive = false; stop(); };
  }, [date, thresholdMinutes, refreshVersion]);
  useEffect(() => {
    if (!newDrops.length) return;
    const timer = window.setTimeout(() => setNewDrops([]), 10000);
    return () => window.clearTimeout(timer);
  }, [newDrops]);
  useEffect(() => { setExpandedId((previous) => previous === selectedId ? previous : null); }, [selectedId]);
  const currentFeed = feed?.date === date ? feed : null;
  const latestByRM = useMemo(() => {
    const latest = new Map<number, ActivityFeedEntry>();
    currentFeed?.entries.forEach((drop) => { if (!latest.has(drop.sender_id)) latest.set(drop.sender_id, drop); });
    return latest;
  }, [currentFeed]);
  const latestDropFor = (sender: ActivitySender) => {
    const incoming = latestByRM.get(sender.sender_id);
    return incoming && (!sender.last_drop_at || Date.parse(incoming.submitted_at) >= Date.parse(sender.last_drop_at)) ? incoming : null;
  };
  const unreadCount = (sender: ActivitySender, latest: ActivityFeedEntry | null) => {
    const count = latest?.daily_visit_count ?? sender.drop_count;
    const at = latest?.submitted_at ?? sender.last_drop_at;
    if (!count) return 0;
    const read = readMarks[String(sender.sender_id)];
    if (!read || !Number.isFinite(read.count)) return count;
    if ((at || "") <= (read.at || "") && count <= read.count) return 0;
    return Math.max(1, count - read.count);
  };
  const markRead = (identity: number) => {
    const person = (overview?.senders || senders).find((sender) => sender.sender_id === identity);
    const incoming = latestByRM.get(identity);
    const latest = incoming && (!person?.last_drop_at || incoming.submitted_at >= person.last_drop_at) ? incoming : null;
    const count = latest?.daily_visit_count ?? person?.drop_count ?? 0;
    const at = latest?.submitted_at ?? person?.last_drop_at ?? null;
    if (!count) return;
    setReadState((previous) => ({
      key: readKey, marks: { ...(previous.key === readKey ? previous.marks : {}), [identity]: { count, at } },
    }));
  };
  const newByRM = new Map<number, number>();
  const freshIds = new Set(newDrops.map((drop) => drop.id));
  newDrops.forEach((drop) => newByRM.set(drop.sender_id, (newByRM.get(drop.sender_id) || 0) + 1));
  const channelSenders = (overview?.senders || []).filter((sender) => channel === null || sender.channels.includes(channel));
  const unreadSenderCount = senders.filter((sender) => unreadCount(sender, latestDropFor(sender)) > 0).length;
  const rows = senders.filter((sender) =>
    (!onlyRecent || latestByRM.has(sender.sender_id)) &&
    (!onlyUnread || unreadCount(sender, latestDropFor(sender)) > 0)
  );
  const filters = [{ value: "all", label: "All RMs" }, { value: "late", label: "Late Start" }, { value: "early", label: "Early Bird" }, { value: "no-gps", label: "Missing GPS" }, { value: "quiet", label: "Long reporting pause" }, { value: "no-drops", label: "No drops on date" }, ...(thresholdMinutes ? [{ value: "flagged", label: "Flagged gaps" }] : [])];
  const showGroup = (kind: "all" | "recent" | "late" | "unread") => {
    setOnlyUnread(kind === "unread");
    onFilter(kind === "late" ? "late" : "all");
    setOnlyRecent(kind === "recent");
    if (kind === "recent") onSort("latest");
    listRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };
  const openRM = (identity: number) => {
    markRead(identity);
    onSearch(""); onChannel(null); onFilter("all"); setOnlyRecent(false); setOnlyUnread(false);
    onSelectRM(identity); setExpandedId(identity);
  };
  const openDrop = (drop: ActivityFeedEntry) => {
    markRead(drop.sender_id);
    if (!senders.some((sender) => sender.sender_id === drop.sender_id)) {
      onSearch(""); onChannel(null); onFilter("all");
    }
    setOnlyRecent(false); setExpandedId(drop.sender_id); onOpenDrop(drop);
  };

  const toggleRM = (sender: ActivitySender, expanded: boolean) => {
    markRead(sender.sender_id);
    if (onlyUnread) {
      setExpandedId(null);
      onOpenTimeline(sender.sender_id);
      if (window.matchMedia("(max-width: 1023px)").matches) {
        window.requestAnimationFrame(() => document.getElementById("activity-brief")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }));
      }
      return;
    }
    onSelectRM(sender.sender_id);
    setExpandedId(expanded ? null : sender.sender_id);
  };

  return <section className="flex h-[730px] min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-300 bg-white shadow-sm lg:h-full" aria-label="RM Activity">
    <header className="shrink-0 border-b-2 border-teal-400 bg-slate-950 px-4 py-3.5 text-white">
      <div className="flex items-center justify-between gap-2"><h3 className="flex items-center gap-2 text-[15px] font-bold tracking-tight"><Activity className="h-4 w-4 text-teal-300" />RM Activity</h3><span className="rounded-full border border-teal-400/40 bg-teal-400/10 px-2 py-1 text-[10px] font-semibold tabular-nums text-teal-200">{senders.filter((sender) => sender.drop_count > 0).length} reporting</span></div>
      <p className="mt-1.5 text-[11px] text-slate-300">Performance and drops, together · {senders.reduce((total, sender) => total + sender.drop_count, 0)} daily visits in view</p>
    </header>
    <div className="shrink-0 space-y-2.5 border-b border-slate-300 px-3 py-3">
      <div className="relative"><Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" /><input aria-label="Search by sender name" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search sender name or ID" className="w-full rounded-xl border border-slate-300 bg-white py-2 pl-8 pr-2 text-[11px] text-slate-900 placeholder:text-slate-500 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600" /></div>
      <label className="block">
        <span className="mb-1 block text-[10px] font-semibold text-slate-600">Channel</span>
        <select aria-label="Filter by channel" value={JSON.stringify(channel)} onChange={(event) => { onChannel(JSON.parse(event.target.value)); setOnlyRecent(false); listRef.current?.scrollTo({ top: 0 }); }}
          title={channel === null ? "All report channels" : channelLabel(channel)} className="w-full min-w-0 rounded-xl border border-slate-300 bg-white px-2.5 py-2 text-[11px] font-medium text-slate-800 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600">
          <option value="null">All channels</option>
          {(overview?.channels || []).map((item) => <option key={item.name} value={JSON.stringify(item.name)}>{channelLabel(item.name)} · {item.sender_count} RM{item.sender_count === 1 ? "" : "s"}</option>)}
          {channel !== null && !overview?.channels.some((item) => item.name === channel) && <option value={JSON.stringify(channel)}>{channelLabel(channel)} · no drops on this date</option>}
        </select>
        {channel !== null && <span className="mt-1 block text-[9px] leading-4 text-slate-500">People who dropped here · cards show full-day visits</span>}
      </label>
      <div className="grid grid-cols-2 gap-1 rounded-xl border border-slate-200 bg-slate-100 p-1">
        {([{ id: "all", label: "All RMs", active: !onlyUnread && !onlyRecent && filter === "all" }, { id: "recent", label: "Recent drops", active: onlyRecent }, { id: "late", label: `Late Start · ${channelSenders.filter((sender) => sender.start_status === "late_start").length}`, active: filter === "late" && !onlyRecent && !onlyUnread }, { id: "unread", label: `Unread only · ${unreadSenderCount}`, active: onlyUnread }] as const).map((item) =>
          <button key={item.id} onClick={() => showGroup(item.id)} aria-label={item.id === "unread" ? "Show only unread RMs" : item.label} aria-pressed={item.active} className={`rounded-lg px-1 py-1.5 text-[10px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 ${item.active ? "bg-slate-900 text-white shadow-sm" : "text-slate-600 hover:bg-white hover:text-slate-900"}`}>{item.label}</button>)}
      </div>
      <div className="rounded-xl border border-cyan-100 bg-cyan-50/50 p-2">
        <button type="button" aria-label="Follow latest case drops on map" aria-pressed={followLatest} onClick={onFollowLatest}
          className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-[11px] font-bold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-700 ${followLatest ? "bg-teal-700 text-white shadow-sm" : "bg-white text-slate-700 hover:bg-teal-50"}`}>
          <span className="inline-flex items-center gap-2"><LocateFixed className="h-4 w-4" />Follow latest</span>
          <span className={`rounded-full px-2 py-0.5 text-[9px] ${followLatest ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"}`}>{followLatest ? "ON" : "OFF"}</span>
        </button>
        <p className="mt-1.5 px-1 text-[9px] leading-4 text-slate-500">{followLatest ? "Follows the newest GPS case with all of that RM's points in view." : "Turn on to follow the latest GPS case and keep the full RM route visible."} Colored rings stay until you open an RM.</p>
      </div>
      <details className="text-[10px] text-slate-600"><summary className="cursor-pointer select-none"><span className="inline-flex items-center gap-1"><SlidersHorizontal className="h-2.5 w-2.5" />Filters & first-drop highlights</span></summary>
        <div className="mt-2 flex gap-1.5">
          <select aria-label="Filter RMs" value={filter} onChange={(event) => onFilter(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white p-1.5">{filters.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select>
          <select aria-label="Sort salespeople" value={sort} onChange={(event) => onSort(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white p-1.5"><option value="quiet">Longest since last report</option><option value="latest">Latest drop</option><option value="drops">Most visits</option><option value="gaps">Longest gaps</option><option value="first">First drop</option><option value="name">Name</option></select>
        </div>
        <label className="mt-2 flex items-center justify-between gap-2">Reporting pause window
          <select aria-label="Reporting pause review window" value={reviewAfterMinutes} onChange={(event) => onReviewAfter(Number(event.target.value))} className="rounded-lg border border-slate-300 bg-white px-2 py-1 font-semibold text-slate-800">
            {[15, 30, 60, 90].map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}
          </select>
        </label>
        <label className="my-2 flex items-center gap-1.5"><input type="checkbox" checked={showAll} onChange={(event) => onShowAll(event.target.checked)} />Include RMs with no drops</label>
        <DailyStartRecognition compact data={overview} onSelect={openRM} onShowLate={() => showGroup("late")} />
      </details>
    </div>
    {failed && <p role="status" className="shrink-0 bg-amber-50 px-3 py-2 text-[10px] text-amber-700">Could not refresh new drops. Retrying automatically.</p>}
    {!!newDrops.length && <button onClick={() => { onSearch(""); onChannel(null); showGroup("recent"); }} className="flex shrink-0 items-center justify-between border-b border-teal-100 bg-teal-50 px-3 py-2 text-[10px] font-semibold text-teal-700"><span className="flex items-center gap-1.5"><Bell className="h-3 w-3" />{newDrops.length} new report{newDrops.length === 1 ? "" : "s"}</span><span>View activity ↑</span></button>}
    <div ref={listRef} className="min-h-0 max-h-[650px] flex-1 space-y-3 overflow-y-auto bg-gradient-to-b from-slate-50 to-sky-50/60 p-3 lg:max-h-none" data-testid="rm-activity-list">
      {rows.map((sender) => {
        const latest = latestDropFor(sender);
        const fresh = newByRM.get(sender.sender_id) || 0;
        const expanded = expandedId === sender.sender_id;
        const selected = selectedId === sender.sender_id;
        return <RMActivityCard key={sender.sender_id} sender={sender} latest={latest} fresh={fresh} unread={unreadCount(sender, latest)} expanded={expanded} selected={selected}
          referenceTime={referenceTime} isToday={isToday} reviewAfterMinutes={reviewAfterMinutes}
          onToggle={() => toggleRM(sender, expanded)}>
          {expanded && <RMRecentReports date={date} senderId={sender.sender_id} thresholdMinutes={thresholdMinutes} refreshVersion={refreshVersion}
            freshIds={freshIds} onOpenDrop={openDrop} onOpenTimeline={() => { markRead(sender.sender_id); onOpenTimeline(sender.sender_id); }} />}
        </RMActivityCard>;
      })}
      {!rows.length && <div role="status" className="py-10 text-center">
        {onlyUnread && !isLoading ? <CheckCircle2 className="mx-auto h-7 w-7 text-teal-500" /> : <Activity className="mx-auto h-6 w-6 text-slate-300" />}
        <p className="mt-2 text-xs font-medium text-slate-500">{isLoading ? "Loading RM activity…" : onlyUnread ? "No unread RMs in this view." : "No RMs match this date, channel, name and filter."}</p>
        {onlyUnread && !isLoading && <><p className="mt-1 px-3 text-[10px] leading-4 text-slate-400">New unreviewed cases will appear automatically.</p><button onClick={() => showGroup("all")} className="mt-3 rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-[10px] font-semibold text-teal-800 hover:bg-teal-100">Show all RMs</button></>}
      </div>}
    </div>
    <p className="shrink-0 border-t border-slate-300 bg-white px-3 py-2 text-[9px] leading-relaxed text-slate-600">{rows.length} RMs shown · {filter === "no-drops" ? "Previously observed RMs; assignments and leave are not known." : filter === "quiet" ? "Reporting pauses for review; working hours are not assumed." : onlyUnread ? "Unread cases only; open an RM to review their timeline" : onlyRecent ? "RMs in the latest 50 team reports" : "expand a card for reports"}{!isToday && referenceTime !== null && <span className="mt-0.5 block">Historical as of {reportTime(new Date(referenceTime).toISOString())}</span>}</p>

    {!!newDrops.length && <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-[1000] w-80 max-w-[calc(100vw-32px)] rounded-2xl border border-teal-600 bg-white p-3 shadow-xl">
      <div className="mb-2 flex items-center justify-between"><span className="flex items-center gap-1.5 text-xs font-bold text-teal-700"><Bell className="h-3.5 w-3.5" />{date === overview?.today ? "New RM activity" : "New reports for this date"} · {newDrops.length}</span><button aria-label="Dismiss new drop notification" onClick={() => setNewDrops([])} className="rounded-lg p-1 text-slate-600 hover:bg-slate-100"><X className="h-3.5 w-3.5" /></button></div>
      {newDrops.slice(0, 3).map((drop) => <button key={drop.id} onClick={() => openDrop(drop)} className="block w-full border-t border-slate-100 py-2 text-left"><span className="block truncate text-[11px] font-semibold text-slate-800">{drop.sender_name} @ {drop.merchant_name}</span><span className="mt-1 block text-[10px] font-bold text-teal-700">Visit #{drop.drop_number} · {drop.daily_visit_count} visits</span><span className="mt-0.5 block text-[10px] text-slate-500">{previousDropLabel(drop)}</span></button>)}
      {newDrops.length > 3 && <button onClick={() => { onChannel(null); onSearch(""); showGroup("recent"); }} className="text-[10px] font-semibold text-teal-700">View {newDrops.length - 3} more in RM Activity<ArrowUpRight className="ml-1 inline h-3 w-3" /></button>}
    </div>}
  </section>;
};
