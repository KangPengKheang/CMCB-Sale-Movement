import { useSession } from "../../context/SessionContext";
import React, { useState, useMemo } from "react";
import {
  Search,
  Filter,
  Download,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Tag,
  Phone,
  CheckCircle2,
  Clock,
  Image,
  ArrowUpDown,
} from "lucide-react";
import type { RawVisitReport } from "../../types";

interface VerifiedVisitsTableProps {
  reports: RawVisitReport[];
  uniqueKhans: string[];
  selectedReportId?: number;
  onSelectReport: (report: RawVisitReport) => void;
}

type SortColumn = "date" | "merchant" | "district" | "sender";
interface BankBadge {
  code: string;
  name: string;
  style: string;
}

const KNOWN_BANKS: Array<{
  code: string;
  name: string;
  pattern: RegExp;
  style: string;
}> = [
  {
    code: "CMCB",
    name: "CMCB",
    pattern: /\b(cmcb|chip\s*mong|chipmong)\b/i,
    style: "bg-emerald-50 text-emerald-800 border-emerald-200",
  },
  {
    code: "ABA",
    name: "ABA",
    pattern: /\b(aba|bab)\b/i,
    style: "bg-sky-50 text-sky-800 border-sky-200",
  },
  {
    code: "ACLEDA",
    name: "ACLEDA",
    pattern: /\b(acleda|ackeda|acelida|ac)\b/i,
    style: "bg-amber-50 text-amber-800 border-amber-200",
  },
  {
    code: "WING",
    name: "Wing",
    pattern: /\bwing\b/i,
    style: "bg-purple-50 text-purple-800 border-purple-200",
  },
  {
    code: "CANADIA",
    name: "Canadia",
    pattern: /\b(canadia|cnb)\b/i,
    style: "bg-rose-50 text-rose-800 border-rose-200",
  },
  {
    code: "KB",
    name: "KB Prasac",
    pattern: /\b(kb\s*prasac|prasac|kb)\b/i,
    style: "bg-indigo-50 text-indigo-800 border-indigo-200",
  },
  {
    code: "SATHAPANA",
    name: "Sathapana",
    pattern: /\b(sathapana|spn)\b/i,
    style: "bg-blue-50 text-blue-800 border-blue-200",
  },
  {
    code: "AMRET",
    name: "Amret",
    pattern: /\bamret\b/i,
    style: "bg-teal-50 text-teal-800 border-teal-200",
  },
  {
    code: "PHILLIP",
    name: "Phillip",
    pattern: /\b(phillip|philip|filip)\b/i,
    style: "bg-cyan-50 text-cyan-800 border-cyan-200",
  },
  {
    code: "WOORI",
    name: "Woori",
    pattern: /\b(woori|worri)\b/i,
    style: "bg-slate-100 text-slate-800 border-slate-300",
  },
  {
    code: "DGB",
    name: "DGB",
    pattern: /\bdgb\b/i,
    style: "bg-orange-50 text-orange-800 border-orange-200",
  },
  {
    code: "MB",
    name: "MB Bank",
    pattern: /\bmb(\s*bank)?\b/i,
    style: "bg-red-50 text-red-800 border-red-200",
  },
  {
    code: "BOC",
    name: "Bank of China",
    pattern: /\b(bank\s*of\s*china|china\s*bank|boc)\b/i,
    style: "bg-yellow-50 text-yellow-800 border-yellow-200",
  },
  {
    code: "MAYBANK",
    name: "Maybank",
    pattern: /\bmay\s*bank\b/i,
    style: "bg-amber-100 text-amber-900 border-amber-300",
  },
  {
    code: "PRINCE",
    name: "Prince",
    pattern: /\bprince\b/i,
    style: "bg-violet-50 text-violet-800 border-violet-200",
  },
  {
    code: "FTB",
    name: "FTB",
    pattern: /\bftb\b/i,
    style: "bg-emerald-100 text-emerald-900 border-emerald-300",
  },
];

function extractBankBadges(row: RawVisitReport): BankBadge[] {
  const badges: BankBadge[] = [];
  const raw = String(row.bank || "").trim();
  const lower = raw.toLowerCase();

  for (const b of KNOWN_BANKS) {
    let matched = false;
    if (b.code === "CMCB" && row.has_cmcb === 1) matched = true;
    else if (b.code === "ABA" && row.has_aba === 1) matched = true;
    else if (b.code === "ACLEDA" && row.has_acleda === 1) matched = true;
    else if (b.pattern.test(lower)) matched = true;

    if (matched) {
      badges.push({ code: b.code, name: b.name, style: b.style });
    }
  }

  if (badges.length === 0) {
    if (row.has_other_bank === 1 || (raw && !/^(n\/?a|none|no|0|-|\?)$/i.test(raw))) {
      const cleanName = raw.replace(/\([^)]*\)/g, "").replace(/[,./]/g, " ").trim();
      badges.push({
        code: "OTHER",
        name: cleanName ? cleanName.slice(0, 15) : "Other Bank",
        style: "bg-slate-100 text-slate-700 border-slate-300",
      });
    }
  }

  return badges;
}

