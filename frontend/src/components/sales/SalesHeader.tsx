import React from "react";
import { useSales } from "../../context/SalesContext";
import { LayoutDashboard, RefreshCw, UserCheck } from "lucide-react";

interface SalesHeaderProps {
  onSwitchToAdmin?: () => void;
}

export const SalesHeader: React.FC<SalesHeaderProps> = ({ onSwitchToAdmin }) => {
  const {
    telegramId,
    setTelegramId,
    availableRMs,
    currentRM,
    setIsRMModalOpen,
    isLoading,
    refreshAll,
  } = useSales();

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-slate-200/80 bg-white px-3 sm:px-4 lg:px-8">
      {/* CMCB Brand Logo & App Name */}
      <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
        <img
          src="/CMCB Logo.jpg"
          alt="CMCB Logo"
          className="h-10 w-10 shrink-0 rounded-xl object-contain shadow-sm ring-1 ring-slate-200/80"
        />
        <div className="hidden sm:block">
          <div className="flex items-center gap-1.5">
            <span className="font-display text-base font-bold tracking-tight text-slate-900">
              CMCB
            </span>
            <span className="rounded bg-emerald-100/80 px-1.5 py-0.5 text-[10px] font-bold text-cmcb-800">
              POS Sales
            </span>
          </div>
          <p className="text-[11px] font-medium text-slate-500">
            Retail Merchant Fieldwork
          </p>
        </div>
      </div>

      {/* Prominent RM Dropdown List (Center) */}
      <div className="flex items-center gap-2 max-w-xs sm:max-w-sm flex-1 mx-2 sm:mx-4 justify-center">
        <div className="flex items-center gap-1.5 w-full rounded-xl border border-cmcb-200 bg-cmcb-50/70 px-2.5 py-1.5 shadow-sm">
          <UserCheck className="h-4 w-4 text-cmcb-700 shrink-0" />
          <span className="text-[11px] font-bold text-cmcb-900 hidden md:inline shrink-0">
            Sales Rep:
          </span>
          <select
            value={telegramId}
            onChange={(e) => setTelegramId(parseInt(e.target.value, 10))}
            className="w-full bg-transparent text-xs font-bold text-cmcb-950 focus:outline-none cursor-pointer truncate"
          >
            {availableRMs.map((rm) => (
              <option
                key={rm.id}
                value={rm.telegram_user_id}
                className="text-slate-900 font-medium py-1"
              >
                {rm.name} ({rm.total_visits} visits · {rm.onboarded_count} onboarded)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Right Controls: Sync, Admin Switcher & Avatar */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Refresh button */}
        <button
          onClick={() => refreshAll()}
          title="Refresh Data from Database"
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors shadow-sm"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin text-cmcb-700" : ""}`} />
        </button>

        {/* Portal Switcher Button */}
        {onSwitchToAdmin && (
          <button
            onClick={onSwitchToAdmin}
            className="hidden md:inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
          >
            <LayoutDashboard className="h-3.5 w-3.5 text-slate-500" />
            Admin Portal
          </button>
        )}

        {/* RM Avatar Pill */}
        <button
          onClick={() => setIsRMModalOpen(true)}
          title="Custom Telegram ID / Profile Modal"
          className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50/80 p-1 pr-2.5 hover:bg-slate-100/80 hover:border-slate-300 transition-all shadow-sm"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-cmcb-700 text-xs font-bold text-white shadow-inner">
            {currentRM?.initials || "RM"}
          </div>
          <span className="text-[11px] font-bold text-slate-800 hidden lg:inline max-w-[90px] truncate">
            {currentRM?.name?.split(" ")[0] || "RM"}
          </span>
        </button>
      </div>
    </header>
  );
};
