import React, { useState } from "react";
import { X, UserCheck, Search, ShieldCheck } from "lucide-react";
import { useSales } from "../../context/SalesContext";

export const RMSwitcherModal: React.FC = () => {
  const {
    telegramId,
    setTelegramId,
    availableRMs,
    currentRM,
    isRMModalOpen,
    setIsRMModalOpen,
  } = useSales();

  const [inputVal, setInputVal] = useState(String(telegramId));
  const [filterQuery, setFilterQuery] = useState("");

  if (!isRMModalOpen) return null;

  const filteredRMs = availableRMs.filter((rm) => {
    const q = filterQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      rm.name.toLowerCase().includes(q) ||
      (rm.username && rm.username.toLowerCase().includes(q)) ||
      String(rm.telegram_user_id).includes(q)
    );
  });

  const handleApplyCustomId = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseInt(inputVal.trim(), 10);
    if (!isNaN(parsed) && parsed > 0) {
      setTelegramId(parsed);
      setIsRMModalOpen(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl border border-slate-100 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 bg-slate-50/70">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Sales Representative Profile</h2>
            <p className="text-xs text-slate-500">
              Active Telegram ID · Auto-injected in production Telegram WebApp
            </p>
          </div>
          <button
            onClick={() => setIsRMModalOpen(false)}
            className="rounded-full p-2 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-6 space-y-6">
          {/* Manual Telegram ID Input */}
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-2">
              Enter Custom Telegram ID
            </label>
            <form onSubmit={handleApplyCustomId} className="flex gap-2">
              <input
                type="number"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                placeholder="e.g. 8859478803"
                className="flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-semibold text-slate-900 shadow-sm focus:border-cmcb-600 focus:outline-none focus:ring-1 focus:ring-cmcb-600"
              />
              <button
                type="submit"
                className="rounded-xl bg-cmcb-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-cmcb-800 transition-colors"
              >
                Apply
              </button>
            </form>
            <p className="mt-2 text-[11px] text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-cmcb-700 shrink-0" />
              Current Active RM:{" "}
              <span className="font-semibold text-slate-800">
                {currentRM?.name || "Loading..."} (ID: {telegramId})
              </span>
            </p>
          </div>

          {/* Quick Switch List */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                Switch to Team Member ({availableRMs.length})
              </label>
            </div>

            {/* Filter Search */}
            <div className="relative mb-3">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder="Search by RM name, handle, or ID..."
                className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs font-medium text-slate-800 placeholder-slate-400 shadow-sm focus:border-cmcb-600 focus:outline-none focus:ring-1 focus:ring-cmcb-600"
              />
            </div>

            <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
              {filteredRMs.map((rm) => {
                const isSelected = rm.telegram_user_id === telegramId;
                return (
                  <button
                    key={rm.id}
                    onClick={() => {
                      setTelegramId(rm.telegram_user_id);
                      setIsRMModalOpen(false);
                    }}
                    className={`w-full flex items-center justify-between rounded-xl px-3.5 py-2.5 text-left transition-all ${
                      isSelected
                        ? "bg-cmcb-50 border border-cmcb-200 text-cmcb-900 shadow-sm"
                        : "hover:bg-slate-50 border border-transparent text-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                          isSelected
                            ? "bg-cmcb-700 text-white"
                            : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        {rm.initials}
                      </div>
                      <div className="min-w-0 truncate">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold truncate text-slate-900">
                            {rm.name}
                          </p>
                          {isSelected && (
                            <UserCheck className="h-3.5 w-3.5 text-cmcb-700 shrink-0" />
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 truncate">
                          {rm.username ? `@${rm.username}` : `TG: ${rm.telegram_user_id}`}
                        </p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <p className="text-xs font-bold text-slate-900">{rm.total_visits} visits</p>
                      <p className="text-[10px] text-emerald-600 font-semibold">
                        {rm.onboarded_count} onboarded
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 bg-slate-50/70 px-6 py-3.5 text-right">
          <button
            onClick={() => setIsRMModalOpen(false)}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
