import React, { useState } from "react";
import {
  X,
  Copy,
  Check,
  ExternalLink,
  Phone,
  Calendar,
  User,
  AlertTriangle,
  Building,
  DollarSign,
  Tag,
  MapPin,
  Image,
  FileText,
} from "lucide-react";
import type { DeadLetterItem, RawVisitReport } from "../../types";

interface RecordDetailDrawerProps {
  selectedReport: RawVisitReport | null;
  selectedDlq: DeadLetterItem | null;
  onClose: () => void;
}

function formatEstimatedUSD(amountRaw?: string): string {
  if (!amountRaw) return "—";
  const str = String(amountRaw).trim();
  if (!str || /^(n\/?a|none|no|0|-|\?)$/i.test(str)) return "—";

  const digits = str.replace(/[^\d.]/g, "");
  const num = parseFloat(digits);
  if (!isNaN(num) && num > 0) {
    return `$${num.toLocaleString()}`;
  }
  return str;
}

function getStatusBadge(report?: RawVisitReport): { style: string; label: string } {
  if (!report) return { style: "bg-slate-50 border-slate-200 text-slate-500", label: "—" };
  const rawStatus = report.status_clean || report.status || "";
  const s = String(rawStatus || "").toLowerCase().trim();
  const r = String(report.remark || "").toLowerCase().trim();
  const stage = String(report.khqr_stage || "").toUpperCase().trim();

  const isSigned =
    stage === "CONVERTED" ||
    stage === "SIGNED" ||
    stage === "EXISTING" ||
    report.has_cmcb === 1 ||
    s.includes("deploy") ||
    s.includes("sign") ||
    s.includes("exist") ||
    s.includes("convert") ||
    /\b(sign|signed|signing|deploy|deployed|open\s*khqr)\b/i.test(r);

  if (isSigned) {
    return { style: "bg-emerald-50 border-emerald-300 text-emerald-800", label: "Signed" };
  }
  if (s.includes("follow") || s.includes("pipe") || s.includes("ap") || stage === "PIPELINE") {
    return { style: "bg-sky-50 border-sky-300 text-sky-800", label: rawStatus || "Follow Up" };
  }
  if (s.includes("not") || s.includes("reject") || s.includes("refuse")) {
    return { style: "bg-rose-50 border-rose-300 text-rose-800", label: rawStatus || "Not Interested" };
  }
  return { style: "bg-indigo-50 border-indigo-200 text-indigo-800", label: rawStatus || "Target" };
}

function getPotentialBadge(level?: string): { style: string; label: string } {
  const p = String(level || "").toUpperCase().trim();
  if (p === "H" || p === "HIGH") {
    return { style: "bg-amber-50 border-amber-300 text-amber-900", label: "High (H)" };
  }
  if (p === "M" || p === "MEDIUM") {
    return { style: "bg-sky-50 border-sky-200 text-sky-800", label: "Medium (M)" };
  }
  if (p === "L" || p === "LOW") {
    return { style: "bg-slate-100 border-slate-200 text-slate-600", label: "Low (L)" };
  }
  return { style: "bg-slate-50 border-slate-200 text-slate-400", label: "—" };
}

