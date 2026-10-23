import React, { useState, useMemo, useRef } from "react";
import {
  Search,
  MapPin,
  Camera,
  Loader2,
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  X,
  Clock,
} from "lucide-react";
import { useSales } from "../../context/SalesContext";
import { useInfiniteScroll } from "../../hooks/useInfiniteScroll";
import { useHeadroom } from "../../hooks/useHeadroom";
import type { SalesVisitItem, SalesVisitGroup } from "../../types";

function delay(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}
const VisitCardBase: React.FC<{ visit: SalesVisitItem; onOpen: (id: number) => void }> = ({
  visit,
  onOpen,
}) => {
  // Strictly Binary Status: Signed vs Not Signed (no OP, AP, etc.)
  const isSigned = Boolean(
    visit.khqr_stage === "CONVERTED" ||
    visit.khqr_stage === "EXISTING" ||
    (visit.outcome && visit.outcome.toLowerCase().includes("exist")) ||
    (visit.outcome && visit.outcome.toLowerCase().includes("sign"))
  );

  return (
    <div
      onClick={() => onOpen(visit.merchant_id)}
      className="flex items-center justify-between rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm hover:border-cmcb-300 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="min-w-0 flex-1 pr-3 space-y-1">
        {/* Store Name & Time */}
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm lg:text-base font-extrabold text-slate-900 truncate">
            {visit.name}
          </h3>
          <span className="text-xs font-semibold text-slate-400 shrink-0">{visit.time}</span>
        </div>

        {/* District & Location */}
        <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
          <MapPin className="h-3 w-3 text-slate-400 shrink-0" />
          <span className="truncate">Khan {visit.district}</span>
          {visit.phone && visit.phone !== "N/A" && (
            <>
              <span>·</span>
              <span className="font-mono text-slate-600 truncate">{visit.phone}</span>
            </>
          )}
        </div>

        {/* Binary Status Badge & Photos */}
        <div className="flex items-center gap-2 pt-1">
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold border ${
              isSigned
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                isSigned ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            {isSigned ? "Signed" : "Not Signed"}
          </span>

          {visit.photo_count > 1 && (
            <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 bg-slate-100 rounded-md px-1.5 py-0.5">
              <Camera className="h-2.5 w-2.5" />
              {visit.photo_count} photos
            </span>
          )}
        </div>

        {/* Remark Note */}
        {visit.remark && (
          <p className="mt-1.5 text-xs text-slate-600 line-clamp-2 leading-relaxed italic">
            "{visit.remark}"
          </p>
        )}
      </div>
    </div>
  );
};

const VisitCard = React.memo(VisitCardBase);

// ============================================================================
// TELEGRAM-STYLE CALENDAR SEARCH POPUP MODAL
// ============================================================================
const TelegramCalendarModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onSelectDate: (dateSlug: string) => void;
  activeDateSlugs: Set<string>;
}> = ({ isOpen, onClose, onSelectDate, activeDateSlugs }) => {
  // Fixed operational view month (September/October 2026)
  const [viewYear, setViewYear] = useState<number>(2026);
  const [viewMonth, setViewMonth] = useState<number>(9); // 0-indexed: 9 = October

  if (!isOpen) return null;

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  // Days in month
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  // First day offset (0 = Sunday, 1 = Monday ...)
  const firstDayOfWeek = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7; // Monday-first

  const handlePrevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="w-full max-w-xs rounded-2xl bg-white p-5 shadow-2xl border border-slate-100 animate-in zoom-in-95 duration-150 select-none">
        {/* Calendar Header with Month Navigation */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <button
            onClick={handlePrevMonth}
            className="p-1 rounded-full text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-extrabold text-slate-900">
            {monthNames[viewMonth]} {viewYear}
          </span>
          <button
            onClick={handleNextMonth}
            className="p-1 rounded-full text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* Days of Week Header */}
        <div className="grid grid-cols-7 pt-3 text-center text-[10px] font-bold uppercase text-slate-400">
          <span>Mo</span>
          <span>Tu</span>
          <span>We</span>
          <span>Th</span>
          <span>Fr</span>
          <span>Sa</span>
          <span>Su</span>
        </div>

        {/* Days Grid */}
        <div className="grid grid-cols-7 gap-1 pt-2">
          {Array.from({ length: firstDayOfWeek }).map((_, i) => (
            <div key={`empty-${i}`} className="h-8 w-8" />
          ))}

          {Array.from({ length: daysInMonth }).map((_, i) => {
            const dayNum = i + 1;
            const mm = String(viewMonth + 1).padStart(2, "0");
            const dd = String(dayNum).padStart(2, "0");
            const slug = `${viewYear}-${mm}-${dd}`;
            const hasVisits = activeDateSlugs.has(slug);

            return (
              <button
                key={`day-${dayNum}`}
                onClick={() => {
                  onSelectDate(slug);
                  onClose();
                }}
                className={`relative flex h-8 w-8 flex-col items-center justify-center rounded-xl text-xs font-bold transition-all ${
                  hasVisits
                    ? "text-slate-900 hover:bg-cmcb-50 hover:text-cmcb-800 cursor-pointer"
                    : "text-slate-400 hover:bg-slate-50 cursor-pointer"
                }`}
              >
                <span>{dayNum}</span>
                {hasVisits && (
                  <span className="absolute bottom-1 h-1 w-1 rounded-full bg-cmcb-700" />
                )}
              </button>
            );
          })}
        </div>

        {/* Calendar Footer */}
        <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="h-2 w-2 rounded-full bg-cmcb-700" />
            Field visit logged
          </span>
          <button
            onClick={onClose}
            className="font-bold text-slate-700 hover:text-slate-900 px-2 py-1 rounded"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export const YourVisitsView: React.FC = () => {
  const {
    visitSections,
    visitsTotal,
    visitsHasMore,
    isVisitsLoading,
    isVisitsLoadingMore,
    loadMoreVisits,
    visitsSearch,
    setVisitsSearch,
    visitDates,
    jumpToVisitDate,
    openMerchantDetail,
  } = useSales();

  const [isCalendarOpen, setIsCalendarOpen] = useState(false);
  const [highlightedDateSlug, setHighlightedDateSlug] = useState<string | null>(null);
  const { isVisible: isHeaderVisible, handleScroll } = useHeadroom();
  const sentinelRef = useInfiniteScroll({
    onLoadMore: loadMoreVisits,
    hasMore: visitsHasMore,
    isLoading: isVisitsLoadingMore || isVisitsLoading,
  });

  const loadedCount = visitSections.reduce((sum, s) => sum + s.visits.length, 0);
  const showInitialLoader = isVisitsLoading && visitSections.length === 0;

  // Set of all active dates across the rep's entire history (from SQLite index)
  const activeDateSlugs = useMemo(() => {
    const set = new Set<string>(visitDates);
    visitSections.forEach((section) => {
      const slug = section.date_slug || section.visits[0]?.date;
      if (slug) set.add(slug);
    });
    return set;
  }, [visitDates, visitSections]);

  // Telegram-style Date Jump with Smooth Scroll & Pulse Highlight
  const handleJumpToDate = async (targetSlug: string) => {
    setHighlightedDateSlug(targetSlug);

    const tryFindAndScroll = () => {
      const el = document.getElementById(`visit-section-${targetSlug}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        return true;
      }
      return false;
    };

    // 1. If section is already loaded in DOM, scroll immediately
    if (tryFindAndScroll()) {
      setTimeout(() => setHighlightedDateSlug(null), 2500);
      return;
    }

    // 2. Instant server keyset jump: fetch starting from this exact date
    const jumped = await jumpToVisitDate(targetSlug);
    if (jumped) {
      await delay(80);
      tryFindAndScroll();
      setTimeout(() => setHighlightedDateSlug(null), 2500);
    }
  };

  return (
    <div
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto bg-slate-50/60 px-4 pb-4 lg:px-8 lg:pb-8 pt-0 space-y-4 max-w-4xl mx-auto w-full select-none"
    >
      {/* Sticky Top Controls: Search Input + Calendar Button + Counter */}
      <div
        className={`sticky top-0 z-20 bg-slate-50 pt-3 pb-2 space-y-2 transition-all duration-300 ease-in-out ${
          isHeaderVisible
            ? "translate-y-0 opacity-100 pointer-events-auto"
            : "-translate-y-full opacity-0 pointer-events-none"
        }`}
      >
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3.5 py-2 shadow-sm focus-within:border-cmcb-600 focus-within:ring-1 focus-within:ring-cmcb-600">
        <Search className="h-4 w-4 text-slate-400 shrink-0" />
        <input
          type="text"
          value={visitsSearch}
          onChange={(e) => setVisitsSearch(e.target.value)}
          placeholder="Search visits by store, remark notes, district..."
          className="flex-1 bg-transparent text-xs lg:text-sm font-semibold text-slate-800 placeholder-slate-400 focus:outline-none"
        />

        {visitsSearch && (
          <button
            onClick={() => setVisitsSearch("")}
            className="p-1 rounded-full text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}

        <div className="h-5 w-px bg-slate-200 shrink-0" />

        {/* Telegram Calendar Search Button */}
        <button
          onClick={() => setIsCalendarOpen(true)}
          title="Jump to date via calendar"
          className="flex items-center gap-1.5 rounded-xl bg-slate-50 hover:bg-cmcb-50 p-1.5 px-2 text-xs font-bold text-cmcb-700 transition-colors shrink-0"
        >
          <CalendarIcon className="h-4 w-4" />
          <span className="hidden sm:inline">Calendar</span>
        </button>
      </div>

      {/* Counter bar */}
      <div className="flex items-center justify-between text-xs font-semibold text-slate-500 px-1">
        <span>
          {loadedCount} of {visitsTotal} visits
        </span>
      </div>
      </div>

      {/* Sections List */}
      <div className="space-y-6">
        {showInitialLoader ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin text-cmcb-700" />
            <p className="mt-2 text-xs font-semibold">Loading your visit history...</p>
          </div>
        ) : visitSections.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400 bg-white rounded-2xl border border-slate-200">
            No visits logged for this search query.
          </div>
        ) : (
          <>
            {visitSections.map((section) => {
              const slug = section.date_slug || section.visits[0]?.date || "";
              const isTargeted = highlightedDateSlug === slug;

              return (
                <div
                  key={section.date_heading}
                  id={slug ? `visit-section-${slug}` : undefined}
                  className={`space-y-3 rounded-2xl transition-all duration-300 ${
                    isTargeted ? "ring-2 ring-cmcb-600 p-2 bg-cmcb-50/30 shadow-md" : ""
                  }`}
                >
                  <div className="flex items-center justify-between px-1">
                    <h2 className="text-sm font-extrabold text-slate-900">
                      {section.date_heading}
                    </h2>
                    <span className="text-xs font-bold text-slate-500">
                      {section.visits.length} {section.visits.length === 1 ? "visit" : "visits"}
                    </span>
                  </div>

                  <div className="space-y-3">
                    {section.visits.map((visit) => (
                      <VisitCard key={visit.id} visit={visit} onOpen={openMerchantDetail} />
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Infinite-scroll sentinel + explicit fallback */}
            <div ref={sentinelRef} className="pt-2 flex flex-col items-center gap-2">
              {isVisitsLoadingMore && (
                <span className="flex items-center gap-2 text-xs font-semibold text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin text-cmcb-700" />
                  Loading more visits...
                </span>
              )}
              {visitsHasMore && !isVisitsLoadingMore && (
                <button
                  onClick={() => loadMoreVisits()}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-cmcb-700 shadow-sm hover:bg-slate-50 transition-colors"
                >
                  Load more
                </button>
              )}
              {!visitsHasMore && (
                <span className="text-[11px] font-medium text-slate-400">
                  All {loadedCount} visits loaded
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {/* Telegram-style Calendar Popup Modal */}
      <TelegramCalendarModal
        isOpen={isCalendarOpen}
        onClose={() => setIsCalendarOpen(false)}
        onSelectDate={handleJumpToDate}
        activeDateSlugs={activeDateSlugs}
      />
    </div>
  );
};
