import React, { useState } from "react";
import { useData } from "../../context/DataContext";
import { VerifiedVisitsTable } from "./VerifiedVisitsTable";
import { UncaughtDlqTable } from "./UncaughtDlqTable";
import { RecordDetailDrawer } from "./RecordDetailDrawer";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import type { DeadLetterItem, RawVisitReport } from "../../types";

export const DataExplorerView: React.FC = () => {
  const { reports, dlqItems, uniqueKhans } = useData();

  const [activeSubTab, setActiveSubTab] = useState<"verified" | "uncaught">("verified");
  const [selectedReport, setSelectedReport] = useState<RawVisitReport | null>(null);
  const [selectedDlq, setSelectedDlq] = useState<DeadLetterItem | null>(null);

  const handleSelectReport = (report: RawVisitReport) => {
    setSelectedDlq(null);
    setSelectedReport((prev) => (prev?.id === report.id ? null : report));
  };

  const handleSelectDlq = (item: DeadLetterItem) => {
    setSelectedReport(null);
    setSelectedDlq((prev) => (prev?.id === item.id ? null : item));
  };

  const handleCloseDrawer = () => {
    setSelectedReport(null);
    setSelectedDlq(null);
  };

  return (
    <div className="flex h-full flex-1 min-h-0 flex-col gap-2.5 p-2 sm:p-3 overflow-hidden">
      {/* Sub-Tab Navigation Header */}
      <div className="flex items-center justify-between border-b border-slate-200/80 bg-white px-4 py-2 rounded-xl shadow-subtle">
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setActiveSubTab("verified");
              handleCloseDrawer();
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeSubTab === "verified"
                ? "bg-emerald-50 text-cmcb-700 ring-1 ring-emerald-600/20 shadow-sm"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span>Verified Visits</span>
            <span className="rounded-full bg-emerald-100 px-1.5 py-0.2 font-mono text-[10px] text-emerald-800">
              {reports.length}
            </span>
          </button>

          <button
            onClick={() => {
              setActiveSubTab("uncaught");
              handleCloseDrawer();
            }}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeSubTab === "uncaught"
                ? "bg-amber-50 text-amber-800 ring-1 ring-amber-600/20 shadow-sm"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            }`}
          >
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
            <span>Uncaught Telegram Data (DLQ)</span>
            <span className={`rounded-full px-1.5 py-0.2 font-mono text-[10px] ${
              dlqItems.length > 0 ? "bg-amber-200 text-amber-900 font-bold" : "bg-slate-100 text-slate-500"
            }`}>
              {dlqItems.length}
            </span>
          </button>
        </div>

        <div className="hidden sm:block text-[11px] text-slate-400 font-medium">
          Direct database ledger &amp; audit inspection
        </div>
      </div>

      {/* Main Table Area with Drawer */}
      <div className="relative flex-1 min-h-0">
        {activeSubTab === "verified" && (
          <VerifiedVisitsTable
            reports={reports}
            uniqueKhans={uniqueKhans}
            selectedReportId={selectedReport?.id}
            onSelectReport={handleSelectReport}
          />
        )}

        {activeSubTab === "uncaught" && (
          <UncaughtDlqTable
            items={dlqItems}
            selectedDlqId={selectedDlq?.id}
            onSelectItem={handleSelectDlq}
          />
        )}

        {/* Slide-over detail drawer */}
        <RecordDetailDrawer
          selectedReport={selectedReport}
          selectedDlq={selectedDlq}
          onClose={handleCloseDrawer}
        />
      </div>
    </div>
  );
};
