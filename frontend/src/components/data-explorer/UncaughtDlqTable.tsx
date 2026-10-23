import React, { useState, useMemo } from "react";
import {
  AlertTriangle,
  Search,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  User,
  FileText,
  MapPinOff,
} from "lucide-react";
import type { DeadLetterItem } from "../../types";

interface UncaughtDlqTableProps {
  items: DeadLetterItem[];
  selectedDlqId?: number;
  onSelectItem: (item: DeadLetterItem) => void;
}

export const UncaughtDlqTable: React.FC<UncaughtDlqTableProps> = ({
  items,
  selectedDlqId,
  onSelectItem,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIssueType, setSelectedIssueType] = useState("all");
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Classify issues
  const classifyIssue = (reason: string) => {
    const r = (reason || "").toLowerCase();
    if (r.includes("location") || r.includes("gps") || r.includes("pin")) {
      return {
        label: "Missing GPS Pin",
        color: "bg-amber-50 text-amber-800 border-amber-200",
        icon: MapPinOff,
        key: "gps",
      };
    }
    if (r.includes("blank") || r.includes("empty") || r.includes("template")) {
      return {
        label: "Blank Form Template",
        color: "bg-red-50 text-red-800 border-red-200",
        icon: FileText,
        key: "blank",
      };
    }
    return {
      label: "Unparsed Format",
      color: "bg-slate-100 text-slate-700 border-slate-200",
      icon: AlertTriangle,
      key: "other",
    };
  };

  // KPIs
  const totalItems = items.length;
  const missingGpsCount = useMemo(
    () => items.filter((i) => classifyIssue(i.reason).key === "gps").length,
    [items]
  );
  const blankFormCount = useMemo(
    () => items.filter((i) => classifyIssue(i.reason).key === "blank").length,
    [items]
  );

  // Filter items
  const filtered = useMemo(() => {
    return items.filter((item) => {
      // Issue type filter
      if (selectedIssueType !== "all") {
        const issue = classifyIssue(item.reason);
        if (issue.key !== selectedIssueType) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const sName = (item.sender_name || "").toLowerCase();
        const rText = (item.raw_content || "").toLowerCase();
        const reason = (item.reason || "").toLowerCase();
        if (!sName.includes(q) && !rText.includes(q) && !reason.includes(q)) {
          return false;
        }
      }

      return true;
    });
  }, [items, selectedIssueType, searchQuery]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, currentPage]);

  const handleCopyRaw = (e: React.MouseEvent, item: DeadLetterItem) => {
    e.stopPropagation();
    if (!item.raw_content) return;
    navigator.clipboard.writeText(item.raw_content);
    setCopiedId(item.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-subtle">
      {/* Top Issue Summary Strip */}
      <div className="grid grid-cols-3 gap-2 border-b border-slate-100 p-3 bg-slate-50/70">
        <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white p-2.5 shadow-subtle">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-red-50 text-red-600">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div>
            <span className="font-mono text-base font-bold text-slate-900 tabular-nums">
              {totalItems}
            </span>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Total Uncaught Items
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white p-2.5 shadow-subtle">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-amber-50 text-amber-600">
            <MapPinOff className="h-4 w-4" />
          </div>
          <div>
            <span className="font-mono text-base font-bold text-amber-700 tabular-nums">
              {missingGpsCount}
            </span>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Missing GPS Pin (&gt;15m)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white p-2.5 shadow-subtle">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-slate-100 text-slate-600">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <span className="font-mono text-base font-bold text-slate-800 tabular-nums">
              {blankFormCount}
            </span>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Blank / Incomplete Form
            </p>
          </div>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-slate-100 p-3">
        <div className="flex flex-1 flex-wrap items-center gap-2 min-w-[240px]">
          <div className="relative min-w-[200px] flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search sender, failure reason, message text..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          <select
            value={selectedIssueType}
            onChange={(e) => {
              setSelectedIssueType(e.target.value);
              setCurrentPage(1);
            }}
            className="h-8 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 transition-colors focus:border-emerald-500 focus:outline-none"
          >
            <option value="all">All Issue Types</option>
            <option value="gps">📍 Missing GPS Location</option>
            <option value="blank">📝 Blank Form Template</option>
            <option value="other">⚪ Unparsed Format</option>
          </select>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Showing <strong className="font-mono text-slate-900">{filtered.length}</strong> uncaught items
        </div>
      </div>

      {/* Table Area with sticky header */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-100/95 backdrop-blur font-bold uppercase tracking-wider text-[10px] text-slate-600">
            <tr>
              <th className="px-3.5 py-2.5">Date &amp; Time</th>
              <th className="px-3.5 py-2.5">Sales Rep</th>
              <th className="px-3.5 py-2.5">Issue Category</th>
              <th className="px-3.5 py-2.5">Correlation Failure Reason</th>
              <th className="px-3.5 py-2.5">Raw Telegram Content</th>
              <th className="px-3.5 py-2.5 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {paginatedRows.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400">
                  No uncaught Telegram items found matching filters.
                </td>
              </tr>
            ) : (
              paginatedRows.map((row) => {
                const issue = classifyIssue(row.reason);
                const IssueIcon = issue.icon;
                const dateStr = row.msg_date
                  ? new Date(row.msg_date).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "2-digit",
                    })
                  : "";
                const timeStr = row.msg_date
                  ? new Date(row.msg_date).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "";
                const isCopied = copiedId === row.id;
                const isSelected = selectedDlqId === row.id;

                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelectItem(row)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-amber-50/90 hover:bg-amber-100/80 border-l-4 border-l-amber-600 shadow-2xs font-medium"
                        : "hover:bg-slate-50/90"
                    }`}
                  >
                    {/* Date */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 font-mono text-[11px] text-slate-700">
                      <div>{dateStr}</div>
                      <div className="text-[10px] text-slate-400">{timeStr}</div>
                    </td>

                    {/* Sales Rep */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 text-slate-800 font-semibold">
                      {row.sender_name || "Unknown"}
                    </td>

                    {/* Issue Category Badge */}
                    <td className="whitespace-nowrap px-3.5 py-2.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-bold ${issue.color}`}
                      >
                        <IssueIcon className="h-3 w-3" />
                        {issue.label}
                      </span>
                    </td>

                    {/* Reason */}
                    <td className="px-3.5 py-2.5 text-slate-700 font-medium max-w-[260px] truncate" title={row.reason}>
                      {row.reason}
                    </td>

                    {/* Raw Content Preview */}
                    <td className="px-3.5 py-2.5 font-mono text-[11px] text-slate-500 max-w-[300px] truncate">
                      {row.raw_content ? row.raw_content.replace(/\n/g, " · ") : "—"}
                    </td>

                    {/* Copy Button */}
                    <td className="whitespace-nowrap px-3.5 py-2.5 text-center">
                      <button
                        onClick={(e) => handleCopyRaw(e, row)}
                        className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold transition-colors ${
                          isCopied
                            ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                            : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                        }`}
                        title="Copy raw message content to clipboard"
                      >
                        {isCopied ? (
                          <>
                            <Check className="h-3 w-3" />
                            <span>Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
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
          <strong className="font-mono text-slate-900">{Math.min(currentPage * pageSize, filtered.length)}</strong> of{" "}
          <strong className="font-mono text-slate-900">{filtered.length}</strong> items
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
