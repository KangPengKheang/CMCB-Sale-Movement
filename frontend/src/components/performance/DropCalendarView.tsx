import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarDays, RefreshCw, Search, Sparkles } from "lucide-react";
import { fetchActivityCalendar } from "../../services/api";
import { startAutoRefresh } from "../../services/autoRefresh";
import type { ActivityCalendar } from "../../types";

const number = (value: number) => value.toLocaleString();
const formatDay = (value: string, options: Intl.DateTimeFormatOptions) =>
  new Date(value + "T12:00:00+07:00").toLocaleDateString("en-GB", { timeZone: "Asia/Phnom_Penh", ...options });
const shortDate = (value: string) => formatDay(value, { day: "numeric", month: "short" });
const heat = (value: number) => value === 0 ? "bg-slate-100 text-slate-400" : value <= 2 ? "bg-sky-100 text-sky-800" : value <= 5 ? "bg-teal-200 text-teal-950" : value <= 9 ? "bg-violet-400 text-white" : "bg-fuchsia-600 text-white";
const weekStyles = [
  { head: "bg-violet-50 text-violet-800", cell: "bg-violet-50/60 text-violet-950", bar: "bg-violet-500" },
  { head: "bg-sky-50 text-sky-800", cell: "bg-sky-50/60 text-sky-950", bar: "bg-sky-500" },
  { head: "bg-teal-50 text-teal-800", cell: "bg-teal-50/60 text-teal-950", bar: "bg-teal-500" },
  { head: "bg-amber-50 text-amber-800", cell: "bg-amber-50/60 text-amber-950", bar: "bg-amber-500" },
];

