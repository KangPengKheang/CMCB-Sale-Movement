import React from "react";
import {
  Calendar,
  MapPin,
  Users,
  ClipboardList,
  Sparkles,
  Map as MapIcon,
  Home,
  CheckCircle2,
  ChevronDown,
  LayoutDashboard,
} from "lucide-react";
import { useSales } from "../../context/SalesContext";
import { SalesHeader } from "./SalesHeader";
import { RMSwitcherModal } from "./RMSwitcherModal";
import { TodayView } from "./TodayView";
import { SalesStoreMapView } from "./SalesStoreMapView";
import { MyCustomersView } from "./MyCustomersView";
import { YourVisitsView } from "./YourVisitsView";
import { SalesMerchantDetailDrawer } from "./SalesMerchantDetailDrawer";
import type { SalesTab } from "../../types";

interface SalesPortalViewProps {
  onSwitchToAdmin?: () => void;
}

export const SalesPortalView: React.FC<SalesPortalViewProps> = ({ onSwitchToAdmin }) => {
  const {
    activeSalesTab,
    setActiveSalesTab,
    currentRM,
    telegramId,
    setTelegramId,
    availableRMs,
    setIsRMModalOpen,
  } = useSales();
  const NAV_TABS: Array<{ id: SalesTab; label: string; icon: React.ComponentType<{ className?: string }> }> = [
    { id: "today", label: "Today", icon: Home },
    { id: "store-map", label: "Store map", icon: MapPin },
    { id: "customers", label: "Customers", icon: Users },
    { id: "visits", label: "Your visits", icon: ClipboardList },
  ];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans text-slate-900 antialiased select-none">
      {/* Desktop Left Sidebar (from Desktop design mockups) */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col justify-between border-r border-slate-200/80 bg-white p-5">
        <div className="space-y-6">
          {/* CMCB Brand Logo */}
          <div className="flex items-center gap-3">
            <img
              src="/CMCB Logo.jpg"
              alt="CMCB Logo"
              className="h-10 w-10 shrink-0 rounded-xl object-contain shadow-sm ring-1 ring-slate-200/80"
            />
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-display text-base font-bold tracking-tight text-slate-900">
                  CMCB
                </span>
                <span className="rounded bg-emerald-100/80 px-1.5 py-0.5 text-[10px] font-bold text-cmcb-800">
                  POS Sales
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-500">Retail Fieldwork</p>
            </div>
          </div>

          {/* Workspace Pill */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Workspace
            </span>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Phnom Penh Sales Team</span>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </div>
          </div>

          {/* Nav Items */}
          <nav className="space-y-1">
            {NAV_TABS.map(({ id, label, icon: Icon }) => {
              const isActive = activeSalesTab === id;
              return (
                <button
                  key={id}
                  onClick={() => setActiveSalesTab(id)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-bold transition-all ${
                    isActive
                      ? "bg-cmcb-50 text-cmcb-800 font-extrabold shadow-sm"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? "text-cmcb-700" : "text-slate-400"}`} />
                  {label}
                </button>
              );
            })}
          </nav>

          {/* Territory Status Card */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <MapIcon className="h-4 w-4 text-cmcb-700" />
              <span className="text-xs font-bold text-slate-800">
                {currentRM?.top_districts
                  ? Object.keys(currentRM.top_districts)[0] || "Phnom Penh"
                  : "Phnom Penh"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              Shared coverage with active field reps.
            </p>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-cmcb-700 pt-1">
              <span className="h-2 w-2 rounded-full bg-cmcb-500" />
              All changes synced
            </div>
          </div>
        </div>

        {/* Bottom Profile & Admin Switcher */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          {onSwitchToAdmin && (
            <button
              onClick={onSwitchToAdmin}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <LayoutDashboard className="h-3.5 w-3.5 text-slate-500" />
              Back to Admin Portal
            </button>
          )}

          {/* Quick RM Selector Dropdown in Sidebar */}
          <div className="space-y-1.5 pt-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Active Sales Rep
            </label>
            <select
              value={telegramId}
              onChange={(e) => setTelegramId(parseInt(e.target.value, 10))}
              className="w-full rounded-xl border border-cmcb-200 bg-cmcb-50/70 p-2 text-xs font-bold text-cmcb-950 focus:border-cmcb-600 focus:outline-none cursor-pointer"
            >
              {availableRMs.map((rm) => (
                <option key={rm.id} value={rm.telegram_user_id} className="text-slate-900 font-medium">
                  {rm.name} ({rm.total_visits} visits)
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={() => setIsRMModalOpen(true)}
            className="flex w-full items-center gap-3 rounded-xl p-2 hover:bg-slate-50 transition-colors text-left"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cmcb-700 text-xs font-bold text-white shadow-inner">
              {currentRM?.initials || "RM"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-slate-900 truncate">
                {currentRM?.name || "Select RM"}
              </p>
              <p className="text-[11px] text-slate-500 truncate">
                {currentRM?.username ? `@${currentRM.username}` : "Field Salesperson"}
              </p>
            </div>
          </button>
        </div>
      </aside>

      {/* Main App Content Area */}
      <div className="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden relative">
        {/* Top Header */}
        <SalesHeader onSwitchToAdmin={onSwitchToAdmin} />

        {/* Active View Container */}
        <main className="flex-1 min-h-0 min-w-0 overflow-hidden flex flex-col pb-16 lg:pb-0">
          {activeSalesTab === "today" && <TodayView />}
          {activeSalesTab === "store-map" && <SalesStoreMapView />}
          {activeSalesTab === "customers" && <MyCustomersView />}
          {activeSalesTab === "visits" && <YourVisitsView />}
        </main>

        {/* Mobile Bottom Tab Navigation (from Mobile design mockups) */}
        <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t border-slate-200 bg-white px-2 shadow-lg">
          {NAV_TABS.map(({ id, label, icon: Icon }) => {
            const isActive = activeSalesTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveSalesTab(id)}
                className={`flex flex-col items-center justify-center py-1 px-3 transition-colors ${
                  isActive ? "text-cmcb-700" : "text-slate-400 hover:text-slate-600"
                }`}
              >
                <Icon className={`h-5 w-5 ${isActive ? "text-cmcb-700" : "text-slate-400"}`} />
                <span className={`text-[10px] mt-1 font-semibold ${isActive ? "font-bold text-cmcb-800" : ""}`}>
                  {label}
                </span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* RM Switcher & Identity Modal */}
      <RMSwitcherModal />

      {/* Full Merchant Detail Drawer */}
      <SalesMerchantDetailDrawer />
    </div>
  );
};