export const RecordDetailDrawer: React.FC<RecordDetailDrawerProps> = ({
  selectedReport,
  selectedDlq,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  if (!selectedReport && !selectedDlq) return null;

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="absolute inset-y-0 right-0 z-[1000] flex w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-drawer transition-transform animate-in slide-in-from-right duration-200 sm:w-[480px]">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-100 p-4 bg-slate-50/60">
        <div className="min-w-0 flex-1 pr-2">
          {selectedReport && (
            <>
              <div className="flex items-center gap-2">
                <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-200">
                  Verified Visit Report #{selectedReport.id}
                </span>
                <span className="font-mono text-xs text-slate-500">
                  {new Date(selectedReport.report_time).toLocaleDateString()}
                </span>
              </div>
              <h2 className="mt-1.5 font-display text-base font-bold text-slate-900 truncate">
                {selectedReport.merchant_name}
              </h2>
              <p className="text-xs text-slate-500 font-medium">
                {selectedReport.business_clean || selectedReport.business || "Retail"} · Khan {selectedReport.district_khan}
              </p>
            </>
          )}

          {selectedDlq && (
            <>
              <div className="flex items-center gap-2">
                <span className="rounded bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200 flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Uncaught Telegram Item #{selectedDlq.id}
                </span>
                <span className="font-mono text-xs text-slate-500">
                  {new Date(selectedDlq.msg_date).toLocaleDateString()}
                </span>
              </div>
              <h2 className="mt-1.5 font-display text-base font-bold text-slate-900 truncate">
                {selectedDlq.reason}
              </h2>
              <p className="text-xs text-slate-500 font-medium">
                Sales Rep: <strong className="text-slate-700">{selectedDlq.sender_name}</strong>
              </p>
            </>
          )}
        </div>

        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          title="Close drawer"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Scroll Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* VIEW 1: VERIFIED VISIT RECORD */}
        {selectedReport && (
          <>
            {/* Quick Actions */}
            <div className="grid grid-cols-2 gap-2">
              {selectedReport.tel && (
                <a
                  href={`tel:${selectedReport.tel}`}
                  className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  <Phone className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="truncate">{selectedReport.tel_clean || selectedReport.tel}</span>
                </a>
              )}
              {selectedReport.latitude && selectedReport.longitude && (
                <a
                  href={selectedReport.map_url || `https://www.google.com/maps?q=${selectedReport.latitude},${selectedReport.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  <ExternalLink className="h-3.5 w-3.5 text-blue-600" />
                  <span>Google Maps</span>
                </a>
              )}
            </div>

            {/* Top Highlights: Compact & Color-coded Status & Potential */}
            {(() => {
              const status = getStatusBadge(selectedReport);
              const potential = getPotentialBadge(selectedReport.potential_level);
              return (
                <div className="flex items-center gap-2">
                  <div className={`flex-1 flex items-center justify-between rounded-lg border px-3 py-1.5 shadow-2xs ${status.style}`}>
                    <span className="text-[10px] font-bold uppercase tracking-wider opacity-75 font-mono">Status:</span>
                    <span className="text-xs font-black tracking-tight">{status.label}</span>
                  </div>
                  <div className={`flex-1 flex items-center justify-between rounded-lg border px-3 py-1.5 shadow-2xs ${potential.style}`}>
                    <span className="text-[10px] font-bold uppercase tracking-wider opacity-75 font-mono">Potential:</span>
                    <span className="text-xs font-black tracking-tight">{potential.label}</span>
                  </div>
                </div>
              );
            })()}

            {/* Prominent Remark Card at Top */}
            <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-3.5 text-xs">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800/80 block mb-1 font-mono">
                Remark
              </span>
              {selectedReport.remark ? (
                <p className="text-xs italic font-medium text-slate-800 leading-relaxed">
                  "{selectedReport.remark}"
                </p>
              ) : (
                <p className="text-xs text-slate-400 italic">No remark provided</p>
              )}
            </div>

            {/* Standardized Field List */}
            <div className="rounded-xl border border-slate-200/90 bg-white shadow-subtle overflow-hidden">
              <div className="divide-y divide-slate-100 text-xs">
                {/* 1. Name */}
                <div className="flex items-start px-4 py-2.5 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Name:</span>
                  <span className="font-bold text-slate-900 break-words flex-1">{selectedReport.merchant_name || "—"}</span>
                </div>

                {/* 2. Business */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Business:</span>
                  <span className="text-slate-800 font-medium flex-1">{selectedReport.business_clean || selectedReport.business || "—"}</span>
                </div>

                {/* 3. Purpose */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Purpose:</span>
                  <span className="text-slate-800 font-medium flex-1">{selectedReport.purpose || "—"}</span>
                </div>

                {/* 4. Bank */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Bank:</span>
                  <span className="font-semibold text-slate-800 flex-1">{selectedReport.bank || "—"}</span>
                </div>

                {/* 5. Amount */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Amount:</span>
                  <span className="font-mono text-slate-800 flex-1">{selectedReport.amount || "—"}</span>
                </div>

                {/* 6. Interest */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Interest:</span>
                  <span className="font-mono text-slate-800 flex-1">{selectedReport.interest || "—"}</span>
                </div>

                {/* 7. Loan Type */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Loan Type:</span>
                  <span className="text-slate-800 flex-1">{selectedReport.loan_type || "—"}</span>
                </div>

                {/* 8. Tenure */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Tenure:</span>
                  <span className="font-mono text-slate-800 flex-1">{selectedReport.tenure || "—"}</span>
                </div>

                {/* 9. Maturity */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Maturity:</span>
                  <span className="font-mono text-slate-800 flex-1">{selectedReport.maturity || "—"}</span>
                </div>

                {/* 10. Estimated_USD */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Estimated_USD:</span>
                  <span className="font-mono font-bold text-emerald-800 flex-1">
                    {formatEstimatedUSD(selectedReport.amount)}
                  </span>
                </div>

                {/* 11. Potential Product */}
                <div className="flex items-center px-4 py-2 hover:bg-slate-50/60 transition-colors">
                  <span className="w-36 shrink-0 font-mono text-[11px] font-bold text-slate-500">Potential Product:</span>
                  <span className="font-semibold text-slate-800 flex-1">{selectedReport.potential_product || "—"}</span>
                </div>
              </div>
            </div>

            {/* Photo count banner */}
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50/70 px-3.5 py-2 text-xs text-slate-600">
              <div className="flex items-center gap-1.5">
                <Image className="h-3.5 w-3.5 text-slate-400" />
                <span>Photos Attached:</span>
              </div>
              <strong className="font-mono text-slate-900">{selectedReport.photo_count || 1} photo(s)</strong>
            </div>
          </>
        )}

        {/* VIEW 2: UNCAUGHT TELEGRAM ITEM (DLQ) */}
        {selectedDlq && (
          <>
            {/* Action Card for Supervisor */}
            <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5 text-xs">
              <h3 className="font-bold text-amber-900 flex items-center gap-1.5">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Supervisor Action Required
              </h3>
              <p className="mt-1 text-amber-800">
                This message arrived from Telegram but was not correlated into verified visits because:
                <strong className="block mt-0.5">{selectedDlq.reason}</strong>
              </p>
            </div>

            {/* Raw Telegram Message Viewer */}
            <div className="rounded-xl border border-slate-200/80 bg-white p-3.5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h3 className="font-display text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-slate-400" />
                  Raw Message Payload
                </h3>
                {selectedDlq.raw_content && (
                  <button
                    onClick={() => handleCopyText(selectedDlq.raw_content!)}
                    className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-semibold border transition-colors ${
                      copied
                        ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copied ? "Copied" : "Copy Raw"}</span>
                  </button>
                )}
              </div>

              <div className="mt-2.5 max-h-72 overflow-y-auto rounded-lg bg-slate-900 p-3 text-[11px] font-mono text-emerald-400 leading-relaxed whitespace-pre-wrap selection:bg-emerald-900">
                {selectedDlq.raw_content || "No raw text content available for this message."}
              </div>

              <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-100 pt-2">
                <span>Telegram Msg ID: <strong className="font-mono text-slate-600">{selectedDlq.msg_id}</strong></span>
                <span>Type: <strong className="text-slate-600">{selectedDlq.message_type}</strong></span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
