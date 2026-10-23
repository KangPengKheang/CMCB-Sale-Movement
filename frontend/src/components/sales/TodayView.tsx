import React, { useMemo, useState, useEffect, useRef } from "react";
import { useSales } from "../../context/SalesContext";
import { MapCanvas } from "../map/MapCanvas";
import { Marker, Tooltip, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import {
  MapPin,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Flame,
  Activity,
  LocateFixed,
  Users,
  User,
  Clock,
  Sparkles,
  ExternalLink,
} from "lucide-react";

// Auto-camera controller matching Google Maps / Live Pulse behavior
const TodayMapCameraController: React.FC<{
  stops: Array<{ latitude: number; longitude: number }>;
  defaultCenter: [number, number];
  focusCoord?: [number, number] | null;
  recenterTrigger?: number;
}> = ({ stops, defaultCenter, focusCoord, recenterTrigger }) => {
  const map = useMap();
  const prevCountRef = useRef<number>(-1);
  const prevTriggerRef = useRef<number>(0);

  useEffect(() => {
    if (focusCoord) {
      map.flyTo(focusCoord, 16, { duration: 0.7 });
      return;
    }

    const triggerChanged = recenterTrigger && recenterTrigger !== prevTriggerRef.current;
    if (triggerChanged) {
      prevTriggerRef.current = recenterTrigger;
    } else if (prevCountRef.current === stops.length && stops.length > 0) {
      return;
    }

    prevCountRef.current = stops.length;

    if (stops.length === 0) {
      map.flyTo(defaultCenter, 13, { duration: 0.8 });
      return;
    }

    if (stops.length === 1) {
      map.flyTo([stops[0].latitude, stops[0].longitude], 15, { duration: 0.8 });
      return;
    }

    const latLngs = stops.map((s) => [s.latitude, s.longitude] as [number, number]);
    const bounds = L.latLngBounds(latLngs);
    map.flyToBounds(bounds, { padding: [60, 60], maxZoom: 16, duration: 0.8 });
  }, [stops, defaultCenter, focusCoord, recenterTrigger, map]);

  return null;
};

// Marker icon generator for stops with sequence number or initials and pulsing aura
const createTodayStopIcon = (label: string, stage: string, isTeammate = false) => {
  const isConverted = stage === "CONVERTED" || stage === "EXISTING";
  const bgColor = isConverted
    ? "#006B3F" // CMCB Emerald Green
    : stage === "PIPELINE"
    ? "#0284c7" // Pipeline Blue
    : isTeammate
    ? "#e11d48" // Rose / Crimson
    : "#006B3F";

  const size = isTeammate && label.length > 1 ? 32 : 30;
  const innerSize = isTeammate && label.length > 1 ? 24 : 22;
  const fontSize = isTeammate && label.length > 1 ? "10px" : "11px";

  return L.divIcon({
    className: "custom-today-stop-icon",
    html: `
      <div style="
        width: ${size}px;
        height: ${size}px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
      ">
        <span class="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping" style="background-color: ${bgColor}; animation-duration: 2.2s;"></span>
        <span class="relative flex items-center justify-center rounded-full border-2 border-white text-white font-mono font-black shadow-lg" style="
          width: ${innerSize}px;
          height: ${innerSize}px;
          font-size: ${fontSize};
          background-color: ${bgColor};
          box-shadow: 0 0 10px ${bgColor};
        ">${label}</span>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

type MapMode = "my" | "team" | "specific";
type SheetSnap = "peek" | "half" | "full";

export const TodayView: React.FC = () => {
  const { todayData, openMerchantDetail, setActiveSalesTab, dateOffset, setDateOffset } = useSales();

  const [mapMode, setMapMode] = useState<MapMode>("my");
  const [selectedTeammateId, setSelectedTeammateId] = useState<number | null>(null);
  const [focusedCoord, setFocusedCoord] = useState<[number, number] | null>(null);
  const [recenterCount, setRecenterCount] = useState<number>(0);
  const [sheetSnap, setSheetSnap] = useState<SheetSnap>("peek");

  const visits_today = useMemo(() => todayData?.visits_today || [], [todayData]);
  const team_activity = useMemo(() => todayData?.team_activity || [], [todayData]);
  const territory = todayData?.territory;

  const defaultCenter: [number, number] = useMemo(
    () => [territory?.center_latitude || 11.5564, territory?.center_longitude || 104.9282],
    [territory]
  );

  // Distinct teammates active today for the dropdown selector
  const teamRoster = useMemo(() => {
    const map = new Map<number, { rm_id: number; name: string; initials: string; count: number }>();
    team_activity.forEach((act) => {
      const id = act.rm_id || 0;
      if (!id) return;
      const existing = map.get(id);
      if (existing) {
        existing.count += 1;
      } else {
        map.set(id, {
          rm_id: id,
          name: act.rm_name,
          initials: act.rm_initials,
          count: 1,
        });
      }
    });
    return Array.from(map.values());
  }, [team_activity]);

  // Set default selected teammate if switching to specific mode and none is selected
  useEffect(() => {
    if (mapMode === "specific" && selectedTeammateId === null && teamRoster.length > 0) {
      setSelectedTeammateId(teamRoster[0].rm_id);
    }
  }, [mapMode, selectedTeammateId, teamRoster]);

  // Selected teammate metadata
  const selectedTeammate = useMemo(() => {
    if (!selectedTeammateId) return null;
    return teamRoster.find((t) => t.rm_id === selectedTeammateId) || null;
  }, [selectedTeammateId, teamRoster]);

  // Determine active stops to plot based on mode
  const displayedStops = useMemo(() => {
    // 1. My Visits (You)
    if (mapMode === "my") {
      return visits_today.map((v, idx) => ({
        id: v.id,
        merchant_id: v.merchant_id,
        name: v.name,
        latitude: v.latitude,
        longitude: v.longitude,
        time: v.time,
        outcome: v.outcome,
        stage: v.khqr_stage,
        district: v.district,
        remark: v.remark,
        label: String(idx + 1),
        is_teammate: false,
        rm_name: todayData?.rm_name || "You",
      }));
    }

    // 2. All Sales (Whole Team)
    if (mapMode === "team") {
      return team_activity.map((act) => ({
        id: act.id,
        merchant_id: act.merchant_id,
        name: act.merchant_name,
        latitude: act.latitude,
        longitude: act.longitude,
        time: act.time,
        outcome: act.status,
        stage: act.stage,
        district: act.district,
        remark: act.remark,
        label: act.rm_initials,
        is_teammate: true,
        rm_name: act.rm_name,
      }));
    }

    // 3. Specific Sales Rep
    const filtered = team_activity.filter((act) => act.rm_id === selectedTeammateId);
    const sorted = [...filtered].sort((a, b) => (a.time > b.time ? 1 : -1));
    return sorted.map((act, idx) => ({
      id: act.id,
      merchant_id: act.merchant_id,
      name: act.merchant_name,
      latitude: act.latitude,
      longitude: act.longitude,
      time: act.time,
      outcome: act.status,
      stage: act.stage,
      district: act.district,
      remark: act.remark,
      label: String(idx + 1),
      is_teammate: true,
      rm_name: act.rm_name,
    }));
  }, [mapMode, selectedTeammateId, visits_today, team_activity, todayData?.rm_name]);

  // Route path coords (only connect when displaying sequential route of one person)
  const routePoints: [number, number][] = useMemo(() => {
    if (mapMode === "my") {
      return visits_today.map((v) => [v.latitude, v.longitude] as [number, number]);
    }
    if (mapMode === "specific") {
      return displayedStops.map((s) => [s.latitude, s.longitude] as [number, number]);
    }
    return [];
  }, [mapMode, visits_today, displayedStops]);

  // Early Bird from team activity (matches Live Pulse)
  const earlyBird = useMemo(() => {
    if (team_activity.length === 0) return null;
    const sorted = [...team_activity].sort((a, b) => (a.time > b.time ? 1 : -1));
    return sorted[0];
  }, [team_activity]);

  // Latest activity item for ticker snippet in collapsed sheet
  const latestActivity = useMemo(() => {
    if (mapMode === "my") {
      return visits_today[0] || null;
    }
    if (mapMode === "specific") {
      const filtered = team_activity.filter((act) => act.rm_id === selectedTeammateId);
      return filtered[filtered.length - 1] || null;
    }
    return team_activity[team_activity.length - 1] || null;
  }, [mapMode, visits_today, team_activity, selectedTeammateId]);

  // Exact date formatted for the pill (e.g. "Today (8 Oct 2026)")
  const pillDateLabel = useMemo(() => {
    const targetTime = Date.now() - (dateOffset * 86400000);
    const d = new Date(targetTime);
    const day = d.getDate();
    const month = d.toLocaleDateString("en-US", { month: "short" });
    const year = d.getFullYear();
    const relative = dateOffset === 0 ? "Today" : dateOffset === 1 ? "Yesterday" : `-${dateOffset}d`;
    return `${relative} (${day} ${month} ${year})`;
  }, [dateOffset]);
  const handleRecenter = () => {
    setFocusedCoord(null);
    setRecenterCount((c) => c + 1);
  };

  const cycleSheetSnap = () => {
    setSheetSnap((curr) => {
      if (curr === "peek") return "half";
      if (curr === "half") return "full";
      return "peek";
    });
  };

  // Drag / Slide gestures for mobile bottom sheet
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffsetY, setDragOffsetY] = useState(0);
  const dragStartYRef = useRef(0);
  const hadDragRef = useRef(false);
  const sheetSnapRef = useRef<SheetSnap>(sheetSnap);
  sheetSnapRef.current = sheetSnap;

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    dragStartYRef.current = e.clientY;
    setIsDragging(true);
    setDragOffsetY(0);
    hadDragRef.current = false;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {}
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || dragStartYRef.current === 0) return;
    const deltaY = e.clientY - dragStartYRef.current;
    if (Math.abs(deltaY) > 6) {
      hadDragRef.current = true;
    }

    // Resistance / rubber band when pulling beyond bounds
    if (sheetSnapRef.current === "peek" && deltaY > 0) {
      setDragOffsetY(deltaY * 0.25);
    } else if (sheetSnapRef.current === "full" && deltaY < 0) {
      setDragOffsetY(deltaY * 0.25);
    } else {
      setDragOffsetY(deltaY);
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {}

    const deltaY = dragOffsetY;
    setIsDragging(false);
    setDragOffsetY(0);

    // If dragged by > 35px, advance or retreat snap state
    if (deltaY < -35) {
      // Swiped UP
      if (sheetSnapRef.current === "peek") setSheetSnap("half");
      else if (sheetSnapRef.current === "half") setSheetSnap("full");
    } else if (deltaY > 35) {
      // Swiped DOWN
      if (sheetSnapRef.current === "full") setSheetSnap("half");
      else if (sheetSnapRef.current === "half") setSheetSnap("peek");
    }

    dragStartYRef.current = 0;
  };

  const handleHeaderClick = () => {
    if (hadDragRef.current) {
      hadDragRef.current = false;
      return;
    }
    cycleSheetSnap();
  };
  if (!todayData || !territory) {
    return (
      <div className="flex flex-1 items-center justify-center p-12 text-slate-400">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-cmcb-700 border-t-transparent" />
          <p className="text-sm font-semibold">Loading daily field map...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1 w-full h-full min-h-0 overflow-hidden bg-slate-100 select-none">
      {/* ========================================================================= */}
      {/* 1. FULL-BLEED GOOGLE MAPS CANVAS                                          */}
      {/* ========================================================================= */}
      <div className="absolute inset-0 z-0">
        <MapCanvas center={defaultCenter} zoom={13}>
          <TodayMapCameraController
            stops={displayedStops}
            defaultCenter={defaultCenter}
            focusCoord={focusedCoord}
            recenterTrigger={recenterCount}
          />

          {/* Sequential Route Trail Polyline (My Visits & Specific RM) */}
          {routePoints.length > 1 && (
            <Polyline
              positions={routePoints}
              pathOptions={{
                color: "#006B3F",
                weight: 4,
                dashArray: "6, 8",
                opacity: 0.9,
                lineJoin: "round",
              }}
            />
          )}

          {/* Stops Markers */}
          {displayedStops.map((stop) => (
            <Marker
              key={`${mapMode}-${stop.id}`}
              position={[stop.latitude, stop.longitude]}
              icon={createTodayStopIcon(stop.label, stop.stage, stop.is_teammate)}
              eventHandlers={{
                click: () => {
                  if (stop.merchant_id) openMerchantDetail(stop.merchant_id);
                },
              }}
            >
              <Tooltip direction="top" offset={[0, -16]} opacity={1}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-800">
                    {stop.is_teammate ? `${stop.rm_name} · Stop #${stop.label}` : `Stop #${stop.label}`}
                  </span>
                  <span className="text-[10px] font-medium text-slate-500">{stop.time}</span>
                </div>
                <div className="font-bold text-slate-900">{stop.name}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {stop.district} · <span className="font-semibold text-slate-700">{stop.outcome}</span>
                </div>
                {stop.remark && (
                  <div className="text-[11px] text-slate-600 mt-1 italic max-w-xs">
                    "{stop.remark}"
                  </div>
                )}
              </Tooltip>
            </Marker>
          ))}
        </MapCanvas>
      </div>

      {/* ========================================================================= */}
      {/* 2. FLOATING TOP CONTROLS (Google Maps Island)                             */}
      {/* ========================================================================= */}
      <div className="absolute top-3 left-3 right-3 z-10 pointer-events-none flex flex-col gap-2.5 max-w-xl mx-auto">
        {/* Top Row: Metric Label + Re-center Action */}
        <div className="flex items-center justify-between gap-2 pointer-events-auto">
          {/* RM Visits Today Metric Pill & Date Navigator (matches Live Pulse) */}
          <div className="flex items-center gap-1.5 rounded-full bg-white/95 backdrop-blur-md px-2.5 py-1.5 shadow-md border border-slate-200/80">
            <button
              onClick={() => setDateOffset((prev) => prev + 1)}
              title="Previous day"
              className="p-1 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>

            <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-100 text-emerald-800">
              <Flame className="h-3.5 w-3.5 text-emerald-700 fill-emerald-600" />
            </span>
            <span className="text-xs font-black text-slate-900 tracking-tight shrink-0">
              {visits_today.length} {visits_today.length === 1 ? "Visit" : "Visits"} Today
            </span>

            <span className="text-[11px] font-semibold text-slate-400 shrink-0">·</span>

            {/* Exact Date before District for clarity and debugging */}
            <span className="text-[11px] font-bold text-slate-700 font-mono shrink-0">
              {pillDateLabel}
            </span>

            <span className="text-[11px] font-semibold text-slate-400 shrink-0">·</span>

            <span className="text-[11px] font-semibold text-slate-500 truncate shrink-0">
              {territory.primary_khan}
            </span>

            <button
              onClick={() => setDateOffset((prev) => Math.max(0, prev - 1))}
              disabled={dateOffset === 0}
              title="Next day"
              className="p-1 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors cursor-pointer"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Map Quick Action Buttons */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleRecenter}
              title="Re-center map on stops"
              className="grid h-8.5 w-8.5 place-items-center rounded-full bg-white/95 backdrop-blur-md shadow-md border border-slate-200/80 text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-all cursor-pointer"
            >
              <LocateFixed className="h-4 w-4 text-slate-700" />
            </button>
          </div>
        </div>

        {/* Second Row: Floating 3-Mode Selector Bar */}
        <div className="pointer-events-auto flex items-center gap-1 rounded-2xl bg-white/95 backdrop-blur-md p-1 shadow-md border border-slate-200/80 overflow-x-auto no-scrollbar">
          {/* Mode 1: You */}
          <button
            onClick={() => {
              setMapMode("my");
              setFocusedCoord(null);
            }}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all shrink-0 cursor-pointer ${
              mapMode === "my"
                ? "bg-cmcb-700 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
            }`}
          >
            <User className="h-3.5 w-3.5" />
            <span>You ({visits_today.length})</span>
          </button>

          {/* Mode 2: All Sales */}
          <button
            onClick={() => {
              setMapMode("team");
              setFocusedCoord(null);
            }}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition-all shrink-0 cursor-pointer ${
              mapMode === "team"
                ? "bg-cmcb-700 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
            }`}
          >
            <Users className="h-3.5 w-3.5" />
            <span>All Sales ({team_activity.length})</span>
          </button>

          {/* Mode 3: Specific Sales Rep */}
          <div className="relative shrink-0">
            <select
              value={mapMode === "specific" ? selectedTeammateId || "none" : "none"}
              onChange={(e) => {
                const val = e.target.value;
                if (val === "none") {
                  setMapMode("team");
                } else {
                  setSelectedTeammateId(parseInt(val, 10));
                  setMapMode("specific");
                  setFocusedCoord(null);
                }
              }}
              className={`flex items-center rounded-xl px-2.5 py-1.5 text-xs font-bold transition-all cursor-pointer focus:outline-none ${
                mapMode === "specific"
                  ? "bg-cmcb-700 text-white shadow-xs"
                  : "bg-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
              }`}
            >
              <option value="none" className="text-slate-900 bg-white font-semibold">
                {mapMode === "specific" ? `RM: ${selectedTeammate?.name || "Pick"} ▾` : "Select Sale ▾"}
              </option>
              {teamRoster.map((t) => (
                <option key={t.rm_id} value={t.rm_id} className="text-slate-900 bg-white font-semibold">
                  {t.name} ({t.count} {t.count === 1 ? "stop" : "stops"})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 3. COLLAPSIBLE BOTTOM SHEET (Mobile) / FLOATING SIDE PANEL (Desktop)       */}
      {/* ========================================================================= */}
      <div
        style={{
          transform: isDragging && dragOffsetY !== 0 ? `translateY(${dragOffsetY}px)` : undefined,
          transition: isDragging ? "none" : "height 0.3s cubic-bezier(0.16, 1, 0.3, 1), transform 0.3s ease",
        }}
        className={`absolute bottom-0 left-0 right-0 z-20 bg-white rounded-t-3xl shadow-2xl border-t border-slate-200/90 flex flex-col lg:left-4 lg:bottom-4 lg:right-auto lg:top-20 lg:w-96 lg:rounded-2xl lg:border lg:border-slate-200/90 ${
          sheetSnap === "peek"
            ? "h-[74px] lg:h-auto lg:max-h-[75vh]"
            : sheetSnap === "half"
            ? "h-[46vh] lg:h-auto lg:max-h-[75vh]"
            : "h-[84vh] lg:h-auto lg:max-h-[85vh]"
        }`}
      >
        {/* Top Drag Handle & Clickable Header */}
        <div
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onClick={handleHeaderClick}
          className="px-4 pt-2.5 pb-2.5 border-b border-slate-100 cursor-grab active:cursor-grabbing select-none shrink-0 touch-none bg-white rounded-t-3xl lg:rounded-t-2xl"
        >
          {/* Mobile Drag Indicator Bar */}
          <div className="mx-auto mb-2.5 h-1.5 w-12 rounded-full bg-slate-300 lg:hidden" />
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <h3 className="font-extrabold text-xs lg:text-sm text-slate-800 truncate">
                {mapMode === "my"
                  ? "Your Route Timeline"
                  : mapMode === "specific"
                  ? `${selectedTeammate?.name || "Sales Rep"} Timeline`
                  : "Live Team Ticker"}
              </h3>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] font-mono font-bold bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-200">
                {displayedStops.length} {displayedStops.length === 1 ? "stop" : "stops"}
              </span>

              {/* Snap Toggle Buttons */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  cycleSheetSnap();
                }}
                className="grid h-6 w-6 place-items-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 lg:hidden"
              >
                {sheetSnap === "full" ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronUp className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Peek Ticker Snippet (shown when sheet is collapsed on mobile) */}
          {sheetSnap === "peek" && latestActivity && (
            <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500 truncate lg:hidden">
              <span className="font-mono font-bold text-slate-400 shrink-0">
                {latestActivity.time}
              </span>
              <span>·</span>
              <span className="font-semibold text-slate-700 truncate">
                {"rm_name" in latestActivity && `${latestActivity.rm_name} @ `}
                {"name" in latestActivity ? latestActivity.name : latestActivity.merchant_name}
              </span>
              <span className="text-emerald-600 font-bold shrink-0">
                [{"outcome" in latestActivity ? latestActivity.outcome : latestActivity.status}]
              </span>
            </div>
          )}
        </div>

        {/* Scrollable Timeline / Feed Body */}
        <div
          className={`flex-1 overflow-y-auto p-3.5 space-y-2.5 ${
            sheetSnap === "peek" ? "hidden lg:block" : "block"
          }`}
        >
          {/* ------------------------------------------------------------- */}
          {/* Mode A: ALL SALES (Team Live Ticker + Early Bird Banner)       */}
          {/* ------------------------------------------------------------- */}
          {mapMode === "team" && (
            <>
              {/* Early Bird Achievement Banner (from Live Pulse) */}
              {earlyBird && (
                <div
                  onClick={() => {
                    setFocusedCoord([earlyBird.latitude, earlyBird.longitude]);
                  }}
                  className="rounded-xl bg-gradient-to-r from-red-950 via-rose-900 to-red-950 p-2.5 text-white shadow-sm flex items-center justify-between border border-rose-500/40 cursor-pointer hover:opacity-95 transition-opacity"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-rose-500/20 border border-rose-400/30">
                      <Flame className="h-3.5 w-3.5 text-rose-300 fill-rose-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-black tracking-wider text-[9px] text-rose-300 uppercase font-mono">
                          EARLY BIRD
                        </span>
                        <span className="text-[9px] text-rose-400 font-mono">• {earlyBird.time}</span>
                      </div>
                      <p className="text-xs font-bold text-white truncate">
                        {earlyBird.rm_name}
                        <span className="font-normal text-rose-200">
                          {" "}
                          @ {earlyBird.merchant_name}
                        </span>
                      </p>
                    </div>
                  </div>
                  <span className="text-[8px] font-bold uppercase tracking-wider bg-rose-500/20 px-1.5 py-0.5 rounded text-rose-200 border border-rose-400/30 shrink-0">
                    1st on field
                  </span>
                </div>
              )}

              {/* Team Live Ticker Stream Cards */}
              {team_activity.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No visits logged by team yet today.
                </div>
              ) : (
                team_activity.map((act) => {
                  const isConverted = act.stage === "CONVERTED" || act.stage === "EXISTING";
                  return (
                    <div
                      key={act.id}
                      onClick={() => {
                        setFocusedCoord([act.latitude, act.longitude]);
                        if (act.merchant_id) openMerchantDetail(act.merchant_id);
                      }}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 hover:border-slate-200 hover:bg-slate-50/70 transition-all cursor-pointer group"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        {/* Teammate Initials Bubble */}
                        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-900 text-white font-mono text-[10px] font-black group-hover:bg-cmcb-700 transition-colors">
                          {act.rm_initials}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-slate-900 truncate">
                            <span className="text-cmcb-700">{act.rm_name}</span> · {act.merchant_name}
                          </p>
                          <p className="text-[10px] text-slate-500 truncate">
                            {act.district} · {act.remark || "Visit logged"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono text-slate-400">{act.time}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                            isConverted
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                          }`}
                        >
                          {act.status}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </>
          )}

          {/* ------------------------------------------------------------- */}
          {/* Mode B: YOU (Sequential Stop Timeline)                         */}
          {/* ------------------------------------------------------------- */}
          {mapMode === "my" && (
            <>
              {visits_today.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400 space-y-1">
                  <p className="font-semibold text-slate-600">No visits logged yet today.</p>
                  <p>Send a visit report with GPS in Telegram to log automatically.</p>
                </div>
              ) : (
                visits_today.map((v, idx) => {
                  const isConverted = v.khqr_stage === "CONVERTED" || v.khqr_stage === "EXISTING";
                  return (
                    <div
                      key={v.id}
                      onClick={() => {
                        setFocusedCoord([v.latitude, v.longitude]);
                        openMerchantDetail(v.merchant_id);
                      }}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 hover:border-slate-200 hover:bg-slate-50/70 transition-all cursor-pointer group"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        {/* Numbered Sequence Bubble */}
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cmcb-700 text-white font-mono text-[10px] font-black group-hover:scale-105 transition-transform">
                          {idx + 1}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-slate-900 truncate">{v.name}</p>
                          <p className="text-[10px] text-slate-500 truncate">
                            {v.district} · {v.remark || "Visit interaction logged"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono text-slate-400">{v.time}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                            isConverted
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {isConverted ? "Signed" : "Not Signed"}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </>
          )}

          {/* ------------------------------------------------------------- */}
          {/* Mode C: SPECIFIC SALES REP (Sequential Route Timeline)        */}
          {/* ------------------------------------------------------------- */}
          {mapMode === "specific" && (
            <>
              {displayedStops.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No visits logged for this sales rep today.
                </div>
              ) : (
                displayedStops.map((stop) => {
                  const isConverted = stop.stage === "CONVERTED" || stop.stage === "EXISTING";
                  return (
                    <div
                      key={stop.id}
                      onClick={() => {
                        setFocusedCoord([stop.latitude, stop.longitude]);
                        if (stop.merchant_id) openMerchantDetail(stop.merchant_id);
                      }}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 hover:border-slate-200 hover:bg-slate-50/70 transition-all cursor-pointer group"
                    >
                      <div className="flex items-center gap-2.5 min-w-0 pr-2">
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-900 text-white font-mono text-[10px] font-black group-hover:bg-cmcb-700 transition-colors">
                          {stop.label}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-slate-900 truncate">{stop.name}</p>
                          <p className="text-[10px] text-slate-500 truncate">
                            {stop.district} · {stop.remark || "Visit logged"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono text-slate-400">{stop.time}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                            isConverted
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                          }`}
                        >
                          {stop.outcome}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