export const VerifiedVisitsTable: React.FC<VerifiedVisitsTableProps> = ({
  reports,
  uniqueKhans,
  selectedReportId,
  onSelectReport,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedKhan, setSelectedKhan] = useState("all");
  const [selectedStage, setSelectedStage] = useState("all");
  const [sortCol, setSortCol] = useState<SortColumn>("date");
  const [sortAsc, setSortAsc] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Filter logic
  const filtered = useMemo(() => {
    return reports.filter((r) => {
      // Khan filter
      if (selectedKhan !== "all") {
        const k = (r.district_khan || "").toLowerCase();
        if (k !== selectedKhan.toLowerCase()) return false;
      }

      // Stage filter
      if (selectedStage !== "all") {
        const s = (r.khqr_stage || "").toUpperCase();
        if (selectedStage === "CONVERTED" && s !== "CONVERTED") return false;
        if (selectedStage === "PIPELINE" && s !== "PIPELINE") return false;
        if (selectedStage === "TARGET" && s !== "TARGET") return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const mName = (r.merchant_name || "").toLowerCase();
        const sName = (r.sender_name || "").toLowerCase();
        const tel = (r.tel || r.tel_clean || "").toLowerCase();
        const remark = (r.remark || "").toLowerCase();
        const bus = (r.business || r.business_clean || "").toLowerCase();
        const bank = (r.bank || "").toLowerCase();
        if (!mName.includes(q) && !sName.includes(q) && !tel.includes(q) && !remark.includes(q) && !bus.includes(q) && !bank.includes(q)) {
          return false;
        }
      }

      return true;
    });
  }, [reports, selectedKhan, selectedStage, searchQuery]);

  // Sort logic
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      if (sortCol === "date") {
        cmp = new Date(a.report_time).getTime() - new Date(b.report_time).getTime();
      } else if (sortCol === "merchant") {
        cmp = a.merchant_name.localeCompare(b.merchant_name);
      } else if (sortCol === "district") {
        cmp = (a.district_khan || "").localeCompare(b.district_khan || "");
      } else if (sortCol === "sender") {
        cmp = a.sender_name.localeCompare(b.sender_name);
      }
      return sortAsc ? cmp : -cmp;
    });
  }, [filtered, sortCol, sortAsc]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, currentPage]);

  const handleSort = (col: SortColumn) => {
    if (sortCol === col) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(col);
      setSortAsc(false); // default newest or desc
    }
  };

  const session = useSession();

  const handleExportExcel = () => {
    window.open("/api/reports/export/excel", "_blank");
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-subtle">
      {/* Table Filter & Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-slate-100 p-3 bg-slate-50/50">
        <div className="flex flex-1 flex-wrap items-center gap-2 min-w-[240px]">
          {/* Search Box */}
          <div className="relative min-w-[200px] flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search merchant, RM, telephone, remarks..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          {/* Khan Filter */}
          <select
            value={selectedKhan}
            onChange={(e) => {
              setSelectedKhan(e.target.value);
              setCurrentPage(1);
            }}
            className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 transition-colors focus:border-emerald-500 focus:outline-none"
          >
            <option value="all">All Khans ({uniqueKhans.length})</option>
            {uniqueKhans.map((k) => (
              <option key={k} value={k}>
                Khan {k}
              </option>
            ))}
          </select>

          {/* Stage Filter */}
          <select
            value={selectedStage}
            onChange={(e) => {
              setSelectedStage(e.target.value);
              setCurrentPage(1);
            }}
            className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 transition-colors focus:border-emerald-500 focus:outline-none"
          >
            <option value="all">All Stages</option>
            <option value="CONVERTED">🟢 CMCB Deployed</option>
            <option value="PIPELINE">🔵 Pipeline</option>
            <option value="TARGET">🔴 Target / Prospect</option>
          </select>
        </div>

        {/* Excel Export Button */}
        <button
          onClick={handleExportExcel}
          disabled={!session?.all_sources}
          className="flex h-8 items-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-50 px-3 text-xs font-bold text-cmcb-700 transition-colors hover:bg-emerald-100 shadow-sm"
          title={session?.all_sources ? "Download verified visits as formatted Excel workbook" : "This export requires access to all sources."}
        >
          <Download className="h-3.5 w-3.5" />
          <span>Export Excel</span>
        </button>
      </div>

      {/* Main Table Area with sticky header */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-100/95 backdrop-blur font-bold uppercase tracking-wider text-[10px] text-slate-600">
            <tr>
              <th
                onClick={() => handleSort("date")}
                className="cursor-pointer px-3.5 py-2.5 hover:text-slate-900"
              >
                <div className="flex items-center gap-1">
                  <span>Date &amp; Time</span>
                  <ArrowUpDown className="h-3 w-3 text-slate-400" />
                </div>
              </th>
              <th
                onClick={() => handleSort("merchant")}
                className="cursor-pointer px-3.5 py-2.5 hover:text-slate-900"
              >
                <div className="flex items-center gap-1">
                  <span>Merchant / Store</span>
                  <ArrowUpDown className="h-3 w-3 text-slate-400" />
                </div>
              </th>
              <th
                onClick={() => handleSort("district")}
                className="cursor-pointer px-3.5 py-2.5 hover:text-slate-900"
              >
                <div className="flex items-center gap-1">
                  <span>District</span>
                  <ArrowUpDown className="h-3 w-3 text-slate-400" />
                </div>
              </th>
              <th
                onClick={() => handleSort("sender")}
                className="cursor-pointer px-3.5 py-2.5 hover:text-slate-900"
              >
                <div className="flex items-center gap-1">
                  <span>Sales Rep</span>
                  <ArrowUpDown className="h-3 w-3 text-slate-400" />
                </div>
              </th>
              <th className="px-3.5 py-2.5">Telephone</th>
              <th className="px-3.5 py-2.5">Banking</th>
              <th className="px-3.5 py-2.5">Stage</th>
              <th className="px-3.5 py-2.5">Remark</th>
              <th className="px-3.5 py-2.5 text-center">GPS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {paginatedRows.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-slate-400">
                  No verified visit reports match the selected filters.
                </td>
              </tr>
            ) : (
              paginatedRows.map((row) => {
                const isCMCB =
                  row.has_cmcb === 1 || (row.khqr_stage || "").toUpperCase() === "CONVERTED";
                const dateStr = row.report_time
                  ? new Date(row.report_time).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "2-digit",
                    })
                  : "";
                const timeStr = row.report_time
                  ? new Date(row.report_time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "";

                const isSelected = selectedReportId === row.id;

                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelectReport(row)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-emerald-50/90 hover:bg-emerald-100/80 border-l-4 border-l-emerald-600 shadow-2xs font-medium"
                        : "hover:bg-slate-50/90"
                    }`}
                  >
                    {/* Date & Time */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[11px] text-slate-700">
                      <div>{dateStr}</div>
                      <div className="text-[10px] text-slate-400">{timeStr}</div>
                    </td>

                    {/* Merchant & Business */}
                    <td className="px-3.5 py-2.5">
                      <div className="font-display font-bold text-slate-900 max-w-[200px] truncate">
                        {row.merchant_name}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate max-w-[180px]">
                        {row.business_clean || row.business || "Retail"}
                      </div>
                    </td>

                    {/* District */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 text-slate-700 font-medium">
                      Khan {row.district_khan || "Phnom Penh"}
                    </td>

                    {/* Sales Rep */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 text-slate-800 font-semibold">
                      {row.sender_name}
                    </td>

                    {/* Telephone */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-slate-600">
                      {row.tel_clean || row.tel || "—"}
                    </td>

                    {/* Banking Badges */}
                    <td className="px-3.5 py-2.5">
                      <div className="flex items-center gap-1 flex-wrap max-w-[220px]">
                        {extractBankBadges(row).map((b) => (
                          <span
                            key={b.code}
                            className={`rounded px-1.5 py-0.5 text-[9px] font-bold border ${b.style}`}
                          >
                            {b.name}
                          </span>
                        ))}
                        {extractBankBadges(row).length === 0 && (
                          <span className="text-[11px] text-slate-400">—</span>
                        )}
                      </div>
                    </td>

                    {/* Lifecycle Stage */}
                    <td className="whitespace-nowrap px-3.5 py-2.5">
                      <span
                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-bold ${
                          isCMCB
                            ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                            : "bg-red-50 text-red-800 border border-red-200"
                        }`}
                      >
                        {isCMCB ? "CMCB Signed" : "Target"}
                      </span>
                    </td>

                    {/* Remarks */}
                    <td className="px-3.5 py-2.5 text-slate-600 max-w-[200px] truncate" title={row.remark || ""}>
                      {row.remark ? `"${row.remark}"` : "—"}
                    </td>

                    {/* GPS Coordinates link */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 text-center">
                      {row.map_url || (row.latitude && row.longitude) ? (
                        <a
                          href={row.map_url || `https://www.google.com/maps?q=${row.latitude},${row.longitude}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center justify-center text-slate-400 hover:text-blue-600"
                          title="Open coordinates in Google Maps"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 bg-slate-50/50 text-xs text-slate-600">
        <div>
          Showing <strong className="font-mono text-slate-900">{paginatedRows.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}</strong>–
          <strong className="font-mono text-slate-900">{Math.min(currentPage * pageSize, sorted.length)}</strong> of{" "}
          <strong className="font-mono text-slate-900">{sorted.length}</strong> reports
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500 font-medium">
            Page {currentPage} of {totalPages}
          </span>
          <div className="inline-flex rounded-lg border border-slate-200 bg-white">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1 text-slate-600 hover:bg-slate-50 disabled:opacity-30"
              title="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="border-l border-slate-200 p-1 text-slate-600 hover:bg-slate-50 disabled:opacity-30"
              title="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
