import React, { useState } from "react";
import {
  TableProperties,
  CalendarDays,
  RefreshCw,
  Clock,
  Activity,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  LogOut,
} from "lucide-react";
import { useData } from "../../context/DataContext";
import { useSession } from "../../context/SessionContext";
import type { ActiveTab } from "../../types";

interface SidebarProps {
  onSwitchToSales?: () => void;
  onLogout?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onSwitchToSales, onLogout }) => {
  const session = useSession();
  const {
    activeTab,
    setActiveTab,
    isSyncing,
    isLiveConnected,
    lastSyncTime,
    refreshData,
    merchants,
    rms,
    dlqItems,
    statsSummary,
  } = useData();

  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("cmcb_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("cmcb_sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
  };
  const NAV_ITEMS: Array<{ id: ActiveTab; label: string; icon: React.ComponentType<{ className?: string }> }> = [
    { id: "performance", label: "Sales Activity", icon: Clock },
    { id: "live-pulse", label: "Live Pulse", icon: Activity },
    { id: "drop-calendar", label: "Drop Calendar", icon: CalendarDays },
    { id: "data-explorer", label: "Data Explorer", icon: TableProperties },
  ];

  const formatLastSync = (d: Date | null) => {
    if (!d) return "Pending";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  return (
    <aside
      className={`relative flex w-full flex-col border-b border-slate-200 bg-white transition-all duration-300 ease-in-out lg:min-h-screen lg:shrink-0 lg:border-b-0 lg:border-r ${
        isCollapsed ? "lg:w-20" : "lg:w-64"
      }`}
    >
      {/* Floating Edge Collapse/Expand Toggle */}
      <button
        onClick={toggleCollapse}
        title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="hidden lg:flex absolute -right-3 top-6 z-30 h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-xs hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800 hover:shadow-sm transition-all focus:outline-none"
      >
        {isCollapsed ? (
          <ChevronRight className="h-3.5 w-3.5" />
        ) : (
          <ChevronLeft className="h-3.5 w-3.5" />
        )}
      </button>

      {/* Brand Header */}
      {!isCollapsed ? (
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <img
            src="/CMCB Logo.jpg"
            alt="CMCB Logo"
            className="h-10 w-10 shrink-0 rounded-xl object-contain shadow-sm ring-1 ring-slate-200/80"
          />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-display text-base font-bold tracking-tight text-slate-900 truncate">
                CMCB
              </span>
              <span className="rounded bg-emerald-100/80 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                KHQR
              </span>
            </div>
            <p className="text-xs font-medium text-slate-500 truncate">Market Insights</p>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center border-b border-slate-100 py-4 px-2">
          <img
            src="/CMCB Logo.jpg"
            alt="CMCB Logo"
            className="h-10 w-10 shrink-0 rounded-xl object-contain shadow-sm ring-1 ring-slate-200/80"
          />
        </div>
      )}

      {session && !isCollapsed && <div className="border-b border-slate-100 px-4 py-2">
        <div className="flex min-w-0 items-center gap-2"><span title={session.username} className="min-w-0 flex-1 truncate text-xs font-bold text-slate-800">{session.username}</span><span className="rounded-full bg-teal-50 px-2 py-0.5 text-[9px] font-bold uppercase text-teal-700">{session.role}</span></div>
        <p title={session.allowed_sources?.join(", ") || "All sources"} className="mt-0.5 truncate text-[10px] text-slate-500">{session.branch ? `${session.branch} · ` : ""}{session.all_sources ? "All sources" : `${session.allowed_sources?.length || 0} allowed sources`}</p>
      </div>}
      {/* Main Navigation */}
      <nav className={`flex gap-1 overflow-x-auto p-2.5 lg:flex-col lg:overflow-visible ${isCollapsed ? "items-center" : ""}`}>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const isActive = activeTab === id;
          return !isCollapsed ? (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex shrink-0 items-center gap-2 rounded-lg px-2.5 py-2 text-xs font-semibold transition-all lg:px-3.5 lg:py-2.5 lg:text-sm ${
                isActive
                  ? "bg-emerald-50 text-cmcb-700 shadow-sm ring-1 ring-emerald-600/10"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <Icon
                className={`hidden h-4 w-4 shrink-0 transition-colors lg:block ${
                  isActive ? "text-cmcb-700" : "text-slate-400"
                }`}
              />
              <span className="truncate flex-1 text-left">{label}</span>
              {id === "data-explorer" && dlqItems.length > 0 && (
                <span className="rounded-full bg-amber-100 px-1.5 py-0.2 font-mono text-[10px] font-bold text-amber-800 border border-amber-200">
                  {dlqItems.length}
                </span>
              )}
            </button>
          ) : (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              title={label}
              className={`group relative flex h-11 w-11 items-center justify-center rounded-xl transition-all ${
                isActive
                  ? "bg-emerald-50 text-cmcb-700 shadow-sm ring-1 ring-emerald-600/20"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <Icon
                className={`h-5 w-5 shrink-0 transition-colors ${
                  isActive ? "text-cmcb-700" : "text-slate-500 group-hover:text-slate-700"
                }`}
              />
              {id === "data-explorer" && dlqItems.length > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 font-mono text-[9px] font-black text-white shadow-xs">
                  {dlqItems.length}
                </span>
              )}
            </button>
          );
        })}
      </nav>
      {/* Switch to Field Sales Portal Button */}
      {onSwitchToSales && (
        <div className="hidden px-3 pt-1 pb-2 lg:block">
          <button
            onClick={onSwitchToSales}
            className="flex w-full items-center justify-between gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-3.5 py-2.5 text-xs font-bold text-white shadow-sm hover:from-blue-700 hover:to-indigo-700 transition-all"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              <span>Field Sales Portal</span>
            </div>
            <span className="rounded bg-white/20 px-1.5 py-0.5 text-[9px] font-extrabold uppercase">
              TMA
            </span>
          </button>
        </div>
      )}

      {/* System Status & Sync Card */}
      {!isCollapsed ? (
        <div className="mt-auto hidden border-t border-slate-100 p-4 lg:block">
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  {isLiveConnected && (
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  )}
                  <span
                    className={`relative inline-flex h-2 w-2 rounded-full ${
                      isLiveConnected ? "bg-emerald-500" : "bg-amber-500"
                    }`}
                  ></span>
                </span>
                <span className="text-xs font-semibold text-slate-700">
                  {isLiveConnected ? "Live Backend" : "Backend Offline"}
                </span>
              </div>

              <button
                onClick={() => refreshData()}
                disabled={isSyncing}
                title="Sync now"
                className="inline-flex items-center justify-center rounded-md p-1 text-slate-500 hover:bg-slate-200/60 hover:text-slate-700 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? "animate-spin text-emerald-600" : ""}`} />
              </button>
            </div>

            <div className="mt-2 text-[11px] text-slate-500">
              <span>Last sync: </span>
              <span className="font-mono font-medium text-slate-700">
                {formatLastSync(lastSyncTime)}
              </span>
            </div>

            <div className="mt-3 flex items-center justify-between border-t border-slate-200/60 pt-2 text-[11px] text-slate-600">
              <span>Stores: <strong className="font-mono text-slate-800">{statsSummary?.total_merchants ?? merchants.length}</strong></span>
              <span>RMs: <strong className="font-mono text-slate-800">{statsSummary?.total_rms ?? rms.length}</strong></span>
            </div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="mt-2 w-full flex items-center justify-center gap-1.5 rounded-lg py-1.5 px-3 text-xs font-bold text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200/80 transition-colors cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign out</span>
            </button>
          )}
        </div>
      ) : (
        <div className="mt-auto hidden border-t border-slate-100 p-3 lg:flex lg:flex-col lg:items-center lg:gap-2">
          <button
            onClick={() => refreshData()}
            disabled={isSyncing}
            title={`Sync now (${isLiveConnected ? "Backend Online" : "Backend Offline"}) - Last: ${formatLastSync(lastSyncTime)}`}
            className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <span
              className={`absolute top-2 right-2 h-2 w-2 rounded-full ${
                isLiveConnected ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            <RefreshCw className={`h-4 w-4 ${isSyncing ? "animate-spin text-emerald-600" : "text-slate-500"}`} />
          </button>
          {onLogout && (
            <button
              onClick={onLogout}
              title="Sign out"
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200/80 bg-slate-50 text-slate-500 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      )}
    </aside>
  );
};
