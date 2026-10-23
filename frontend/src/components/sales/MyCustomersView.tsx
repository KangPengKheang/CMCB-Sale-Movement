import React from "react";
import {
  Search,
  Phone,
  Loader2,
} from "lucide-react";
import { useSales } from "../../context/SalesContext";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";
import { useHeadroom } from "../../hooks/useHeadroom";
import type { SalesCustomerItem } from "../../types";

function getTelegramUrl(phoneOrHandle?: string): string | null {
  if (!phoneOrHandle) return null;
  const raw = phoneOrHandle.trim();
  if (!raw || raw.toUpperCase() === "N/A" || raw.toUpperCase() === "NONE") return null;

  // Already a Telegram handle
  if (raw.startsWith("@")) return `https://t.me/${raw.slice(1)}`;

  // Plain alphanumeric handle
  if (/^[a-zA-Z0-9_]{4,}$/.test(raw) && !raw.toUpperCase().includes("TELEGRAM") && !raw.toUpperCase().includes("TG")) {
    return `https://t.me/${raw}`;
  }

  const digits = raw.replace(/[^\d]/g, "");
  if (!digits) return null;

  // Local Cambodian number 0XXXXXXXXX -> +855XXXXXXXXX
  if (digits.startsWith("0")) return `https://t.me/+855${digits.slice(1)}`;
  if (digits.startsWith("855")) return `https://t.me/+${digits}`;
  return `https://t.me/+${digits}`;
}

