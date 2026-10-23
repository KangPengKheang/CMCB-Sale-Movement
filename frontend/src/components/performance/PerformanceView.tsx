import { startAutoRefresh } from "../../services/autoRefresh";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, RefreshCw, MapPin, ChevronLeft, ChevronRight, SlidersHorizontal, Radio, Bell, BarChart3, ListOrdered } from "lucide-react";
import { fetchActivityOverview, fetchSenderActivity } from "../../services/api";
import type { ActivityFeedEntry, SalesActivityOverview, SenderActivity } from "../../types";
import { SalesCadenceChart } from "./SalesCadenceChart";
import { SalesMovementMap } from "./SalesMovementMap";
import { RMActivityPanel } from "./RMActivityPanel";
import { StartBadge } from "./DailyStartRecognition";
import { cambodiaDay, hasLongPause, monitorReference } from "./monitoring";
import { matchesSenderSearch } from "./activityFilters";

const reportTimeLabel = (value: Date) => value.toLocaleTimeString("en-GB", { timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", second: "2-digit" });

const localTime = (value: string | null) => value
  ? new Date(value).toLocaleTimeString("en-GB", {
      timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", second: "2-digit",
    }) : "—";

function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`;
  const hours = Math.floor(seconds / 3600);
  return `${hours}h ${Math.floor((seconds % 3600) / 60)}m`;
}

export const PerformanceView: React.FC = () => {
  const [data, setData] = useState<SalesActivityOverview | null>(null);
  const [detail, setDetail] = useState<SenderActivity | null>(null);
  const [day, setDay] = useState("");
  const [threshold, setThreshold] = useState("");
  const [reviewAfterMinutes, setReviewAfterMinutes] = useState(30);
  const [clockNow, setClockNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setClockNow(Date.now()), 15000);
    return () => window.clearInterval(timer);
  }, []);
  const [panel, setPanel] = useState<"map" | "rhythm" | "timeline">("map");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [focusedDropId, setFocusedDropId] = useState<number | null>(null);
  const [followLatest, setFollowLatest] = useState(false);
  const followPoint = useCallback((senderId: number, pointId: number) => {
    setSelectedId(senderId); setFocusedDropId(pointId); setPage(0);
  }, []);
  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("latest");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [page, setPage] = useState(0);
  const [offline, setOffline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const thresholdMinutes = threshold ? Number(threshold) : undefined;

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const response = await fetchActivityOverview(day || undefined, thresholdMinutes);
      if (!alive) return;
      setIsLoading(false);
      if (!response) { setOffline(true); return; }
      setData(response);
      setLastUpdated(new Date());
      setOffline(false);
    };
    setIsLoading(true);
    const stop = startAutoRefresh(load);
    return () => { alive = false; stop(); };
  }, [day, thresholdMinutes, refreshVersion]);

  const selectedDay = day || data?.date || "";
  useEffect(() => { setFocusedDropId(null); }, [selectedDay]);
  useEffect(() => { setPage(0); }, [selectedDay, thresholdMinutes]);
  useEffect(() => {
    if (selectedId === null || !selectedDay) { setDetail(null); return; }
    let alive = true;
    const load = async () => {
      const result = await fetchSenderActivity(selectedId, selectedDay, thresholdMinutes, page * 100);
      if (alive) setDetail(result);
    };
    setDetail(null);
    const stop = startAutoRefresh(load);
    return () => { alive = false; stop(); };
  }, [selectedId, selectedDay, thresholdMinutes, page, refreshVersion]);

  const referenceTime = monitorReference(data, clockNow);
  const isToday = selectedDay === cambodiaDay(clockNow);
  const selected = data?.senders.find((sender) => sender.sender_id === selectedId);
  const visible = useMemo(() => (data?.senders || []).filter((sender) =>
    (channel === null || sender.channels.includes(channel)) &&
    (showAll || filter === "no-drops" || sender.drop_count > 0) &&
    (filter !== "quiet" || hasLongPause(sender, referenceTime, reviewAfterMinutes)) &&
    (filter !== "no-drops" || sender.drop_count === 0) &&
    (filter !== "no-gps" || sender.missing_gps_count > 0) &&
    (filter !== "late" || sender.start_status === "late_start") &&
    (filter !== "early" || sender.is_early_bird) &&
    (filter !== "flagged" || sender.above_threshold_count > 0) &&
    matchesSenderSearch(sender, search)
  ).sort((first, second) => {
    if (sort === "quiet") return (first.last_drop_at ? Date.parse(first.last_drop_at) : Infinity) - (second.last_drop_at ? Date.parse(second.last_drop_at) : Infinity) || first.sender_name.localeCompare(second.sender_name);
    if (sort === "gaps") return (second.longest_gap_seconds ?? -1) - (first.longest_gap_seconds ?? -1);
    if (sort === "latest") return (second.last_drop_at || "").localeCompare(first.last_drop_at || "");
    if (sort === "name") return first.sender_name.localeCompare(second.sender_name);
    if (sort === "first") return (first.first_drop_at || "~").localeCompare(second.first_drop_at || "~");
    return second.drop_count - first.drop_count || first.sender_name.localeCompare(second.sender_name);
  }), [data, search, channel, showAll, filter, sort, referenceTime, reviewAfterMinutes]);
  const visibleSenderIds = useMemo(() => visible.map((sender) => sender.sender_id).sort((first, second) => first - second), [visible]);
  useEffect(() => {
    if (selectedId !== null && visible.some((sender) => sender.sender_id === selectedId)) return;
    setSelectedId(visible.find((sender) => sender.gps_count > 0)?.sender_id ?? visible[0]?.sender_id ?? null);
    setPage(0); setFocusedDropId(null);
  }, [visible, selectedId]);
  const maxDay = Math.max(1, ...(detail?.daily_history.map((item) => item.drop_count) || []));
  const selectedDateIndex = data?.available_dates.indexOf(selectedDay) ?? -1;
  const changeDay = (newDay: string) => { setDay(newDay); setData(null); setPage(0); };
  const chooseSender = (id: number) => { setSelectedId(id); setPage(0); setFocusedDropId(null); };
  const openFeedDrop = (drop: ActivityFeedEntry) => {
    chooseSender(drop.sender_id);
    setPage(Math.floor((drop.drop_number - 1) / 100));
    setFocusedDropId(drop.id);
    setPanel(drop.has_gps ? "map" : "timeline");
    if (window.matchMedia("(max-width: 1023px)").matches) {
      window.requestAnimationFrame(() => document.getElementById("activity-brief")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };
  const shownDrops = visible.reduce((total, sender) => total + sender.drop_count, 0);
  const shownGPS = visible.reduce((total, sender) => total + sender.gps_count, 0);
  const gpsShare = shownDrops ? Math.round(shownGPS / shownDrops * 100) : 0;
  const chartColor = selected?.color || "#0d9488";
  const dayLabel = selectedDay ? new Date(`${selectedDay}T12:00:00+07:00`).toLocaleDateString("en-GB", {
    timeZone: "Asia/Phnom_Penh", weekday: "short", day: "numeric", month: "long", year: "numeric",
  }) : "Loading report date";
  const sourceReady = !offline && data && data.source_status.state !== "error";
  const sheetChecked = data?.source_status.last_checked;
  const sheetInterval = data?.source_status.refresh_seconds ?? 15;



  return (
    <div className="grid h-full min-h-0 auto-rows-min grid-cols-1 gap-3 overflow-y-auto bg-slate-50 p-3 lg:auto-rows-auto lg:grid-cols-[330px_minmax(0,1fr)] lg:overflow-hidden">
      <aside id="daily-rm-panel" className="order-2 flex min-h-[730px] flex-col gap-3 lg:order-1 lg:h-full lg:min-h-0">
        <RMActivityPanel date={selectedDay} overview={data} senders={visible} selectedId={selectedId}
          onSelectRM={chooseSender} onOpenDrop={openFeedDrop}
          followLatest={followLatest} onFollowLatest={() => { setFocusedDropId(null); setFollowLatest((value) => !value); setPanel("map"); }}
          onOpenTimeline={(id) => { chooseSender(id); setPanel("timeline"); }}
          channel={channel} onChannel={setChannel}
          search={search} onSearch={setSearch} filter={filter} onFilter={setFilter} sort={sort} onSort={setSort}
          showAll={showAll} onShowAll={setShowAll} thresholdMinutes={thresholdMinutes}
          refreshVersion={refreshVersion} isLoading={isLoading}
          referenceTime={referenceTime} isToday={isToday} reviewAfterMinutes={reviewAfterMinutes} onReviewAfter={setReviewAfterMinutes} />
      </aside>

      <div id="activity-brief" className="order-1 flex min-h-0 min-w-0 flex-col gap-3 lg:order-2 lg:h-full">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><Activity className="h-5 w-5 text-teal-600" />Daily Sales Activity</h2>
            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500">{dayLabel} · Cambodia time
              {data && data.date !== data.today && <><span className="rounded bg-slate-100 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-slate-500">Historical</span><button className="font-semibold text-teal-700" onClick={() => changeDay(data.today)}>Today</button></>}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <button className="rounded border bg-white p-1.5 text-slate-500 lg:hidden" aria-label="Show drop notifications" onClick={() => document.getElementById("daily-rm-panel")?.scrollIntoView({ behavior: "smooth" })}><Bell className="h-3.5 w-3.5" /></button>
            <button aria-label="Previous report date" disabled={!data || selectedDateIndex >= data.available_dates.length - 1 || selectedDateIndex < 0}
              onClick={() => changeDay(data!.available_dates[selectedDateIndex + 1])} className="rounded border bg-white p-1.5 disabled:opacity-30"><ChevronLeft className="h-3.5 w-3.5" /></button>
            <input aria-label="Report date" type="date" value={selectedDay} onChange={(event) => changeDay(event.target.value)}
              className="rounded border border-slate-200 bg-white px-2 py-1.5 text-[11px]" />
            <button aria-label="Next report date" disabled={!data || selectedDateIndex <= 0} onClick={() => changeDay(data!.available_dates[selectedDateIndex - 1])}
              className="rounded border bg-white p-1.5 disabled:opacity-30"><ChevronRight className="h-3.5 w-3.5" /></button>
            <button onClick={() => setRefreshVersion((value) => value + 1)} disabled={isLoading} title="Refresh activity" aria-label="Refresh activity"
              className="rounded border border-slate-200 bg-white p-1.5"><RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} /></button>
          </div>
        </div>

        {(offline || data?.source_status.state === "error") && <p role="status" className="shrink-0 rounded border border-amber-200 bg-amber-50 px-3 py-1.5 text-[10px] text-amber-800">{offline ? "Dashboard request failed or took too long. Showing saved activity; retrying automatically." : "Google Sheets could not be checked. Showing saved activity; retrying automatically."}</p>}

        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-1">
            {([{ id: "map", label: "Movement map", icon: MapPin }, { id: "rhythm", label: "Daily rhythm", icon: BarChart3 }, { id: "timeline", label: "RM timeline", icon: ListOrdered }] as const).map((item) =>
              <button key={item.id} aria-pressed={panel === item.id} onClick={() => setPanel(item.id)} className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-[10px] font-semibold ${panel === item.id ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-50"}`}><item.icon className="h-3 w-3" />{item.label}</button>)}
          </div>
          <div className="flex items-center gap-1.5"><SlidersHorizontal className="h-3 w-3 text-slate-400" />
            <select aria-label="Optional gap threshold" value={threshold} onChange={(event) => { setThreshold(event.target.value); if (!event.target.value && filter === "flagged") setFilter("all"); }}
              className="max-w-44 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[10px]"><option value="">Show gaps only</option><option value="15">Flag gaps over 15 min</option><option value="30">Flag gaps over 30 min</option><option value="60">Flag gaps over 60 min</option><option value="90">Flag gaps over 90 min</option></select>
          </div>
        </div>

        <div className="min-h-[640px] min-w-0 flex-1 lg:min-h-0" data-testid="activity-main-panel">
          {panel === "map" && <SalesMovementMap fillHeight showLegend={false} date={selectedDay} selectedId={selectedId} selectedName={selected?.sender_name}
            focusPointId={focusedDropId} onSelectSender={chooseSender} allowedSenderIds={visibleSenderIds}
            followLatest={followLatest} onFollowPoint={followPoint}
            onClearFocus={() => setFocusedDropId(null)} refreshVersion={refreshVersion} />}
          {panel === "rhythm" && <div className="h-full overflow-y-auto"><SalesCadenceChart senders={visible} selectedId={selectedId} thresholdMinutes={thresholdMinutes} onSelect={chooseSender} /></div>}
          {panel === "timeline" && <div className="h-full overflow-y-auto">
        <section id="sender-drop-timeline" className="min-w-0 rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
          <div className="border-b p-4">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Selected salesperson</p>
            <h3 className="flex items-center gap-2 font-semibold text-slate-900">{selected && <span className="h-3 w-3 rounded-full" style={{ backgroundColor: selected.color }} />}{selected?.sender_name || "Select a salesperson"}</h3>
            {selected && <div className="mt-2"><StartBadge sender={selected} /></div>}
            <p className="mt-1 text-xs text-slate-500">Drops in time order, with the elapsed time since the previous drop.</p>
            {selected && <p className="mt-1 text-[11px] text-slate-400">Last observed report: {new Date(selected.latest_observed_drop_at).toLocaleString("en-GB", { timeZone: "Asia/Phnom_Penh" })}</p>}
          </div>
          {selected && <div className="grid grid-cols-3 gap-px border-b border-slate-100 bg-slate-100">
            {[["Drops", String(selected.drop_count)], ["Typical gap", duration(selected.median_gap_seconds)], ["GPS drops", String(selected.gps_count)]].map(([label, value]) => <div key={label} className="bg-white px-4 py-3">
              <p className="text-[10px] text-slate-400">{label}</p><p className="mt-1 font-mono text-sm font-bold text-slate-800">{value}</p>
            </div>)}
          </div>}
          {detail && <div className="border-b bg-slate-50 px-4 py-3">
            <p className="mb-2 text-[10px] font-semibold uppercase text-slate-500">14-day submission history · click a day</p>
            <div className="flex h-12 items-end gap-1">{detail.daily_history.map((item) =>
              <button key={item.date} title={`${item.date}: ${item.drop_count} drops`} onClick={() => changeDay(item.date)}
                className="flex-1 min-h-[3px] rounded-t transition-opacity hover:opacity-100"
                style={{ height: `${Math.max(5, item.drop_count / maxDay * 100)}%`, backgroundColor: chartColor, opacity: item.drop_count ? item.date === selectedDay ? 1 : .4 : .1 }} aria-label={`View ${item.date}, ${item.drop_count} drops`} />
            )}</div>
          </div>}
          <div className="overflow-y-auto divide-y divide-slate-100">
            {detail?.drops.map((drop, index) => <div key={drop.id} className={`relative border-l-[3px] p-4 ${focusedDropId === drop.id ? "bg-slate-50" : ""}`} style={{ borderLeftColor: drop.above_threshold ? "#f59e0b" : chartColor }}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-slate-500">{localTime(drop.submitted_at)} · Drop {detail.offset + index + 1}</span>
                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${drop.above_threshold ? "bg-amber-100 text-amber-800" : drop.overnight_gap ? "bg-slate-100 text-slate-500" : "bg-emerald-50 text-emerald-700"}`}>
                  {drop.gap_seconds === null ? "First observed drop" : `${duration(drop.gap_seconds)} gap${drop.overnight_gap ? " · across dates" : ""}`}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-sm text-slate-800">{drop.merchant_name}</div>
                {!!drop.has_gps && <button onClick={() => {
                  setFocusedDropId(drop.id);
                  setPanel("map");
                  window.requestAnimationFrame(() => document.getElementById("sales-movement-map")?.scrollIntoView({ behavior: "smooth", block: "center" }));
                }} className="inline-flex shrink-0 items-center gap-1 rounded border px-2 py-1 text-[10px] text-slate-600"><MapPin className="h-3 w-3" />Locate</button>}
              </div>
              <div className="mt-1 text-xs text-slate-500">{drop.business || "Report submission"} · {drop.has_gps ? "GPS supplied" : "GPS missing"} · {drop.has_image ? "Photo supplied" : "No photo recorded"}</div>
              {drop.remark && <p className="mt-1 text-xs text-slate-500 line-clamp-2">{drop.remark}</p>}
            </div>)}
            {detail && !detail.drops.length && <p className="p-8 text-center text-sm text-slate-500">No drops from this sender on {selectedDay}.</p>}
            {!detail && <p className="p-8 text-center text-sm text-slate-500">{selectedId === null ? "Choose a sender to see drop intervals." : "Loading drop timeline…"}</p>}
          </div>
          {detail && detail.total > 100 && <div className="flex items-center justify-between border-t p-3 text-xs">
            <button disabled={page === 0} onClick={() => setPage((previous) => previous - 1)} className="rounded border px-3 py-1 disabled:opacity-30">Previous</button>
            <span>{detail.offset + 1}–{Math.min(detail.offset + detail.limit, detail.total)} of {detail.total}</span>
            <button disabled={!detail.has_more} onClick={() => setPage((previous) => previous + 1)} className="rounded border px-3 py-1 disabled:opacity-30">Next</button>
          </div>}
        </section>
          </div>}
        </div>
        <p className="flex shrink-0 flex-wrap items-center justify-between gap-1 text-[9px] text-slate-400">
          <span className="inline-flex items-center gap-1"><Radio className={`h-2.5 w-2.5 ${sourceReady ? "text-teal-500" : "text-amber-500"}`} />Dashboard checked {lastUpdated ? reportTimeLabel(lastUpdated) : "—"} · polls every 15s · Sheet {data?.source_status.state === "refreshing" ? "checking…" : sheetChecked ? `checked ${reportTimeLabel(new Date(sheetChecked))}` : "waiting for check"} · sheet checks every {sheetInterval}s · {gpsShare}% GPS in view</span>
          <span>Late Drop = first report after 09:30. Gaps measure reporting time.</span>
        </p>
      </div>
    </div>
  );
};
