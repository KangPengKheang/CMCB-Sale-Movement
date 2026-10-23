import { startAutoRefresh } from "../services/autoRefresh";
import React, { createContext, useContext, useEffect, useState, useMemo, useCallback, useRef } from "react";
import type { ActiveTab, DeadLetterItem, Merchant, RM, RawVisitReport, StatsSummary } from "../types";
import { fetchDlqItems, fetchMerchants, fetchRMs, fetchReports, fetchStatsSummary } from "../services/api";

interface DataContextType {
  merchants: Merchant[];
  rms: RM[];
  reports: RawVisitReport[];
  statsSummary: StatsSummary | null;
  dlqItems: DeadLetterItem[];
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  uniqueKhans: string[];
  isSyncing: boolean;
  isLiveConnected: boolean;
  lastSyncTime: Date | null;
  refreshData: () => Promise<void>;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export const DataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [rms, setRms] = useState<RM[]>([]);
  const [reports, setReports] = useState<RawVisitReport[]>([]);
  const [statsSummary, setStatsSummary] = useState<StatsSummary | null>(null);
  const [dlqItems, setDlqItems] = useState<DeadLetterItem[]>([]);
  const [activeTab, setActiveTab] = useState<ActiveTab>("performance");
  const [isSyncing, setIsSyncing] = useState(false);
  const [isLiveConnected, setIsLiveConnected] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);
  const failures = useRef(0);

  const loadData = useCallback(async () => {
    setIsSyncing(true);
    try {
      const [merchantsRes, rmsRes, statsRes, reportsRes, dlqRes] = await Promise.all([
        (activeTab === "performance" || activeTab === "drop-calendar") ? Promise.resolve(null) : fetchMerchants(),
        (activeTab === "performance" || activeTab === "drop-calendar") ? Promise.resolve(null) : fetchRMs(),
        fetchStatsSummary(),
        (activeTab === "performance" || activeTab === "drop-calendar") ? Promise.resolve(null) : fetchReports(),
        activeTab === "data-explorer" ? fetchDlqItems() : Promise.resolve(null),
      ]);
      if (merchantsRes !== null) setMerchants(merchantsRes);
      if (rmsRes !== null) setRms(rmsRes);
      if (statsRes !== null) setStatsSummary(statsRes);
      if (reportsRes !== null) setReports(reportsRes);
      if (dlqRes !== null) setDlqItems(dlqRes);
      if (statsRes !== null || merchantsRes !== null || reportsRes !== null) {
        failures.current = 0;
        setIsLiveConnected(true);
        setLastSyncTime(new Date());
      } else if (++failures.current >= 3) setIsLiveConnected(false);
    } catch (error) {
      console.error("[DataContext] Error loading data:", error);
      if (++failures.current >= 3) setIsLiveConnected(false);
    } finally {
      setIsSyncing(false);
    }
  }, [activeTab]);

  useEffect(() => {
    return startAutoRefresh(loadData);
  }, [loadData]);

  const uniqueKhans = useMemo(() => Array.from(new Set(merchants
    .map((merchant) => merchant.district_khan || merchant.khan_name).filter((name): name is string => !!name))).sort(), [merchants]);

  return <DataContext.Provider value={{
    merchants, rms, reports, statsSummary, dlqItems, activeTab, setActiveTab,
    uniqueKhans, isSyncing, isLiveConnected, lastSyncTime, refreshData: loadData,
  }}>{children}</DataContext.Provider>;
};

export const useData = () => {
  const context = useContext(DataContext);
  if (!context) throw new Error("useData must be used within a DataProvider");
  return context;
};
