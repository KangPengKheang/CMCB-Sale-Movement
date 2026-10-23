import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useTransition } from "react";
import type {
  SalesTab,
  SalesRMProfile,
  AvailableRM,
  TodayDashboardData,
  SalesStoreMapData,
  SalesCustomersData,
  SalesCustomerItem,
  SalesVisitsData,
  SalesMerchantDetail,
  SalesStoreItem,
} from "../types";
import {
  fetchSalesProfile,
  fetchSalesToday,
  fetchSalesStoreMap,
  fetchSalesCustomers,
  fetchSalesVisits,
  fetchSalesVisitDates,
  fetchSalesMerchantDetail,
} from "../services/api";

const STORAGE_KEY_TG_ID = "cmcb_sales_telegram_id";
const DEFAULT_TG_ID = 8859478803; // Liza Soy (active RM in database)

interface SalesContextType {
  // Session / RM Identity
  telegramId: number;
  setTelegramId: (id: number) => void;
  currentRM: SalesRMProfile | null;
  availableRMs: AvailableRM[];
  isRMModalOpen: boolean;
  setIsRMModalOpen: (open: boolean) => void;

  // Active Navigation Tab
  activeSalesTab: SalesTab;
  setActiveSalesTab: (tab: SalesTab) => void;

  // Main Data Views
  todayData: TodayDashboardData | null;
  dateOffset: number;
  setDateOffset: React.Dispatch<React.SetStateAction<number>>;
  storeMapData: SalesStoreMapData | null;
  // Customers list (keyset-paginated, pages accumulate)
  customerItems: SalesCustomerItem[];
  customerSummary: SalesCustomersData["summary"] | null;
  customerTotal: number;
  customerHasMore: boolean;
  isCustomersLoading: boolean;
  isCustomersLoadingMore: boolean;
  loadMoreCustomers: () => Promise<void>;

  // Visits list (keyset-paginated, date sections merge across pages)
  visitSections: SalesVisitsData["grouped_sections"];
  visitsTotal: number;
  visitsBanner: string;
  visitsHasMore: boolean;
  isVisitsLoading: boolean;
  isVisitsLoadingMore: boolean;
  loadMoreVisits: () => Promise<void>;
  visitDates: string[];
  jumpToVisitDate: (dateSlug: string) => Promise<boolean>;

  // Store Map Specific State & Filters
  mapSearch: string;
  setMapSearch: (s: string) => void;
  mapKhan: string;
  setMapKhan: (k: string) => void;
  mapStage: string;
  setMapStage: (s: string) => void;
  mapOwner: string;
  setMapOwner: (o: string) => void;
  selectedStore: SalesStoreItem | null;
  setSelectedStore: (s: SalesStoreItem | null) => void;

  // Customers Filters
  customerStatus: "ALL" | "SIGNED" | "NOT_SIGNED";
  setCustomerStatus: (s: "ALL" | "SIGNED" | "NOT_SIGNED") => void;
  customerSort: "recent" | "longest_unvisited" | "name";
  setCustomerSort: (s: "recent" | "longest_unvisited" | "name") => void;
  customerSearch: string;
  setCustomerSearch: (s: string) => void;

  // Visits Filters
  visitsTimeRange: "today" | "7d" | "30d" | "all";
  setVisitsTimeRange: (r: "today" | "7d" | "30d" | "all") => void;
  visitsOutcome: string;
  setVisitsOutcome: (o: string) => void;
  visitsSearch: string;
  setVisitsSearch: (s: string) => void;

  // Merchant Detail Modal / Drawer
  selectedMerchantId: number | null;
  selectedMerchantDetail: SalesMerchantDetail | null;
  openMerchantDetail: (id: number) => void;
  closeMerchantDetail: () => void;

  // Global Loading & Refresh
  isLoading: boolean;
  refreshAll: () => Promise<void>;
}

const SalesContext = createContext<SalesContextType | undefined>(undefined);

