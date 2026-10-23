import { startAutoRefresh } from "../../services/autoRefresh";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Pane, useMap } from "react-leaflet";
import L from "leaflet";
import { LocateFixed, MapPin, Users, Play, Pause, RotateCcw, Maximize2, Minimize2, Route } from "lucide-react";
import { MapCanvas } from "../map/MapCanvas";
import { fetchMovementRoutes } from "../../services/api";
import type { SalesMovementRoutes } from "../../types";
import { SalesRouteLayers, routeColors } from "./SalesRouteLayers";

const clock = (timestamp: string) => new Date(timestamp).toLocaleTimeString("en-GB", {
  timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit",
});
function MovementViewport({ routes, selectedId, onlySelected, focusPointId, followLatest, fitVersion, onPopupChange }: {
  routes: SalesMovementRoutes | null;
  selectedId: number | null;
  onlySelected: boolean;
  focusPointId: number | null;
  followLatest: boolean;
  fitVersion: number;
  onPopupChange: (open: boolean) => void;
}) {
  const map = useMap();
  const lastFit = useRef("");
  useEffect(() => {
    const opened = () => onPopupChange(true);
    const closed = () => onPopupChange(false);
    map.on("popupopen", opened);
    map.on("popupclose", closed);
    return () => { map.off("popupopen", opened); map.off("popupclose", closed); };
  }, [map, onPopupChange]);
  const [layoutVersion, setLayoutVersion] = useState(0);
  useEffect(() => {
    let frame = 0;
    let lastSize = "";
    const observer = new ResizeObserver(([entry]) => {
      const size = `${Math.round(entry.contentRect.width)}:${Math.round(entry.contentRect.height)}`;
      if (size === lastSize || !entry.contentRect.width || !entry.contentRect.height) return;
      lastSize = size;
      map.getContainer().style.setProperty("--drop-popup-max-height", `${Math.max(180, Math.floor(entry.contentRect.height) - 64)}px`);
      map.getContainer().style.setProperty("--drop-popup-width", `${Math.max(220, Math.floor(entry.contentRect.width) - 56)}px`);
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        map.invalidateSize({ pan: false });
        setLayoutVersion((previous) => previous + 1);
      });
    });
    observer.observe(map.getContainer());
    return () => { observer.disconnect(); window.cancelAnimationFrame(frame); };
  }, [map]);
  useEffect(() => {
    if (!routes) return;
    const key = `${routes.date}:${routes.tracks.map((track) => track.sender_id).join(",")}:${onlySelected ? selectedId : "all"}:${focusPointId}:${followLatest}:${fitVersion}:${layoutVersion}`;
    if (lastFit.current === key) return;
    const focus = focusPointId === null ? null : routes.tracks
      .flatMap((track) => track.points).find((point) => point.id === focusPointId);
    const points = routes.tracks
      .filter((track) => !onlySelected || track.sender_id === selectedId)
      .flatMap((track) => track.points);
    if (!focus && points.length === 0) return;
    lastFit.current = key;
    map.invalidateSize();
    if (focus && !followLatest) {
      map.flyTo([focus.latitude, focus.longitude], 17, { duration: 0.8, animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches });
    } else if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], 15, { animate: false });
    } else if (points.length > 1) {
      map.flyToBounds(L.latLngBounds(points.map((point) => [point.latitude, point.longitude] as [number, number])), {
        paddingTopLeft: [55, 55], paddingBottomRight: [45, 125], maxZoom: onlySelected ? 17 : 15,
        duration: 0.8,
        animate: followLatest && !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      });
    }
  }, [map, routes, selectedId, onlySelected, focusPointId, followLatest, fitVersion, layoutVersion]);
  return null;
}

