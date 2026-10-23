import React from "react";
import { useData } from "../../context/DataContext";
import { useSession } from "../../context/SessionContext";
import { Sparkles, LogOut } from "lucide-react";

interface HeaderProps {
  onSwitchToSales?: () => void;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onSwitchToSales, onLogout }) => {
  const { activeTab } = useData();
  const session = useSession();

  const TITLES: Record<string, { title: string; desc: string }> = {
    performance: {
      title: "Sales Activity Watcher",
      desc: "Report submission timing, gaps between drops, and daily activity by salesperson.",
    },
    "drop-calendar": {
      title: "Case Drop Calendar",
      desc: "Case counts by salesperson across four weeks and the last 30 days.",
    },
    "data-explorer": {
      title: "Data & Audit Explorer",
      desc: "Complete tabular ledger of verified field visits and uncaught Telegram submissions requiring supervisor review.",
    },
  };

  const currentViewMeta = TITLES[activeTab] || TITLES["performance"];

  return (
    <header className="border-b border-slate-200/80 bg-white">
      {/* Top Banner / Breadcrumb */}
      <div className="flex flex-col justify-between gap-1 border-b border-slate-100 px-4 py-2 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-display text-base sm:text-lg font-bold tracking-tight text-slate-900 leading-tight">
            {currentViewMeta.title}
          </h1>
          <p className="text-[11px] text-slate-500 font-medium hidden sm:block">
            {currentViewMeta.desc}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-cmcb-700 border border-emerald-200/60">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
            <span className="max-w-[150px] truncate">{session ? `${session.username} · ${session.role.toUpperCase()}` : "Sales Monitor"}</span>
          </span>
          {onSwitchToSales && (
            <button
              onClick={onSwitchToSales}
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 border border-blue-200/80 hover:bg-blue-100 transition-colors shadow-sm"
            >
              <Sparkles className="h-3.5 w-3.5 text-blue-600" />
              Field Sales Portal
            </button>
          )}
          {onLogout && (
            <button
              onClick={onLogout}
              title="Sign out from Admin"
              className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600 border border-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 transition-colors shadow-xs cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          )}
        </div>
      </div>

    </header>
  );
};