export const SalesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [telegramId, setTelegramIdState] = useState<number>(() => {
    const tgWin = window as unknown as {
      Telegram?: { WebApp?: { initDataUnsafe?: { user?: { id?: number } } } };
    };
    const tgWebAppData = tgWin.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (typeof tgWebAppData === "number") {
      return tgWebAppData;
    }
    const saved = localStorage.getItem(STORAGE_KEY_TG_ID);
    return saved ? parseInt(saved, 10) : DEFAULT_TG_ID;
  });

  const [activeSalesTab, setActiveSalesTab] = useState<SalesTab>("today");
  const [isRMModalOpen, setIsRMModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Identity
  const [currentRM, setCurrentRM] = useState<SalesRMProfile | null>(null);
  const [availableRMs, setAvailableRMs] = useState<AvailableRM[]>([]);

  // Views Data
  const [todayData, setTodayData] = useState<TodayDashboardData | null>(null);
  const [dateOffset, setDateOffset] = useState<number>(0);

  // Compute selected date string YYYY-MM-DD from live device clock (matching LivePulseView)
  const selectedDateStr = useMemo(() => {
    const targetTime = Date.now() - (dateOffset * 86400000);
    const d = new Date(targetTime);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, [dateOffset]);

  const [storeMapData, setStoreMapData] = useState<SalesStoreMapData | null>(null);
  // Store Map Filters
  const [mapSearch, setMapSearch] = useState("");
  const [mapKhan, setMapKhan] = useState("all");
  const [mapStage, setMapStage] = useState("ALL");
  const [mapOwner, setMapOwner] = useState("all");
  const [selectedStore, setSelectedStore] = useState<SalesStoreItem | null>(null);

  // Customers list (keyset-paginated; pages accumulate here so going back
  // to the tab keeps everything already loaded)
  const [customerStatus, setCustomerStatus] = useState<"ALL" | "SIGNED" | "NOT_SIGNED">("ALL");
  const [customerSort, setCustomerSort] = useState<"recent" | "longest_unvisited" | "name">("recent");
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerItems, setCustomerItems] = useState<SalesCustomerItem[]>([]);
  const [customerSummary, setCustomerSummary] = useState<SalesCustomersData["summary"] | null>(null);
  const [customerTotal, setCustomerTotal] = useState(0);
  const [customerCursor, setCustomerCursor] = useState<string | null>(null);
  const [customerHasMore, setCustomerHasMore] = useState(false);
  const [isCustomersLoading, setIsCustomersLoading] = useState(false);
  const [isCustomersLoadingMore, setIsCustomersLoadingMore] = useState(false);

  // Visits list (same keyset pattern, grouped into date sections)
  const [visitsTimeRange, setVisitsTimeRange] = useState<"today" | "7d" | "30d" | "all">("all");
  const [visitsOutcome, setVisitsOutcome] = useState("all");
  const [visitsSearch, setVisitsSearch] = useState("");
  const [visitSections, setVisitSections] = useState<SalesVisitsData["grouped_sections"]>([]);
  const [visitsTotal, setVisitsTotal] = useState(0);
  const [visitsBanner, setVisitsBanner] = useState("");
  const [visitsCursor, setVisitsCursor] = useState<string | null>(null);
  const [visitsHasMore, setVisitsHasMore] = useState(false);
  const [isVisitsLoading, setIsVisitsLoading] = useState(false);
  const [isVisitsLoadingMore, setIsVisitsLoadingMore] = useState(false);
  const [visitDates, setVisitDates] = useState<string[]>([]);

  // Initialize Native Telegram Mini App SDK (Expand full screen & set brand colors)
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      try {
        tg.ready?.();
        tg.expand?.();
        tg.setHeaderColor?.("#006B3F");
        tg.setBackgroundColor?.("#f8fafc");
      } catch (err) {
        console.debug("[TMA] WebApp init error:", err);
      }
    }
  }, []);

  // Merchant Detail Drawer
  const [selectedMerchantId, setSelectedMerchantId] = useState<number | null>(null);
  const [selectedMerchantDetail, setSelectedMerchantDetail] = useState<SalesMerchantDetail | null>(null);

  const setTelegramId = useCallback((id: number) => {
    setTelegramIdState(id);
    localStorage.setItem(STORAGE_KEY_TG_ID, String(id));
  }, []);

  const openMerchantDetail = useCallback(async (id: number) => {
    setSelectedMerchantId(id);
    const detail = await fetchSalesMerchantDetail(id, telegramId);
    if (detail) {
      setSelectedMerchantDetail(detail);
    }
  }, [telegramId]);

  const closeMerchantDetail = useCallback(() => {
    setSelectedMerchantId(null);
    setSelectedMerchantDetail(null);
  }, []);

  // Fetch Profile & available RMs
  const loadProfile = useCallback(async () => {
    const profRes = await fetchSalesProfile(telegramId);
    if (profRes) {
      setCurrentRM(profRes.current_rm);
      setAvailableRMs(profRes.available_rms);
    }
  }, [telegramId]);

  // Fetch Today Dashboard Data
  const loadToday = useCallback(async () => {
    const data = await fetchSalesToday(telegramId, selectedDateStr);
    if (data) setTodayData(data);
  }, [telegramId, selectedDateStr]);

  // Fetch Store Map Data
  const loadStoreMap = useCallback(async () => {
    const data = await fetchSalesStoreMap({
      telegramId,
      search: mapSearch || undefined,
      khan: mapKhan !== "all" ? mapKhan : undefined,
      stage: mapStage !== "ALL" ? mapStage : undefined,
      owner: mapOwner,
    });
    if (data) setStoreMapData(data);
  }, [telegramId, mapSearch, mapKhan, mapStage, mapOwner]);

  // ---------------------------------------------------------------------------
  // CUSTOMERS — first page + append
  // ---------------------------------------------------------------------------
  const loadCustomers = useCallback(async () => {
    setIsCustomersLoading(true);
    try {
      const data = await fetchSalesCustomers({
        telegramId,
        status: customerStatus,
        search: customerSearch || undefined,
        sortBy: customerSort,
      });
      if (data) {
        setCustomerItems(data.all_customers || []);
        setCustomerSummary(data.summary || null);
        setCustomerTotal(data.total ?? (data.all_customers || []).length);
        setCustomerCursor(data.next_cursor ?? null);
        setCustomerHasMore(Boolean(data.has_more));
      }
    } finally {
      setIsCustomersLoading(false);
    }
  }, [telegramId, customerStatus, customerSearch, customerSort]);

  const loadMoreCustomers = useCallback(async () => {
    if (isCustomersLoadingMore || isCustomersLoading || !customerHasMore) return;
    setIsCustomersLoadingMore(true);
    try {
      const data = await fetchSalesCustomers({
        telegramId,
        status: customerStatus,
        search: customerSearch || undefined,
        sortBy: customerSort,
        cursor: customerCursor,
      });
      if (data) {
        setCustomerItems((prev) => [...prev, ...(data.all_customers || [])]);
        setCustomerCursor(data.next_cursor ?? null);
        setCustomerHasMore(Boolean(data.has_more));
      }
    } finally {
      setIsCustomersLoadingMore(false);
    }
  }, [
    telegramId, customerStatus, customerSearch, customerSort,
    customerCursor, customerHasMore, isCustomersLoading, isCustomersLoadingMore,
  ]);

  // ---------------------------------------------------------------------------
  // VISITS — first page + append, merging date sections across page boundaries
  // ---------------------------------------------------------------------------
  const mergeVisitSections = (
    prev: SalesVisitsData["grouped_sections"],
    incoming: SalesVisitsData["grouped_sections"]
  ) => {
    const merged = prev.map((s) => ({ ...s, visits: [...s.visits] }));
    const indexByHeading = new Map(merged.map((s, i) => [s.date_heading, i]));

    incoming.forEach((section) => {
      const at = indexByHeading.get(section.date_heading);
      if (at === undefined) {
        merged.push({ ...section, visits: [...section.visits] });
        indexByHeading.set(section.date_heading, merged.length - 1);
      } else {
        // A date ran across the page boundary — extend the existing section
        merged[at].visits.push(...section.visits);
        merged[at].count = merged[at].visits.length;
        if (!merged[at].date_slug && section.date_slug) {
          merged[at].date_slug = section.date_slug;
        }
      }
    });

    return merged;
  };

  const loadVisits = useCallback(async () => {
    setIsVisitsLoading(true);
    try {
      const [data, dates] = await Promise.all([
        fetchSalesVisits({
          telegramId,
          timeRange: visitsTimeRange,
          outcome: visitsOutcome !== "all" ? visitsOutcome : undefined,
          search: visitsSearch || undefined,
        }),
        fetchSalesVisitDates(telegramId),
      ]);
      if (dates) setVisitDates(dates);
      if (data) {
        setVisitSections(data.grouped_sections || []);
        setVisitsTotal(data.total_visits ?? 0);
        setVisitsBanner(data.insight_banner || "");
        setVisitsCursor(data.next_cursor ?? null);
        setVisitsHasMore(Boolean(data.has_more));
      }
    } finally {
      setIsVisitsLoading(false);
    }
  }, [telegramId, visitsTimeRange, visitsOutcome, visitsSearch]);

  const jumpToVisitDate = useCallback(
    async (dateSlug: string): Promise<boolean> => {
      // If date section is already loaded in visitSections, return true
      const alreadyLoaded = visitSections.some(
        (s) => s.date_slug === dateSlug || s.visits.some((v) => v.date === dateSlug)
      );
      if (alreadyLoaded) return true;

      setIsVisitsLoading(true);
      try {
        const data = await fetchSalesVisits({
          telegramId,
          timeRange: "all",
          jumpDate: dateSlug,
        });
        if (data && (data.grouped_sections || []).length > 0) {
          setVisitSections((prev) => mergeVisitSections(prev, data.grouped_sections || []));
          setVisitsCursor(data.next_cursor ?? null);
          setVisitsHasMore(Boolean(data.has_more));
          return true;
        }
      } finally {
        setIsVisitsLoading(false);
      }
      return false;
    },
    [telegramId, visitSections]
  );

  const loadMoreVisits = useCallback(async () => {
    if (isVisitsLoadingMore || isVisitsLoading || !visitsHasMore) return;
    setIsVisitsLoadingMore(true);
    try {
      const data = await fetchSalesVisits({
        telegramId,
        timeRange: visitsTimeRange,
        outcome: visitsOutcome !== "all" ? visitsOutcome : undefined,
        search: visitsSearch || undefined,
        cursor: visitsCursor,
      });
      if (data) {
        setVisitSections((prev) => mergeVisitSections(prev, data.grouped_sections || []));
        setVisitsCursor(data.next_cursor ?? null);
        setVisitsHasMore(Boolean(data.has_more));
      }
    } finally {
      setIsVisitsLoadingMore(false);
    }
  }, [
    telegramId, visitsTimeRange, visitsOutcome, visitsSearch,
    visitsCursor, visitsHasMore, isVisitsLoading, isVisitsLoadingMore,
  ]);

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        loadProfile(),
        loadToday(),
        loadStoreMap(),
        loadCustomers(),
        loadVisits(),
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [loadProfile, loadToday, loadStoreMap, loadCustomers, loadVisits]);

  // Initial and Telegram ID change load
  useEffect(() => {
    refreshAll();
  }, [telegramId]);

  // Reactive sub-loads on filter changes
  useEffect(() => {
    if (activeSalesTab === "store-map") {
      loadStoreMap();
    }
  }, [mapSearch, mapKhan, mapStage, mapOwner, loadStoreMap, activeSalesTab]);

  useEffect(() => {
    if (activeSalesTab === "customers") {
      loadCustomers();
    }
  }, [customerStatus, customerSort, customerSearch, loadCustomers, activeSalesTab]);

  useEffect(() => {
    if (activeSalesTab === "visits") {
      loadVisits();
    }
  }, [visitsTimeRange, visitsOutcome, visitsSearch, loadVisits, activeSalesTab]);
  useEffect(() => {
    if (activeSalesTab === "today") {
      loadToday();
    }
  }, [dateOffset, loadToday, activeSalesTab]);

  return (
    <SalesContext.Provider
      value={{
        telegramId,
        setTelegramId,
        currentRM,
        availableRMs,
        isRMModalOpen,
        setIsRMModalOpen,
        activeSalesTab,
        setActiveSalesTab,
        todayData,
        dateOffset,
        setDateOffset,
        storeMapData,
        customerItems,
        customerSummary,
        customerTotal,
        customerHasMore,
        isCustomersLoading,
        isCustomersLoadingMore,
        loadMoreCustomers,
        visitSections,
        visitsTotal,
        visitsBanner,
        visitsHasMore,
        isVisitsLoading,
        isVisitsLoadingMore,
        loadMoreVisits,
        visitDates,
        jumpToVisitDate,
        mapSearch,
        setMapSearch,
        mapKhan,
        setMapKhan,
        mapStage,
        setMapStage,
        mapOwner,
        setMapOwner,
        selectedStore,
        setSelectedStore,
        customerStatus,
        setCustomerStatus,
        customerSort,
        setCustomerSort,
        customerSearch,
        setCustomerSearch,
        visitsTimeRange,
        setVisitsTimeRange,
        visitsOutcome,
        setVisitsOutcome,
        visitsSearch,
        setVisitsSearch,
        selectedMerchantId,
        selectedMerchantDetail,
        openMerchantDetail,
        closeMerchantDetail,
        isLoading,
        refreshAll,
      }}
    >
      {children}
    </SalesContext.Provider>
  );
};

export const useSales = () => {
  const ctx = useContext(SalesContext);
  if (!ctx) throw new Error("useSales must be used within a SalesProvider");
  return ctx;
};