export function DropCalendarView() {
  const [data, setData] = useState<ActivityCalendar | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("cases");
  const [includeZero, setIncludeZero] = useState(true);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const positioned = useRef(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    const stop = startAutoRefresh(async () => {
      const result = await fetchActivityCalendar();
      if (!alive) return;
      setLoading(false);
      setFailed(!result);
      if (result) { setData(result); setCheckedAt(new Date()); }
    });
    return () => { alive = false; stop(); };
  }, [version]);

  useEffect(() => {
    if (data && scroller.current && !positioned.current) {
      // Start with the weekly totals; the day strip is available by scrolling right.
      scroller.current.scrollLeft = 0;
      positioned.current = true;
    }
  }, [data]);

  const rows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return (data?.senders || []).filter((person) =>
      (includeZero || person.total_cases > 0) &&
      (!query || person.sender_name.toLocaleLowerCase().includes(query) || String(person.sender_id).includes(query))
    ).sort((a, b) => sort === "name"
      ? a.sender_name.localeCompare(b.sender_name) || a.sender_id - b.sender_id
      : sort === "week" ? b.weekly_counts[0] - a.weekly_counts[0] || b.total_cases - a.total_cases || a.sender_name.localeCompare(b.sender_name)
      : b.total_cases - a.total_cases || a.sender_name.localeCompare(b.sender_name));
  }, [data, search, includeZero, sort]);
  const dailyTotals = data?.days.map((_, index) => rows.reduce((sum, person) => sum + person.daily_counts[index], 0)) || [];
  const weeklyTotals = data?.weeks.map((_, index) => rows.reduce((sum, person) => sum + person.weekly_counts[index], 0)) || [];
  const total = rows.reduce((sum, person) => sum + person.total_cases, 0);
  const weekMax = data?.weeks.map((_, index) => Math.max(1, ...rows.map((person) => person.weekly_counts[index]))) || [];
  const scrollTo = (end: boolean) => scroller.current?.scrollTo({ left: end ? scroller.current.scrollWidth : 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });

  return <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto bg-slate-50 p-3 sm:p-5">
    <section className="relative shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-950 via-indigo-950 to-violet-900 p-5 text-white shadow-lg shadow-indigo-950/10 sm:p-6">
      <div aria-hidden="true" className="pointer-events-none absolute -right-12 -top-24 h-72 w-72 rounded-full border-[35px] border-cyan-300/10" />
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-white/20 bg-white/10"><CalendarDays className="h-6 w-6 text-cyan-200" /></span>
          <div><p className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[.18em] text-cyan-200"><Sparkles className="h-3 w-3" />Every case counts</p>
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">Drop Calendar</h2>
            <p className="mt-1 text-xs leading-5 text-indigo-200">Your team's case drops, week by week and day by day.</p></div>
        </div>
        <div className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-xs">
          <p className="font-semibold">{data ? shortDate(data.days[0]) + " – " + shortDate(data.today) : "Last 30 days"}</p>
          <p className="mt-1 text-[10px] text-indigo-200">Cambodia time · Weeks start Monday</p>
        </div>
      </div>
    </section>

    {failed && <p role="status" className="shrink-0 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">{data ? "Could not refresh the table. Showing the last loaded counts; retrying automatically." : "Could not load case counts. Check the backend connection, then try Refresh."}</p>}

    <section className="flex min-h-[620px] flex-1 flex-col overflow-hidden rounded-2xl sm:min-h-[480px] lg:min-h-[360px] border border-slate-200 bg-white shadow-sm" aria-label="Weekly and daily case drop counts" aria-busy={loading}>
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div><h3 className="text-sm font-bold text-slate-900">The team's drop board</h3><p className="mt-1 text-[11px] text-slate-500">Each number is a case dropped. Scroll right for all 30 days.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative"><Search aria-hidden="true" className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" /><input aria-label="Search salesperson by name or ID" placeholder="Find a name or ID…" value={search} onChange={(event) => setSearch(event.target.value)} className="w-44 rounded-lg border border-slate-200 py-2 pl-8 pr-2 text-xs outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100" /></div>
          <select aria-label="Sort case drop table" value={sort} onChange={(event) => setSort(event.target.value)} className="rounded-lg border border-slate-200 bg-white p-2 text-xs"><option value="cases">Most cases · 30 days</option><option value="week">Most cases · this week</option><option value="name">Name A–Z</option></select>
          <button onClick={() => setVersion((value) => value + 1)} disabled={loading} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-800 disabled:opacity-50"><RefreshCw className={"h-3.5 w-3.5 " + (loading ? "animate-spin" : "")} />Refresh</button>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 text-[11px]">
        <label className="inline-flex items-center gap-2 text-slate-600"><input type="checkbox" checked={includeZero} onChange={(event) => setIncludeZero(event.target.checked)} className="accent-violet-600" />Include people with zero cases</label>
        <div className="flex items-center gap-2"><span className="mr-1 text-slate-400">{rows.length} people</span>
          <button onClick={() => scrollTo(false)} aria-label="Scroll to weekly totals" className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1.5 font-semibold text-slate-600 hover:border-violet-300"><ArrowLeft className="h-3 w-3" />Weeks</button>
          <button onClick={() => scrollTo(true)} aria-label="Scroll to today's case counts" className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-violet-50 px-2 py-1.5 font-semibold text-violet-700 hover:bg-violet-100">Today<ArrowRight className="h-3 w-3" /></button>
        </div>
      </div>
      {!data ? <div role="status" className="grid flex-1 place-items-center p-10 text-sm text-slate-500">{loading ? "Loading the team's case drops…" : "Case counts are unavailable. Use Refresh to retry."}</div> :
      <div ref={scroller} tabIndex={0} aria-label="Scrollable case counts table; use arrow keys to scroll" className="drop-calendar-scroll relative min-h-0 flex-1 overflow-auto focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-500">
        <table className="w-max min-w-full border-separate border-spacing-0 text-xs">
          <caption className="sr-only">Case drops by salesperson. Four Monday-to-Sunday weekly totals and 30 daily counts ending today. Current week counts through today. Zero means no observed case drops.</caption>
          <thead>
            <tr className="h-9 text-[10px] font-bold uppercase tracking-wider">
              <th rowSpan={2} scope="col" className="sticky left-0 top-0 z-40 min-w-[170px] border-b border-r border-slate-200 bg-white px-4 text-left text-slate-500 sm:min-w-[210px]">Salesperson<span className="mt-1 block text-[9px] font-normal normal-case tracking-normal text-slate-400">Cases dropped, including without GPS</span></th>
              <th colSpan={4} scope="colgroup" className="sticky top-0 z-20 border-b border-r border-violet-100 bg-violet-100/95 px-3 text-left text-violet-800">04 weeks <span className="ml-2 font-normal normal-case tracking-normal">Current + previous 3</span></th>
              <th colSpan={30} scope="colgroup" className="sticky top-0 z-20 border-b border-cyan-100 bg-cyan-50 px-3 text-left text-cyan-800">30 days <span className="ml-2 font-normal normal-case tracking-normal">{shortDate(data.days[0])} – {shortDate(data.today)} · scroll to explore →</span></th>
              <th rowSpan={2} scope="col" className="sticky top-0 z-20 min-w-24 border-b border-l border-slate-200 bg-slate-900 px-3 text-white">30-day<br />total</th>
            </tr>
            <tr className="h-16">
              {data.weeks.map((week, index) => <th key={week.start} scope="col" className={"sticky top-9 z-20 min-w-[108px] border-b border-r border-slate-200 px-3 text-left " + weekStyles[index].head}>
                <span className="block text-[11px] font-bold">{week.label}</span><span className="mt-1 block text-[9px] font-medium opacity-75">{shortDate(week.start)} – {shortDate(week.current ? data.today : week.end)}</span>
                {week.current && <span className="mt-0.5 block text-[8px] font-semibold uppercase tracking-wide">So far</span>}
              </th>)}
              {data.days.map((day) => {
                const today = day === data.today;
                const weekend = [0, 6].includes(new Date(day + "T12:00:00+07:00").getUTCDay());
                return <th key={day} scope="col" aria-current={today ? "date" : undefined} className={"sticky top-9 z-20 min-w-[58px] border-b border-r border-slate-100 px-1 text-center " + (today ? "bg-violet-100 text-violet-800" : weekend ? "bg-slate-100 text-slate-500" : "bg-white text-slate-600")}>
                  <span className="block text-[9px] font-medium">{today ? "TODAY" : formatDay(day, { weekday: "short" })}</span><span className="mt-1 block text-base font-bold leading-none">{day.slice(8)}</span><span className="mt-1 block text-[8px] font-medium">{formatDay(day, { month: "short" })}</span>
                </th>;
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((person, index) => <tr key={person.sender_id} className="group">
              <th scope="row" className="sticky left-0 z-10 border-b border-r border-slate-200 bg-white px-3 py-3 text-left group-hover:bg-violet-50">
                <div className="flex items-center gap-2.5"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl text-[10px] font-bold text-white" style={{ backgroundColor: person.color }}>{person.sender_name.trim().split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase()}</span>
                  <div className="min-w-0"><span className="block max-w-[116px] truncate font-semibold text-slate-800 sm:max-w-[154px]" title={person.sender_name}>{person.sender_name}</span><span className="mt-1 block text-[9px] font-normal text-slate-400">{person.active_days} active days · #{index + 1}</span></div>
                </div>
              </th>
              {person.weekly_counts.map((count, week) => <td key={week} className={"border-b border-r border-slate-100 px-3 py-2 " + weekStyles[week].cell} title={person.sender_name + ": " + number(count) + " cases · " + data.weeks[week].label}>
                <span className="text-lg font-bold tabular-nums">{number(count)}</span><div aria-hidden="true" className="mt-1 h-1 w-full rounded-full bg-white"><div className={"h-1 rounded-full " + weekStyles[week].bar} style={{ width: (count / weekMax[week] * 100) + "%" }} /></div>
              </td>)}
              {person.daily_counts.map((count, index) => <td key={data.days[index]} className={"border-b border-r border-slate-100 p-1.5 " + (data.days[index] === data.today ? "bg-violet-50/60" : "group-hover:bg-slate-50")} title={person.sender_name + " · " + shortDate(data.days[index]) + ": " + number(count) + " cases"}>
                <span className={"grid h-9 min-w-9 place-items-center rounded-lg text-xs font-bold tabular-nums " + heat(count)}>{number(count)}</span>
              </td>)}
              <td className="border-b border-l border-slate-100 bg-slate-50 px-4 text-center text-base font-extrabold tabular-nums text-slate-800">{number(person.total_cases)}</td>
            </tr>)}
            {!rows.length && <tr><td colSpan={36} className="p-8 text-left text-sm text-slate-500">{search ? "No people match your search." : "No case drops found for these filters."}</td></tr>}
          </tbody>
          <tfoot><tr className="font-bold">
            <th scope="row" className="sticky bottom-0 left-0 z-30 border-r border-t border-slate-200 bg-slate-900 px-4 py-3 text-left text-white">Team total<span className="mt-1 block text-[9px] font-normal text-slate-300">For the people shown</span></th>
            {weeklyTotals.map((total, index) => <td key={index} className={"sticky bottom-0 z-20 border-r border-t border-slate-200 px-3 py-3 text-base tabular-nums " + weekStyles[index].head}>{number(total)}</td>)}
            {dailyTotals.map((total, index) => <td key={index} className="sticky bottom-0 z-20 border-r border-t border-slate-200 bg-slate-100 px-1 py-3 text-center tabular-nums text-slate-700">{number(total)}</td>)}
            <td className="sticky bottom-0 z-20 border-l border-t border-slate-200 bg-slate-900 px-4 text-center text-base tabular-nums text-white">{number(total)}</td>
          </tr></tfoot>
        </table>
      </div>}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500"><span className="mr-1 font-semibold">Cases / day</span>{[{ value: 0, label: "0" }, { value: 1, label: "1–2" }, { value: 3, label: "3–5" }, { value: 6, label: "6–9" }, { value: 10, label: "10+" }].map((step) => <span key={step.value} className="inline-flex items-center gap-1"><span className={"h-3 w-3 rounded " + heat(step.value)} />{step.label}</span>)}</div>
        <span className="text-[10px] text-slate-400">{checkedAt ? "Updated " + checkedAt.toLocaleTimeString("en-GB", { timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "Waiting for data"} · refreshes every 15s</span>
      </div>
    </section>
    <p className="shrink-0 text-[10px] leading-4 text-slate-500">One recorded case drop counts once. Counts include cases without GPS and follow your account's channel access. Zero means no recorded drops; it does not indicate absence. Weekly and daily columns overlap—do not add them together.</p>
  </div>;
}
