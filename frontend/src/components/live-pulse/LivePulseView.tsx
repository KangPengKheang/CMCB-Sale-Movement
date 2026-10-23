import React, { useMemo, useState, useEffect, useRef } from "react";
import { useData } from "../../context/DataContext";
import type { RawVisitReport } from "../../types";
import { MapCanvas } from "../map/MapCanvas";
import { Marker, Tooltip, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import { Users, CheckCircle, Activity, MapPin, TrendingUp, Clock, Target, ChevronLeft, ChevronRight, Calendar, Flame, X, Phone, ExternalLink } from "lucide-react";
import { MetricCard } from "../layout/MetricCard";
// Camera controller to smoothly glide to selected RM stops or reset on clear
function LivePulseMapController({
  selectedVisits,
  selectedRMId,
}: {
  selectedVisits: { displayLat: number; displayLng: number }[];
  selectedRMId: number | string | null;
}) {
  const map = useMap();
  const prevRMRef = useRef<number | string | null | undefined>(undefined);

  useEffect(() => {
    // If the selected RM didn't change (e.g. page re-render, tick, or initial load), DO NOTHING
    if (prevRMRef.current === selectedRMId) {
      return;
    }

    // On initial mount with no RM selected, do NOT fire animation (map is already centered)
    if (prevRMRef.current === undefined && !selectedRMId) {
      prevRMRef.current = null;
      return;
    }

    prevRMRef.current = selectedRMId;

    if (!selectedRMId || selectedVisits.length === 0) {
      // Smoothly return to whole city overview
      map.flyTo([11.5564, 104.9282], 12, { duration: 0.9 });
      return;
    }

    if (selectedVisits.length === 1) {
      // Single stop: glide straight to street level
      const stop = selectedVisits[0];
      map.flyTo([stop.displayLat, stop.displayLng], 15, { duration: 0.9 });
    } else {
      // Multiple stops: calculate bounds and smoothly frame all stops with padding
      const latLngs = selectedVisits.map((v) => [v.displayLat, v.displayLng] as [number, number]);
      const bounds = L.latLngBounds(latLngs);
      map.flyToBounds(bounds, {
        padding: [60, 60],
        maxZoom: 16,
        duration: 0.9,
      });
    }
  }, [selectedRMId, selectedVisits, map]);
  return null;
}

/** Check if a report represents a signed deal (sales win) regardless of competitor presence */
function isVisitSigned(r: RawVisitReport): boolean {
  const stage = (r.khqr_stage || "").toUpperCase();
  if (stage === "CONVERTED" || stage === "SIGNED" || stage === "EXISTING") return true;
  if (r.has_cmcb === 1) return true;
  const statusStr = `${r.status || ""} ${r.status_clean || ""}`.toLowerCase();
  if (statusStr.includes("sign") || statusStr.includes("deploy") || statusStr.includes("exist")) return true;
  const remarkStr = (r.remark || "").toLowerCase();
  if (/\b(sign|signed|signing|deploy|deployed|open\s*khqr)\b/i.test(remarkStr)) return true;
  return false;
}

export const LivePulseView: React.FC = () => {
  const { reports } = useData();
  const [selectedRMId, setSelectedRMId] = useState<number | string | null>(null);
  const [offsetDays, setOffsetDays] = useState<number>(0); // 0 = Today, 1 = Yesterday, etc.
  const [selectedAuditReport, setSelectedAuditReport] = useState<RawVisitReport | null>(null);
  const { activeReports, prevReports, systemNow, selectedDateString, isToday } = useMemo(() => {
    if (!reports) return { activeReports: [], prevReports: [], systemNow: Date.now(), selectedDateString: "", isToday: true };
    
    const now = Date.now();
    
    // Calculate the actual date we want to view, and the day before it
    const targetTime = now - (offsetDays * 86400000);
    const prevTargetTime = now - ((offsetDays + 1) * 86400000);
    
    const selectedDateStr = new Date(targetTime).toDateString();
    const prevDateStr = new Date(prevTargetTime).toDateString();
    
    const dayReports = reports.filter((r) => new Date(r.report_time).toDateString() === selectedDateStr);
    const yesterdayReports = reports.filter((r) => new Date(r.report_time).toDateString() === prevDateStr);
    
    return { 
      activeReports: dayReports, 
      prevReports: yesterdayReports,
      systemNow: now, 
      selectedDateString: selectedDateStr,
      isToday: offsetDays === 0 
    };
  }, [reports, offsetDays]);

  // 2. Compute Macro KPIs
  // 2. Compute Macro KPIs & Deltas
  const { visitsToday, activeRMs, highPotential, signed, newProspects, deltas } = useMemo(() => {
    const rmSet = new Set<string | number>();
    let hCount = 0;
    let sCount = 0;
    let newCount = 0;
    
    activeReports.forEach(r => {
      rmSet.add(r.rm_id || r.sender_name);
      if (r.potential_level === "H" || r.potential_level === "High") hCount++;
      
      if (isVisitSigned(r)) {
        sCount++;
      } else {
        newCount++;
      }
    });
    
    // Calculate previous day metrics for real trend data
    let prevHCount = 0;
    let prevSCount = 0;
    prevReports.forEach(r => {
      if (r.potential_level === "H" || r.potential_level === "High") prevHCount++;
      if (isVisitSigned(r)) prevSCount++;
    });
    
    return {
      visitsToday: activeReports.length,
      activeRMs: rmSet.size,
      highPotential: hCount,
      signed: sCount,
      newProspects: newCount,
      deltas: {
        visits: activeReports.length - prevReports.length,
        highPotential: hCount - prevHCount,
        signed: sCount - prevSCount,
      }
    };
  }, [activeReports, prevReports]);
  
  // Format delta helper
  const formatDelta = (num: number) => num > 0 ? `+${num}` : `${num}`;
  const getDeltaVariant = (num: number) => num > 0 ? "success" : num < 0 ? "warning" : "neutral";

  // 3. Compute RM Leaderboard (Idle Time vs Max Idle)
  const rmLeaderboard = useMemo(() => {
    const rmMap = new Map<string | number, { name: string, visits: number, signs: number, lastReportTime: number, allTimes: number[] }>();
    
    activeReports.forEach(r => {
      const key = r.rm_id || r.sender_name;
      if (!rmMap.has(key)) {
        rmMap.set(key, { name: r.sender_name, visits: 0, signs: 0, lastReportTime: 0, allTimes: [] });
      }
      const state = rmMap.get(key)!;
      state.visits += 1;
      if (isVisitSigned(r)) state.signs += 1;
      
      const t = new Date(r.report_time).getTime();
      state.allTimes.push(t);
      if (t > state.lastReportTime) state.lastReportTime = t;
    });
    
    return Array.from(rmMap.entries()).map(([id, stats]) => {
      let displayMinutes = 0;
      
      if (isToday) {
        // Current live idle time
        displayMinutes = Math.floor((systemNow - stats.lastReportTime) / 60000);
      } else {
        // Max idle gap for historical days
        const sorted = stats.allTimes.sort((a, b) => a - b);
        let maxGap = 0;
        for (let i = 1; i < sorted.length; i++) {
          const gap = sorted[i] - sorted[i - 1];
          if (gap > maxGap) maxGap = gap;
        }
        displayMinutes = Math.floor(maxGap / 60000);
      }
      
      return { id, ...stats, displayMinutes };
    }).sort((a, b) => b.visits - a.visits);
  }, [activeReports, systemNow, isToday]);
  // 3.5 Compute Early Bird of the day (Strictly the very first visit/report of the morning)
  const earlyBird = useMemo(() => {
    if (!activeReports || activeReports.length === 0) return null;

    // Sort chronologically (earliest report of the day first)
    const chronological = [...activeReports].sort(
      (a, b) => new Date(a.report_time).getTime() - new Date(b.report_time).getTime()
    );

    const first = chronological[0];
    if (!first) return null;

    return {
      rmId: first.rm_id || first.sender_name,
      rmName: first.sender_name,
      merchantName: first.merchant_name,
      time: first.report_time,
      district: first.district_khan,
    };
  }, [activeReports]);

  // 4. Activity Feed (Filtered by selected RM if active, otherwise latest 10 across team)
  const activityFeed = useMemo(() => {
    if (selectedRMId) {
      return activeReports
        .filter(r => (r.rm_id || r.sender_name) === selectedRMId)
        .sort((a, b) => new Date(a.report_time).getTime() - new Date(b.report_time).getTime()); // Chronological 1, 2, 3...
    }
    return [...activeReports]
      .sort((a, b) => new Date(b.report_time).getTime() - new Date(a.report_time).getTime())
      .slice(0, 10);
  }, [activeReports, selectedRMId]);

  // Format idle time helper
  const formatIdleTime = (mins: number) => {
    if (mins < 60) return `${mins}m`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  };

  // Helper to generate the dropdown labels dynamically
  const getDateLabel = (offset: number) => {
    if (offset === 0) return "Today";
    if (offset === 1) return "Yesterday";
    const d = new Date(systemNow - offset * 86400000);
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  };

  // Map markers (Heat map for Today, Blue dots for Historical)
  const getMarkerIcon = (ageMinutes: number, isSelectedRM: boolean, isHistorical: boolean, sequenceNumber?: number) => {
    let bgColor = isHistorical ? "#3b82f6" : "#94a3b8"; // Blue for history, Slate for cold live
    
    if (!isHistorical) {
      if (ageMinutes < 60) bgColor = "#10b981"; // Hot (< 1 hour, Emerald)
      else if (ageMinutes < 180) bgColor = "#f59e0b"; // Warm (< 3 hours, Amber)
    }
    
    const opacity = isSelectedRM ? "1" : "0.4";
    const scale = isSelectedRM ? "1.2" : "0.8";

    // Only pulse if it's today (live pulse)
    const pulseHtml = !isHistorical
      ? `<span class="absolute inline-flex h-full w-full rounded-full opacity-60 animate-ping" style="background-color: ${bgColor}; animation-duration: 2s;"></span>` 
      : '';
      
    const innerSize = sequenceNumber ? "18px" : "12px";
    const outerSize = sequenceNumber ? 28 : 24;
    const fontSize = "10px";
    
    return L.divIcon({
      className: "custom-marker-icon",
      html: `<div style="
        width: ${outerSize}px;
        height: ${outerSize}px;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: ${opacity};
        transform: scale(${scale});
        transition: all 0.3s ease;
      ">
        ${pulseHtml}
        <span class="relative flex items-center justify-center rounded-full border-[1px] border-white text-white font-mono font-bold" style="
          width: ${innerSize};
          height: ${innerSize};
          font-size: ${fontSize};
          background-color: ${bgColor};
          box-shadow: 0 0 10px ${bgColor}, 0 0 4px ${bgColor};
        ">${sequenceNumber || ""}</span>
      </div>`,
      iconSize: [outerSize, outerSize],
      iconAnchor: [outerSize/2, outerSize/2]
    });
  };
  // Jitter identical coordinates so stacked pins at the same venue/mall fan out visibly
  const selectedRMVisits = useMemo(() => {
    if (!selectedRMId) return [];
    
    const rawVisits = activeReports
      .filter(r => {
        const isMatch = (r.rm_id || r.sender_name) === selectedRMId;
        const lat = Number(r.latitude);
        const lng = Number(r.longitude);
        return isMatch && !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;
      })
      .sort((a, b) => new Date(a.report_time).getTime() - new Date(b.report_time).getTime());

    // Detect overlapping coordinates down to ~1 meter and fan them out by ~16 meters
    const coordCounts = new Map<string, number>();
    return rawVisits.map((v) => {
      const lat = Number(v.latitude);
      const lng = Number(v.longitude);
      const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
      const count = coordCounts.get(key) || 0;
      coordCounts.set(key, count + 1);

      if (count === 0) {
        return { ...v, displayLat: lat, displayLng: lng };
      }

      // Nudge duplicate pins in a circular fanning pattern (~16 meters offset)
      const angle = (count - 1) * 1.57 + 0.78; // 45°, 135°, 225°, 315°
      const radius = 0.00015; // ~16.5m in Phnom Penh
      const displayLat = lat + Math.sin(angle) * radius;
      const displayLng = lng + (Math.cos(angle) * radius) / Math.cos((lat * Math.PI) / 180);

      return { ...v, displayLat, displayLng };
    });
  }, [activeReports, selectedRMId]);

  // General map visits with duplicate coordinate fanning
  const displayAllReports = useMemo(() => {
    const coordCounts = new Map<string, number>();
    return activeReports
      .filter(r => {
        const lat = Number(r.latitude);
        const lng = Number(r.longitude);
        return !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;
      })
      .map(r => {
        const lat = Number(r.latitude);
        const lng = Number(r.longitude);
        const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
        const count = coordCounts.get(key) || 0;
        coordCounts.set(key, count + 1);

        if (count === 0) {
          return { ...r, displayLat: lat, displayLng: lng };
        }
        const angle = (count - 1) * 1.57 + 0.78;
        const radius = 0.00015;
        const displayLat = lat + Math.sin(angle) * radius;
        const displayLng = lng + (Math.cos(angle) * radius) / Math.cos((lat * Math.PI) / 180);
        return { ...r, displayLat, displayLng };
      });
  }, [activeReports]);


  return (
    <div className="grid grid-cols-1 lg:grid-cols-[380px_minmax(0,1fr)] h-full min-h-0 bg-slate-50 gap-4 p-4 overflow-hidden">
      {/* Left Column: The Team (Fixed Width) */}
      <div className="flex flex-col flex-[2] gap-4 min-h-0 overflow-hidden">
        {/* RM Leaderboard */}
        <div className="flex-[3] flex flex-col min-h-0 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="p-4 border-b border-slate-100 bg-slate-50 rounded-t-xl flex justify-between items-center">
            <h3 className="font-bold text-slate-800">{isToday ? "Live RM Performance" : "Daily RM Performance"}</h3>
            <span className="text-xs font-medium text-slate-500">{rmLeaderboard.length} Active RMs</span>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {rmLeaderboard.map((rm, idx) => {
              const isIdleLong = rm.displayMinutes > (isToday ? 60 : 120); // Amber threshold (1h live, 2h max gap)
              const isSelected = selectedRMId === rm.id;
              
              return (
                <div
                  key={rm.id}
                  onClick={() => setSelectedRMId(isSelected ? null : rm.id)}
                  className={`flex cursor-pointer items-center justify-between p-3.5 transition-colors hover:bg-slate-50 ${
                    isSelected ? "bg-emerald-50/80 ring-1 ring-inset ring-emerald-600/20" : ""
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1 pr-2">
                    <span
                      className={`grid h-6 w-6 shrink-0 place-items-center rounded-full font-mono text-xs font-bold ${
                        idx === 0
                          ? "bg-amber-100 text-amber-900 ring-2 ring-amber-300"
                          : idx === 1
                          ? "bg-slate-200 text-slate-800"
                          : idx === 2
                          ? "bg-orange-100 text-orange-900"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <h3 className="font-display text-sm font-bold text-slate-900 truncate">
                          {rm.name}
                        </h3>
                        {earlyBird && earlyBird.rmId === rm.id && (
                          <span
                            className="inline-flex items-center gap-1 rounded bg-rose-100 px-1.5 py-0.5 text-[9px] font-black uppercase font-mono text-rose-800 border border-rose-300 shadow-2xs"
                            title={`Early Bird! First visit of the day at ${new Date(earlyBird.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (${earlyBird.merchantName})`}
                          >
                            <Flame className="h-3 w-3 text-rose-600 fill-rose-500" />
                            <span>EARLY BIRD</span>
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1 mt-0.5">
                        <Clock className={`w-3 h-3 ${isIdleLong ? 'text-amber-500' : 'text-slate-400'}`} />
                        <span className={`font-mono text-[10px] ${isIdleLong ? 'text-amber-600 font-bold' : 'text-slate-500'}`}>
                          {isToday 
                            ? (rm.displayMinutes === 0 ? 'Active now' : formatIdleTime(rm.displayMinutes) + ' idle')
                            : (rm.displayMinutes === 0 ? 'Only 1 visit' : formatIdleTime(rm.displayMinutes) + ' gap')}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-right">
                    <div className="w-12">
                      <span className="font-mono text-sm font-bold text-slate-900 tabular-nums">
                        {rm.visits}
                      </span>
                      <p className="text-[9px] text-slate-500 font-medium uppercase tracking-wider">
                        Visits
                      </p>
                    </div>
                    <div className="w-12">
                      <span className="font-mono text-sm font-bold text-emerald-700 tabular-nums">
                        {rm.signs}
                      </span>
                      <p className="text-[9px] text-emerald-600 font-medium uppercase tracking-wider">
                        Signed
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
            
            {rmLeaderboard.length === 0 && (
              <div className="text-sm text-slate-500 text-center py-8">No activity for this date.</div>
            )}
          </div>
        </div>

        {/* Live Activity Feed / Selected RM Timeline */}
        <div className="flex-[2] flex flex-col min-h-0 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="p-3.5 border-b border-slate-100 bg-slate-50 rounded-t-xl flex items-center justify-between">
            <div className="flex items-center gap-1.5 min-w-0">
              <h3 className="font-bold text-xs sm:text-sm text-slate-800 truncate">
                {selectedRMId ? (
                  <span>
                    Timeline: <span className="text-cmcb-700">{activityFeed[0]?.sender_name || "Sales Rep"}</span>
                  </span>
                ) : (
                  isToday ? "Live Ticker" : "End of Day Log"
                )}
              </h3>
            </div>
            {selectedRMId && (
              <span className="text-[10px] font-mono font-bold bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-200">
                {activityFeed.length} stops
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {/* Early Bird Achievement Banner */}
            {earlyBird && !selectedRMId && (
              <div className="rounded-lg bg-gradient-to-r from-red-950 via-rose-900 to-red-950 p-2.5 text-white shadow-sm flex items-center justify-between border border-rose-500/40">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-rose-500/20 border border-rose-400/30">
                    <Flame className="h-3.5 w-3.5 text-rose-300 fill-rose-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-black tracking-wider text-[10px] text-rose-300 uppercase font-mono">
                        EARLY BIRD
                      </span>
                      <span className="text-[10px] text-rose-400 font-mono">
                        • {new Date(earlyBird.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-xs font-bold text-white truncate">
                      {earlyBird.rmName}
                      <span className="font-normal text-rose-200"> @ {earlyBird.merchantName}</span>
                    </p>
                  </div>
                </div>
                <span className="text-[9px] font-bold uppercase tracking-wider bg-rose-500/20 px-2 py-0.5 rounded text-rose-200 border border-rose-400/30 shrink-0">
                  First On Field
                </span>
              </div>
            )}
            {activityFeed.map((r, idx) => {
              const isConverted = isVisitSigned(r);
              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedAuditReport(r)}
                  className="flex gap-2.5 items-start p-1.5 -mx-1.5 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors group"
                  title="Click to view full report audit data"
                >
                  {selectedRMId ? (
                    <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-slate-900 text-white font-mono text-[9px] font-bold mt-0.5">
                      {idx + 1}
                    </span>
                  ) : (
                    <div className={`mt-1 h-2 w-2 rounded-full shrink-0 ${isConverted ? 'bg-cmcb-500' : 'bg-slate-300'}`} />
                  )}
                  <div className="flex-1 text-xs min-w-0">
                    <p className="text-slate-800 leading-tight">
                      {!selectedRMId && <span className="font-bold">{r.sender_name} </span>}
                      <span className="font-medium">{r.merchant_name}</span>
                    </p>
                    <div className="flex gap-1.5 text-[10px] text-slate-500 mt-0.5 flex-wrap">
                      <span>{new Date(r.report_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      <span>•</span>
                      <span>{r.district_khan}</span>
                      {isConverted && (
                        <>
                          <span>•</span>
                          <span className="text-emerald-700 font-bold bg-emerald-50 px-1 py-0.2 rounded border border-emerald-300">Signed</span>
                        </>
                      )}
                      {r.potential_level === "H" && (
                        <>
                          <span>•</span>
                          <span className="text-orange-600 font-semibold">High Potential</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {activityFeed.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-4">No visits logged for this date.</div>
            )}
          </div>
        </div>
      </div>

      {/* Right Column: The Market (Flexible Width) */}
      <div className="flex flex-col flex-[3] gap-4 min-h-0 overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <Activity className="h-6 w-6 text-cmcb-600" />
            {isToday ? "Live Executive Brief" : "Daily Executive Brief"}
          </h2>
          
          {/* 7-Day Paginator */}
          <div className="flex items-center bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden shrink-0">
            <button 
              onClick={() => setOffsetDays(d => Math.min(6, d + 1))}
              disabled={offsetDays >= 6}
              className="p-2 hover:bg-slate-50 text-slate-600 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            
            {/* The Select Dropdown */}
            <div className="px-3 py-1.5 flex items-center gap-2 min-w-[130px] justify-center border-l border-r border-slate-100 relative group cursor-pointer hover:bg-slate-50 transition-colors">
              <Calendar className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
              <select 
                value={offsetDays}
                onChange={(e) => setOffsetDays(Number(e.target.value))}
                className="text-sm font-bold text-slate-700 bg-transparent border-none outline-none focus:ring-0 cursor-pointer appearance-none pl-6 pr-2 text-center w-full"
              >
                {[0, 1, 2, 3, 4, 5, 6].map(offset => (
                  <option key={offset} value={offset}>
                    {getDateLabel(offset)}
                  </option>
                ))}
              </select>
            </div>

            <button 
              onClick={() => setOffsetDays(d => Math.max(0, d - 1))}
              disabled={offsetDays <= 0}
              className="p-2 hover:bg-slate-50 text-slate-600 disabled:opacity-30 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
        
        {/* Macro KPIs Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard
            label="Visits Today"
            value={visitsToday}
            icon={MapPin}
            badge={{ 
              text: `${formatDelta(deltas.visits)} vs yesterday`, 
              variant: getDeltaVariant(deltas.visits) 
            }}
          />
          <MetricCard
            label="New Visits"
            value={newProspects}
            icon={Target}
            badge={{ text: "Brand new stores", variant: "info" }}
          />
          <MetricCard
            label="High Potential"
            value={highPotential}
            icon={TrendingUp}
            badge={{ 
              text: `${formatDelta(deltas.highPotential)} vs yesterday`, 
              variant: getDeltaVariant(deltas.highPotential) 
            }}
          />
          <MetricCard
            label="Signed"
            value={signed}
            icon={CheckCircle}
            badge={{ 
              text: `${formatDelta(deltas.signed)} vs yesterday`, 
              variant: getDeltaVariant(deltas.signed) 
            }}
          />
        </div>

        {/* Live Operations Map */}
        <div className="flex-1 min-h-0 rounded-xl border border-slate-200 shadow-sm overflow-hidden relative bg-white flex flex-col">
          <div className="p-3 border-b border-slate-100 bg-white font-semibold text-slate-700 flex justify-between items-center">
            <span>{isToday ? "Live Operations Map" : "End of Day Coverage Map"}</span>
            {selectedRMId && (
              <button 
                onClick={() => setSelectedRMId(null)}
                className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded"
              >
                Clear Filter
              </button>
            )}
          </div>
          <div className="flex-1 relative">
            <MapCanvas center={[11.5564, 104.9282]} zoom={12}>
              <LivePulseMapController selectedVisits={selectedRMVisits} selectedRMId={selectedRMId} />
              {/* If no RM is selected, show all active dots with aura */}
              {!selectedRMId && displayAllReports.map(r => {
                const ageMinutes = Math.floor((systemNow - new Date(r.report_time).getTime()) / 60000);
                
                return (
                  <Marker 
                    key={r.id} 
                    position={[r.displayLat, r.displayLng]}
                    icon={getMarkerIcon(ageMinutes, true, !isToday)}
                  >
                    <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                      <div className="font-semibold">{r.merchant_name}</div>
                      <div className="text-xs text-slate-500">{r.sender_name} • {new Date(r.report_time).toLocaleTimeString()}</div>
                      {isToday && (
                        <div className="text-[10px] text-slate-400 font-medium mt-1">
                          {ageMinutes === 0 ? 'Just now' : `${formatIdleTime(ageMinutes)} ago`}
                        </div>
                      )}
                    </Tooltip>
                  </Marker>
                );
              })}

              {/* If an RM is selected, hide all other dots and show their numbered trail */}
              {selectedRMId && selectedRMVisits.length > 0 && (
                <>
                  <Polyline
                    positions={selectedRMVisits.map(v => [v.displayLat, v.displayLng] as [number, number])}
                    pathOptions={{
                      color: "#006B3F",
                      weight: 3,
                      dashArray: "6, 8",
                      opacity: 0.8,
                      lineJoin: "round",
                    }}
                  />
                  {selectedRMVisits.map((v, index) => {
                    const seqNumber = index + 1;
                    const isLatest = index === selectedRMVisits.length - 1;
                    const ageMinutes = Math.floor((systemNow - new Date(v.report_time).getTime()) / 60000);
                    
                    return (
                      <Marker
                        key={`trail-${v.id}`}
                        position={[v.displayLat, v.displayLng]}
                        icon={getMarkerIcon(ageMinutes, true, !isToday, seqNumber)}
                      >
                        <Tooltip direction="top" offset={[0, -16]} opacity={1}>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-800">
                              Stop #{seqNumber}
                            </span>
                            {isToday && (
                              <span className="text-[10px] font-medium text-slate-400">
                                {ageMinutes === 0 ? 'Just now' : `${formatIdleTime(ageMinutes)} ago`}
                              </span>
                            )}
                          </div>
                          <div className="font-semibold text-slate-800">{v.merchant_name}</div>
                          <div className="text-xs text-slate-500">{v.sender_name} • {new Date(v.report_time).toLocaleTimeString()}</div>
                        </Tooltip>
                      </Marker>
                    );
                  })}
                </>
              )}
            </MapCanvas>
            
            {/* Map Legend */}
            <div className="absolute bottom-4 left-4 z-[400] rounded-xl border border-slate-200/90 bg-white/95 p-3 shadow-card backdrop-blur text-xs">
              <p className="font-bold text-slate-800 uppercase tracking-wider text-[10px] mb-2">
                {isToday ? "Live Pulse" : "Historical Map"}
              </p>
              {isToday ? (
                <div className="space-y-1.5 font-medium text-slate-600">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white shadow-sm"></span>
                    <span>Hot (&lt; 1 hr ago)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500 ring-2 ring-white shadow-sm"></span>
                    <span>Warm (1-3 hrs ago)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-slate-400 ring-2 ring-white shadow-sm"></span>
                    <span>Cold (&gt; 3 hrs ago)</span>
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5 font-medium text-slate-600">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-blue-500 ring-2 ring-white shadow-sm"></span>
                    <span>Visited that day</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Visit Audit Modal */}
      {selectedAuditReport && (
        <div
          className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => setSelectedAuditReport(null)}
        >
          <div
            className="w-full max-w-lg max-h-[90vh] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 p-4 bg-slate-50/70">
              <div className="min-w-0 flex-1 pr-2">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-200 font-mono">
                    Visit Report #{selectedAuditReport.id}
                  </span>
                  <span className="font-mono text-xs text-slate-500">
                    {new Date(selectedAuditReport.report_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="text-slate-300">•</span>
                  <span className="text-xs text-slate-500 font-medium">
                    {new Date(selectedAuditReport.report_time).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="mt-1.5 font-display text-base font-bold text-slate-900 truncate">
                  {selectedAuditReport.merchant_name}
                </h3>
                <p className="text-xs text-slate-500 font-medium">
                  Reported by <strong className="text-slate-800">{selectedAuditReport.sender_name}</strong> · Khan {selectedAuditReport.district_khan}
                </p>
              </div>

              <button
                onClick={() => setSelectedAuditReport(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs">
              {/* Quick Actions (Call / Maps) */}
              <div className="grid grid-cols-2 gap-2">
                {selectedAuditReport.tel && (
                  <a
                    href={`tel:${selectedAuditReport.tel}`}
                    className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50/80 p-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
                  >
                    <Phone className="h-3.5 w-3.5 text-emerald-600" />
                    <span className="truncate">{selectedAuditReport.tel_clean || selectedAuditReport.tel}</span>
                  </a>
                )}
                {selectedAuditReport.latitude && selectedAuditReport.longitude && (
                  <a
                    href={selectedAuditReport.map_url || `https://www.google.com/maps?q=${selectedAuditReport.latitude},${selectedAuditReport.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50/80 p-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
                  >
                    <ExternalLink className="h-3.5 w-3.5 text-blue-600" />
                    <span>Google Maps</span>
                  </a>
                )}
              </div>

              {/* Status & Potential Highlights */}
              <div className="flex items-center gap-2">
                <div className={`flex-1 flex items-center justify-between rounded-lg border px-3 py-1.5 ${
                  isVisitSigned(selectedAuditReport)
                    ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                    : "bg-indigo-50 border-indigo-200 text-indigo-800"
                }`}>
                  <span className="text-[10px] font-bold uppercase tracking-wider opacity-75 font-mono">Status:</span>
                  <span className="text-xs font-black tracking-tight">
                    {isVisitSigned(selectedAuditReport) ? "Signed" : (selectedAuditReport.status_clean || selectedAuditReport.status || "Target")}
                  </span>
                </div>
                <div className={`flex-1 flex items-center justify-between rounded-lg border px-3 py-1.5 ${
                  selectedAuditReport.potential_level === "H"
                    ? "bg-amber-50 border-amber-300 text-amber-900"
                    : selectedAuditReport.potential_level === "M"
                    ? "bg-sky-50 border-sky-200 text-sky-800"
                    : "bg-slate-100 border-slate-200 text-slate-600"
                }`}>
                  <span className="text-[10px] font-bold uppercase tracking-wider opacity-75 font-mono">Potential:</span>
                  <span className="text-xs font-black tracking-tight">
                    {selectedAuditReport.potential_level ? `${selectedAuditReport.potential_level === "H" ? "High (H)" : selectedAuditReport.potential_level === "M" ? "Medium (M)" : "Low (L)"}` : "—"}
                  </span>
                </div>
              </div>

              {/* Prominent Remark Card */}
              <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-3 text-xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800/80 block mb-1 font-mono">
                  Remark:
                </span>
                {selectedAuditReport.remark ? (
                  <p className="text-xs italic font-medium text-slate-800 leading-relaxed">
                    "{selectedAuditReport.remark}"
                  </p>
                ) : (
                  <p className="text-xs text-slate-400 italic">No remark provided</p>
                )}
              </div>

              {/* 14-Field Report Audit Table */}
              <div className="rounded-xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
                <div className="divide-y divide-slate-100 text-xs">
                  <div className="flex items-start px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Name:</span>
                    <span className="font-bold text-slate-900 break-words flex-1">{selectedAuditReport.merchant_name || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Business:</span>
                    <span className="text-slate-800 font-medium flex-1">{selectedAuditReport.business_clean || selectedAuditReport.business || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Purpose:</span>
                    <span className="text-slate-800 font-medium flex-1">{selectedAuditReport.purpose || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Bank:</span>
                    <span className="font-semibold text-slate-800 flex-1">{selectedAuditReport.bank || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Amount:</span>
                    <span className="font-mono text-slate-800 flex-1">{selectedAuditReport.amount || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Interest:</span>
                    <span className="font-mono text-slate-800 flex-1">{selectedAuditReport.interest || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Loan Type:</span>
                    <span className="text-slate-800 flex-1">{selectedAuditReport.loan_type || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Tenure:</span>
                    <span className="font-mono text-slate-800 flex-1">{selectedAuditReport.tenure || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Maturity:</span>
                    <span className="font-mono text-slate-800 flex-1">{selectedAuditReport.maturity || "—"}</span>
                  </div>
                  <div className="flex items-center px-3.5 py-2 hover:bg-slate-50/60 transition-colors">
                    <span className="w-32 shrink-0 font-mono text-[11px] font-bold text-slate-500">Potential Product:</span>
                    <span className="font-semibold text-slate-800 flex-1">{selectedAuditReport.potential_product || "—"}</span>
                  </div>
                </div>
              </div>
              </div>

            {/* Modal Footer */}
            <div className="border-t border-slate-100 p-3 bg-slate-50/60 flex justify-end">
              <button
                onClick={() => setSelectedAuditReport(null)}
                className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-2xs"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