const CustomerCardBase: React.FC<{ item: SalesCustomerItem; onOpen: (id: number) => void }> = ({
  item,
  onOpen,
}) => {
  const isSigned = Boolean(
    item.is_onboarded || item.stage === "CONVERTED" || item.stage === "EXISTING"
  );
  const durationLabel = item.duration_label || item.due_badge || item.due_label || "Recent";
  const tgUrl = getTelegramUrl(item.phone);

  return (
    <div
      onClick={() => onOpen(item.id)}
      className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm hover:border-cmcb-300 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="min-w-0 flex-1 pr-3 space-y-1">
        <h3 className="text-sm lg:text-base font-extrabold text-slate-900 truncate">
          {item.name}
        </h3>

        <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium truncate">
          <span className="truncate">{item.business_category}</span>
          <span>·</span>
          <span className="truncate">Khan {item.district}</span>
        </div>

        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
          <Phone className="h-3 w-3 text-slate-400 shrink-0" />
          <span>{item.phone && item.phone !== "N/A" ? item.phone : "No phone listed"}</span>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold border ${
              isSigned
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${isSigned ? "bg-emerald-500" : "bg-rose-500"}`} />
            {isSigned ? "Signed" : "Not Signed"}
          </span>

          <span className="text-[10px] font-medium text-slate-500 bg-slate-100 rounded-md px-2 py-0.5">
            Last visit: {durationLabel}
          </span>
        </div>
      </div>

      {tgUrl ? (
        <a
          href={tgUrl}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          title={`Open Telegram with ${item.name}`}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-emerald-600 hover:bg-emerald-700 text-white shadow-md hover:scale-105 transition-all"
        >
          <svg className="h-5 w-5 fill-white -translate-x-0.5 translate-y-0.5" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.52 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
          </svg>
        </a>
      ) : (
        <div
          title="No Telegram handle or phone available"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-300"
        >
          <svg className="h-5 w-5 fill-slate-300 -translate-x-0.5 translate-y-0.5" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.52 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
          </svg>
        </div>
      )}
    </div>
  );
};

/**
 * Memoized: `item` objects keep their identity across page appends (the list is
 * built with `[...prev, ...new]`) and `onOpen` is a stable useCallback, so
 * already-mounted cards skip re-rendering when a new page arrives.
 */
const CustomerCard = React.memo(CustomerCardBase);

export const MyCustomersView: React.FC = () => {
  const {
    customerItems,
    customerSummary,
    customerTotal,
    customerHasMore,
    isCustomersLoading,
    isCustomersLoadingMore,
    loadMoreCustomers,
    customerStatus,
    setCustomerStatus,
    customerSort,
    setCustomerSort,
    customerSearch,
    setCustomerSearch,
    openMerchantDetail,
  } = useSales();
  const { isVisible: isHeaderVisible, handleScroll } = useHeadroom();

  const sentinelRef = useInfiniteScroll({
    onLoadMore: loadMoreCustomers,
    hasMore: customerHasMore,
    isLoading: isCustomersLoadingMore || isCustomersLoading,
  });

  const summary = customerSummary || { all_count: 0, pipeline_count: 0, converted_count: 0, target_count: 0 };
  const signedCount = (summary.converted_count || 0);
  const notSignedCount = Math.max(0, (summary.all_count || 0) - signedCount);

  const showInitialLoader = isCustomersLoading && customerItems.length === 0;

  return (
    <div
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto bg-slate-50/60 px-4 pb-4 lg:px-8 lg:pb-8 pt-0 space-y-4 max-w-4xl mx-auto w-full select-none"
    >
      {/* Sticky Top Controls: Search + Status Filter Chips + Sort Row */}
      <div
        className={`sticky top-0 z-20 bg-slate-50 pt-3 pb-2 space-y-2.5 transition-all duration-300 ease-in-out ${
          isHeaderVisible
            ? "translate-y-0 opacity-100 pointer-events-auto"
            : "-translate-y-full opacity-0 pointer-events-none"
        }`}
      >
      <div className="relative">
        <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
        <input
          type="text"
          value={customerSearch}
          onChange={(e) => setCustomerSearch(e.target.value)}
          placeholder="Search by store name, phone, district..."
          className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-xs lg:text-sm font-semibold text-slate-800 placeholder-slate-400 shadow-sm focus:border-cmcb-600 focus:outline-none focus:ring-1 focus:ring-cmcb-600"
        />
      </div>

      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
        <button
          onClick={() => setCustomerStatus("ALL")}
          className={`rounded-full px-4 py-1.5 text-xs font-bold transition-all shrink-0 ${
            customerStatus === "ALL"
              ? "bg-cmcb-700 text-white shadow-sm"
              : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
          }`}
        >
          All ({summary.all_count || 0})
        </button>

        <button
          onClick={() => setCustomerStatus("SIGNED")}
          className={`rounded-full px-4 py-1.5 text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
            customerStatus === "SIGNED"
              ? "bg-emerald-600 text-white shadow-sm"
              : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
          }`}
        >
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Signed ({signedCount})
        </button>

        <button
          onClick={() => setCustomerStatus("NOT_SIGNED")}
          className={`rounded-full px-4 py-1.5 text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
            customerStatus === "NOT_SIGNED"
              ? "bg-rose-600 text-white shadow-sm"
              : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
          }`}
        >
          <span className="h-2 w-2 rounded-full bg-rose-500" />
          Not Signed ({notSignedCount})
        </button>
      </div>

      <div className="flex items-center justify-between text-xs font-semibold text-slate-500 px-1">
        <span>
          {customerItems.length} of {customerTotal} stores
        </span>
        <div className="flex items-center gap-1.5">
          <span>Sort:</span>
          <select
            value={customerSort}
            onChange={(e) => setCustomerSort(e.target.value as "recent" | "longest_unvisited" | "name")}
            className="rounded-lg border-0 bg-transparent py-0.5 text-xs font-bold text-cmcb-700 focus:outline-none cursor-pointer"
          >
            <option value="recent">Most recently visited</option>
            <option value="longest_unvisited">Longest unvisited</option>
            <option value="name">Store name (A-Z)</option>
          </select>
        </div>
      </div>
      </div>

      <div className="space-y-3">
        {showInitialLoader ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin text-cmcb-700" />
            <p className="mt-2 text-xs font-semibold">Loading your customers...</p>
          </div>
        ) : customerItems.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400 bg-white rounded-2xl border border-slate-200">
            No customers match your search or filter.
          </div>
        ) : (
          <>
            {customerItems.map((item) => (
              <CustomerCard key={item.id} item={item} onOpen={openMerchantDetail} />
            ))}

            {/* Infinite-scroll sentinel + explicit fallback */}
            <div ref={sentinelRef} className="pt-2 flex flex-col items-center gap-2">
              {isCustomersLoadingMore && (
                <span className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin text-cmcb-700" />
                  Loading more stores...
                </span>
              )}
              {customerHasMore && !isCustomersLoadingMore && (
                <button
                  onClick={() => loadMoreCustomers()}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-cmcb-700 shadow-sm hover:bg-slate-50 transition-colors"
                >
                  Load more
                </button>
              )}
              {!customerHasMore && (
                <span className="text-[11px] font-medium text-slate-400">
                  All {customerItems.length} stores loaded
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