export const SalesMovementMap: React.FC<{
  date: string;
  selectedId: number | null;
  selectedName?: string;
  allowedSenderIds?: number[];
  focusPointId: number | null;
  onSelectSender: (id: number) => void;
  onClearFocus: () => void;
  refreshVersion?: number;
  followLatest?: boolean;
  onFollowPoint?: (senderId: number, pointId: number) => void;
  fillHeight?: boolean;
  showLegend?: boolean;
}> = ({ date, selectedId, selectedName, allowedSenderIds, focusPointId, onSelectSender, onClearFocus, refreshVersion = 0, followLatest = false, onFollowPoint, fillHeight = false, showLegend = true }) => {
  const [allRoutes, setRoutes] = useState<SalesMovementRoutes | null>(null);
  const [popupPointId, setPopupPointId] = useState<number | null>(null);
  const [popupVisible, setPopupVisible] = useState(false);
  useEffect(() => {
    if (popupPointId !== null && !allRoutes?.tracks.some(track =>
      track.sender_id === selectedId && track.points.some(point => point.id === popupPointId)
    )) setPopupPointId(null);
  }, [selectedId, allRoutes, popupPointId]);
  const scopeKey = allowedSenderIds?.join(",") ?? "*";
  const routes = useMemo(() => {
    if (!allRoutes) return null;
    const allowed = allowedSenderIds ? new Set(allowedSenderIds) : null;
    const tracks = allRoutes.tracks.filter((track) => !allowed || allowed.has(track.sender_id));
    return { ...allRoutes, tracks, sender_count: tracks.length };
  }, [allRoutes, scopeKey]);

  const [failed, setFailed] = useState(false);
  const [onlySelected, setOnlySelected] = useState(true);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!expanded) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [expanded]);
  const [fitVersion, setFitVersion] = useState(0);
  const [search, setSearch] = useState("");
  const [playbackIndex, setPlaybackIndex] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  useEffect(() => {
    let alive = true;
    setRoutes(null);
    setFailed(false);
    if (!date) return;
    const load = async () => {
      const response = await fetchMovementRoutes(date);
      if (!alive) return;
      if (response) { setRoutes(response); setFailed(false); }
      else setFailed(true);
    };
    const stop = startAutoRefresh(load);
    return () => { alive = false; stop(); };
  }, [date, refreshVersion]);
  const selectedTrack = routes?.tracks.find((track) => track.sender_id === selectedId);
  const replayCount = selectedTrack?.points.length ?? 0;
  const lastFollowed = useRef("");
  useEffect(() => {
    if (!followLatest) { lastFollowed.current = ""; return; }
    if (!routes || !onFollowPoint) return;
    let latest: { senderId: number; id: number; submittedAt: string } | null = null;
    for (const track of routes.tracks) {
      for (const point of track.points) {
        if (!latest || point.submitted_at > latest.submittedAt ||
            (point.submitted_at === latest.submittedAt && point.id > latest.id)) {
          latest = { senderId: track.sender_id, id: point.id, submittedAt: point.submitted_at };
        }
      }
    }
    if (!latest) return;
    const key = routes.date + ":" + scopeKey + ":" + latest.id;
    if (lastFollowed.current === key) return;
    lastFollowed.current = key;
    setOnlySelected(true); setPlaybackIndex(null); setIsPlaying(false);
    onFollowPoint(latest.senderId, latest.id);
  }, [followLatest, routes, scopeKey, onFollowPoint]);
  useEffect(() => { setPlaybackIndex(null); setIsPlaying(false); }, [date, selectedId]);
  useEffect(() => {
    if (focusPointId !== null) { setOnlySelected(true); setPlaybackIndex(null); setIsPlaying(false); }
  }, [focusPointId]);
  useEffect(() => {
    if (!isPlaying || replayCount < 2) return;
    const timer = window.setInterval(() => setPlaybackIndex((previous) => Math.min((previous ?? 0) + 1, replayCount - 1)), 1200);
    return () => window.clearInterval(timer);
  }, [isPlaying, replayCount]);
  useEffect(() => {
    if (playbackIndex !== null && playbackIndex >= replayCount - 1) setIsPlaying(false);
  }, [playbackIndex, replayCount]);
  const replayPoint = playbackIndex === null ? null : selectedTrack?.points[playbackIndex];
  const toggleReplay = () => {
    if (isPlaying) { setIsPlaying(false); return; }
    onClearFocus();
    setOnlySelected(true);
    setPlaybackIndex((previous) => previous === null || previous >= replayCount - 1 ? 0 : previous);
    setIsPlaying(true);
    setFitVersion((previous) => previous + 1);
  };

  const tracks = routes?.tracks.filter((track) => !onlySelected || track.sender_id === selectedId) || [];
  const ordered = [...tracks.filter((track) => track.sender_id !== selectedId), ...tracks.filter((track) => track.sender_id === selectedId)]
    .map((track) => track.sender_id === selectedId && playbackIndex !== null ? {
      ...track, points: track.points.slice(0, playbackIndex + 1), segments: track.segments.slice(0, playbackIndex),
    } : track);
  const legend = routes?.tracks.filter((track) => `${track.sender_name} ${track.sender_id}`.toLowerCase().includes(search.toLowerCase().trim())) || [];
  const choose = (id: number) => {
    setPlaybackIndex(null); setIsPlaying(false);
    onClearFocus();
    onSelectSender(id);
    setOnlySelected(true);
    setFitVersion((previous) => previous + 1);
  };
  const showAll = () => {
    setPlaybackIndex(null); setIsPlaying(false);
    onClearFocus();
    setOnlySelected(false);
    setFitVersion((previous) => previous + 1);
  };

  const effectiveFill = fillHeight || expanded;
  return <section id="sales-movement-map" className={`sales-movement-view overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${expanded ? "fixed inset-3 z-[900] flex min-h-0 flex-col shadow-2xl" : fillHeight ? "flex h-full min-h-0 flex-col" : ""}`}>
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-teal-50 text-teal-700"><Route className="h-4 w-4" /></span>
        <div><h3 className="text-sm font-bold text-slate-900">Sales movement</h3><p className="text-[9px] text-slate-400">Follow the trail · every point is a reported stop</p></div>
      </div>
      <div className="flex items-center gap-1">
        <div role="group" aria-label="Map salesperson scope" data-testid="map-scope-slider" className="relative isolate grid grid-cols-2 overflow-hidden rounded-full border border-cyan-100 bg-gradient-to-r from-slate-50 to-cyan-50 p-1 text-[10px] shadow-inner">
          <span aria-hidden="true" data-testid="map-scope-highlight" className={`pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-4px)] rounded-full bg-gradient-to-r shadow-md ring-1 ring-inset ring-white/20 transition-transform duration-300 ease-out motion-reduce:transition-none ${onlySelected ? "translate-x-full from-indigo-600 to-violet-600 shadow-indigo-500/25" : "translate-x-0 from-teal-600 to-cyan-700 shadow-teal-600/25"}`} />
          <button aria-pressed={!onlySelected} onClick={showAll} className={`relative z-10 flex items-center justify-center gap-1 whitespace-nowrap rounded-full px-3 py-2 font-semibold transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-teal-800 motion-reduce:transition-none ${!onlySelected ? "text-white" : "text-slate-600 hover:text-teal-800"}`}><Users className="h-3 w-3" />All salespeople</button>
          <button aria-pressed={onlySelected} disabled={selectedId === null} onClick={() => { onClearFocus(); setPlaybackIndex(null); setIsPlaying(false); setOnlySelected(true); setFitVersion((previous) => previous + 1); }}
            className={`relative z-10 whitespace-nowrap rounded-full px-3 py-2 font-semibold transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-indigo-800 disabled:opacity-30 motion-reduce:transition-none ${onlySelected ? "text-white" : "text-slate-600 hover:text-indigo-800"}`}>Selected only</button>
        </div>
        <button title="Fit visible routes" aria-label="Fit visible routes" onClick={() => { onClearFocus(); setFitVersion((previous) => previous + 1); }} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><LocateFixed className="h-4 w-4" /></button>
        <button title={expanded ? "Collapse map · Esc" : "Expand map"} aria-label={expanded ? "Collapse map" : "Expand map"} aria-expanded={expanded} onClick={() => setExpanded((previous) => !previous)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100">{expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
      </div>
    </div>
    <div className={`grid ${showLegend ? "lg:grid-cols-[minmax(0,1fr)_220px]" : ""} ${effectiveFill ? "min-h-0 flex-1" : ""}`}>
      <div className={`relative isolate min-w-0 ${effectiveFill ? "h-full min-h-[300px] lg:min-h-0" : "h-[540px]"}`}>
        <MapCanvas zoom={12} restrictToCambodia={false} showZoomControls>
          <MovementViewport routes={routes} selectedId={selectedId} onlySelected={onlySelected} focusPointId={focusPointId} followLatest={followLatest} fitVersion={fitVersion} onPopupChange={setPopupVisible} />
          <Pane name="sales-route-casing" style={{ zIndex: 410 }} />
          <Pane name="sales-route-lines" style={{ zIndex: 420 }} />
          <Pane name="sales-route-directions" style={{ zIndex: 430 }} />
          <Pane name="sales-route-points" style={{ zIndex: 450 }} />
          <Pane name="sales-selected-points" style={{ zIndex: 470 }} />
          {ordered.map((track) => <SalesRouteLayers key={`${track.sender_id}:${track.sender_id === selectedId ? "selected" : "team"}`} track={track} selected={track.sender_id === selectedId} onSelect={onSelectSender} replaying={playbackIndex !== null}
            popupPointId={popupPointId} onSelectPoint={(id) => { setPopupPointId(id); onSelectSender(track.sender_id); }}
            />)}
        </MapCanvas>

        {selectedTrack && !popupVisible && <div className="absolute bottom-7 left-4 right-4 z-[500] mx-auto max-w-xl rounded-2xl border border-white/90 bg-white/95 p-3 shadow-lg backdrop-blur" data-testid="movement-replay-controls">
          <div className="flex items-center gap-2">
            <button disabled={replayCount < 2} onClick={toggleReplay} className="flex shrink-0 items-center gap-1.5 rounded-xl bg-slate-900 px-3 py-2 text-[10px] font-semibold text-white shadow-sm disabled:opacity-30">
              {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}{isPlaying ? "Pause" : "Replay drops"}
            </button>
            <input type="range" min={0} max={Math.max(0, replayCount - 1)} value={Math.min(playbackIndex ?? 0, Math.max(0, replayCount - 1))} disabled={replayCount < 2}
              aria-label="Replay GPS drops" aria-valuetext={replayPoint ? `Drop ${replayPoint.drop_number}, ${clock(replayPoint.submitted_at)}` : "Full route"}
              onChange={(event) => { onClearFocus(); setOnlySelected(true); setIsPlaying(false); setPlaybackIndex(Number(event.target.value)); }}
              className="min-w-0 flex-1 accent-teal-600" />
            <button onClick={() => { setPlaybackIndex(null); setIsPlaying(false); setFitVersion((previous) => previous + 1); }} title="Show full route" aria-label="Show full route" className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100"><RotateCcw className="h-3.5 w-3.5" /></button>
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-1 text-[9px] text-slate-400">
            <span className="font-mono font-semibold text-slate-600">{replayPoint ? `Visit #${replayPoint.drop_number} · ${clock(replayPoint.submitted_at)}` : `${clock(selectedTrack.points[0].submitted_at)} → ${clock(selectedTrack.points[replayCount - 1].submitted_at)}`}</span>
            <span>{playbackIndex !== null ? "One reported stop per step" : "Drag the slider or replay the reported stops"}</span>
          </div>
        </div>}
        {failed && routes && tracks.length > 0 && <div role="status" className="absolute left-4 top-16 z-[500] rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 shadow">Showing saved routes. Refresh will retry automatically.</div>}
        {(!routes || tracks.length === 0) && <div className="pointer-events-none absolute inset-x-6 bottom-14 z-[500] rounded-xl border border-slate-200 bg-white/95 px-4 py-4 text-center text-xs text-slate-600 shadow-lg">
          {failed ? "GPS trails could not be refreshed. Retrying automatically."
            : !routes ? "Loading GPS drop trails…"
            : allowedSenderIds?.length === 0 ? "No salespeople match the channel and sender filters."
            : onlySelected ? `${selectedName || "This salesperson"} has no GPS drops on this date.`
            : "No GPS drops are available for this date."}
        </div>}
      </div>
      {showLegend && <aside className="border-t bg-slate-50 lg:border-l lg:border-t-0">
        <div className="border-b px-3 py-3"><p className="text-xs font-semibold text-slate-800">{routes?.sender_count ?? 0} salespeople with GPS</p><input value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Find a salesperson on the map" placeholder="Find a salesperson" className="mt-2 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs" /></div>
        <div className="max-h-40 overflow-y-auto lg:max-h-[375px]">
          {legend.map((track) => <button key={track.sender_id} onClick={() => choose(track.sender_id)} className={`flex w-full items-center gap-2 border-b border-slate-100 px-3 py-2 text-left hover:bg-white ${selectedId === track.sender_id ? "bg-white" : ""}`}>
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: routeColors(track.color).point }} /><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold text-slate-800">{track.sender_name}</span><span className="text-[10px] text-slate-400">{track.points.length} GPS drops</span></span>
          </button>)}
        </div>
      </aside>}
    </div>
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-1 border-t border-slate-100 px-3 py-1.5 text-[9px] text-slate-400">
      <span>Dark points = reported stops · dashed trails = direction · dotted trails = intervening reports without GPS</span>
      <span>Connections are not a recorded road route.</span>
    </div>
  </section>
};
