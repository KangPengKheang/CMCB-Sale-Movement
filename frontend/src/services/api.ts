import type {
  DeadLetterItem,
  KhanStat,
  Merchant,
  RM,
  RMVisit,
  RawVisitReport,
  StatsSummary,
  TransactionMerchant,
  TransactionWeek,
  ClusterZoneItem,
  UploadResult,
  SalesRMProfile,
  AvailableRM,
  TodayDashboardData,
  SalesStoreMapData,
  SalesCustomersData,
  SalesVisitsData,
  SalesMerchantDetail,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").trim().replace(/\/+$/, "") || "/api";
const ADMIN_TOKEN_KEY = "cmcb_admin_token";

export interface SessionUser {
  username: string;
  role: "admin" | "sro" | "rm";
  allowed_sources: string[] | null;
  all_sources: boolean;
  branch: string;
  tele_id: string;
}

async function sessionFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await window.fetch(input, { cache: "no-store", ...init });
  const url = input instanceof Request ? input.url : String(input);
  if (response.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/logout")) {
    clearAdminToken();
    window.dispatchEvent(new Event("cmcb-session-expired"));
  }
  return response;
}

export async function getCurrentSession(): Promise<SessionUser | null> {
  if (!getAdminToken()) return null;
  try {
    const response = await sessionFetch(`${API_BASE}/auth/me`, { headers: authHeaders(), signal: AbortSignal.timeout(20000) });
    if (!response.ok) return null;
    return await response.json();
  } catch { return null; }
}

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function loginAdmin(
  password: string
): Promise<{ success: boolean; error?: string; user?: SessionUser }> {
  try {
    const res = await sessionFetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
      signal: AbortSignal.timeout(20000),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { success: false, error: data.detail || "Password not accepted." };
    }
    if (data.token) {
      setAdminToken(data.token);
      return { success: true, user: { username: data.username, role: data.role, allowed_sources: data.allowed_sources, all_sources: data.all_sources, branch: data.branch || "", tele_id: data.tele_id || "" } };
    }
  } catch (err: any) {
    return { success: false, error: err.message || "Network error. Please try again." };
  }
  return { success: false, error: "Authentication failed" };
}

export async function logoutAdmin(): Promise<void> {
  try {
    await sessionFetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(5000),
    });
  } catch {}
  clearAdminToken();
}

export async function checkAdminAuth(): Promise<boolean> {
  const token = getAdminToken();
  if (!token) return false;
  try {
    const res = await sessionFetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(6000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Robust API Client with generous timeouts (10-12s).
 */

export async function fetchMerchants(): Promise<Merchant[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/merchants?limit=3000`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchMerchants error:", err);
  }
  return null;
}

export async function fetchMerchantDetail(merchantId: number): Promise<Merchant | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/merchants/${merchantId}`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchMerchantDetail error:", err);
    return null;
  }
}

export async function fetchRMs(): Promise<RM[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/rms?limit=100`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchRMs error:", err);
  }
  return null;
}

/** Chronological visit feed for one RM, used to draw the route trail. */
export async function fetchRMVisits(rmId: number, limit = 300): Promise<RMVisit[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/rms/${rmId}/visits?limit=${limit}`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchRMVisits error:", err);
  }
  return null;
}

export async function fetchReports(): Promise<RawVisitReport[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/reports?limit=2000`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchReports error:", err);
  }
  return null;
}

export async function fetchStatsSummary(): Promise<StatsSummary | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/reports/stats`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchStatsSummary error:", err);
  }
  return null;
}

export async function fetchKhanStats(): Promise<KhanStat[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/map/khan-stats`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchKhanStats error:", err);
  }
  return null;
}

export async function fetchDlqItems(): Promise<DeadLetterItem[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/reports/dlq?limit=200`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchDlqItems error:", err);
  }
  return null;
}


// ============================================================================
// Target Acquisition & Transaction Pipeline Endpoints (/api/transactions)
// ============================================================================

export async function fetchTransactionWeeks(): Promise<TransactionWeek[] | null> {
  try {
    const res = await sessionFetch(`${API_BASE}/transactions/weeks`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchTransactionWeeks error:", err);
  }
  return null;
}

export async function fetchTransactionMerchants(params: {
  week?: string;
  min_txns?: number;
  is_in_pp?: boolean;
  change_status?: string;
  bank_code?: string;
  search?: string;
} = {}): Promise<TransactionMerchant[] | null> {
  try {
    const query = new URLSearchParams();
    if (params.week) query.append("week", params.week);
    if (params.min_txns !== undefined) query.append("min_txns", String(params.min_txns));
    if (params.is_in_pp !== undefined) query.append("is_in_pp", String(params.is_in_pp));
    if (params.change_status) query.append("change_status", params.change_status);
    if (params.bank_code) query.append("bank_code", params.bank_code);
    if (params.search) query.append("search", params.search);

    const res = await sessionFetch(`${API_BASE}/transactions/merchants?${query.toString()}`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(12000),
    });
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchTransactionMerchants error:", err);
  }
  return null;
}

export async function fetchTransactionClusters(params: {
  week?: string;
  min_txns?: number;
  cluster_distance_meters?: number;
  min_cluster_stores?: number;
} = {}): Promise<ClusterZoneItem[] | null> {
  try {
    const query = new URLSearchParams();
    if (params.week) query.append("week", params.week);
    if (params.min_txns !== undefined) query.append("min_txns", String(params.min_txns));
    if (params.cluster_distance_meters !== undefined) {
      query.append("cluster_distance_meters", String(params.cluster_distance_meters));
    }
    if (params.min_cluster_stores !== undefined) {
      query.append("min_cluster_stores", String(params.min_cluster_stores));
    }

    const res = await sessionFetch(`${API_BASE}/transactions/clusters?${query.toString()}`, {
      headers: { ...authHeaders() },
      signal: AbortSignal.timeout(12000),
    });
    const data = await res.json();
    if (Array.isArray(data)) return data;
  } catch (err) {
    console.debug("[API] fetchTransactionClusters error:", err);
  }
  return null;
}

export async function uploadTransactionFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await sessionFetch(`${API_BASE}/transactions/upload`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = "Upload failed.";
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // Non-JSON response body
    }
    throw new Error(errorDetail);
  }

  return await res.json();
}

export function getMissionsExportUrl(week: string = "latest", minTxns: number = 11): string {
  const query = new URLSearchParams();
  if (week) query.append("week", week);
  if (minTxns !== undefined) query.append("min_txns", String(minTxns));
  return `${API_BASE}/transactions/export-missions?${query.toString()}`;
}

// ============================================================================
// SALES PORTAL (FIELDWORK TMA) CLIENT METHODS
// ============================================================================

export function getTelegramInitData(): string {
  if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.initData) {
    return (window as any).Telegram.WebApp.initData;
  }
  return "";
}

export function telegramHeaders(): Record<string, string> {
  const initData = getTelegramInitData();
  return { ...authHeaders(), ...(initData ? { "X-Telegram-Init-Data": initData } : {}) };
}
export async function fetchSalesProfile(telegramId?: number): Promise<{ current_rm: SalesRMProfile; available_rms: AvailableRM[] } | null> {
  try {
    const query = new URLSearchParams();
    if (telegramId) query.append("telegram_id", String(telegramId));
    const res = await sessionFetch(`${API_BASE}/sales/profile?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesProfile error:", err);
    return null;
  }
}

export async function fetchSalesToday(telegramId?: number, refDate?: string): Promise<TodayDashboardData | null> {
  try {
    const query = new URLSearchParams();
    if (telegramId) query.append("telegram_id", String(telegramId));
    if (refDate && refDate.trim()) query.append("ref_date", refDate.trim());
    const res = await sessionFetch(`${API_BASE}/sales/today?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesToday error:", err);
    return null;
  }
}

export async function fetchSalesStoreMap(params: {
  telegramId?: number;
  search?: string;
  khan?: string;
  stage?: string;
  owner?: string;
  limit?: number;
} = {}): Promise<SalesStoreMapData | null> {
  try {
    const query = new URLSearchParams();
    if (params.telegramId) query.append("telegram_id", String(params.telegramId));
    if (params.search) query.append("search", params.search);
    if (params.khan) query.append("khan", params.khan);
    if (params.stage) query.append("stage", params.stage);
    if (params.owner) query.append("owner", params.owner);
    if (params.limit !== undefined) query.append("limit", String(params.limit));
    const res = await sessionFetch(`${API_BASE}/sales/store-map?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(12000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesStoreMap error:", err);
    return null;
  }
}

export async function fetchSalesCustomers(params: {
  telegramId?: number;
  status?: string;
  search?: string;
  sortBy?: string;
  cursor?: string | null;
  limit?: number;
} = {}): Promise<SalesCustomersData | null> {
  try {
    const query = new URLSearchParams();
    if (params.telegramId) query.append("telegram_id", String(params.telegramId));
    if (params.status) query.append("status", params.status);
    if (params.search) query.append("search", params.search);
    if (params.sortBy) query.append("sort_by", params.sortBy);
    if (params.cursor) query.append("cursor", params.cursor);
    if (params.limit) query.append("limit", String(params.limit));
    const res = await sessionFetch(`${API_BASE}/sales/customers?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesCustomers error:", err);
    return null;
  }
}

export async function fetchSalesVisitDates(telegramId?: number): Promise<string[] | null> {
  try {
    const query = new URLSearchParams();
    if (telegramId) query.append("telegram_id", String(telegramId));
    const res = await sessionFetch(`${API_BASE}/sales/visits/dates?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    if (data && Array.isArray(data.dates)) return data.dates;
  } catch (err) {
    console.debug("[API] fetchSalesVisitDates error:", err);
  }
  return null;
}

export async function fetchSalesVisits(params: {
  telegramId?: number;
  timeRange?: string;
  outcome?: string;
  search?: string;
  jumpDate?: string;
  cursor?: string | null;
  limit?: number;
} = {}): Promise<SalesVisitsData | null> {
  try {
    const query = new URLSearchParams();
    if (params.telegramId) query.append("telegram_id", String(params.telegramId));
    if (params.timeRange) query.append("time_range", params.timeRange);
    if (params.outcome) query.append("outcome", params.outcome);
    if (params.search) query.append("search", params.search);
    if (params.jumpDate) query.append("jump_date", params.jumpDate);
    if (params.cursor) query.append("cursor", params.cursor);
    if (params.limit) query.append("limit", String(params.limit));
    const res = await sessionFetch(`${API_BASE}/sales/visits?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesVisits error:", err);
    return null;
  }
}

export async function fetchSalesMerchantDetail(merchantId: number, telegramId?: number): Promise<SalesMerchantDetail | null> {
  try {
    const query = new URLSearchParams();
    if (telegramId) query.append("telegram_id", String(telegramId));
    const res = await sessionFetch(`${API_BASE}/sales/merchants/${merchantId}?${query.toString()}`, {
      headers: { ...telegramHeaders() },
      signal: AbortSignal.timeout(10000),
    });
    return await res.json();
  } catch (err) {
    console.debug("[API] fetchSalesMerchantDetail error:", err);
    return null;
  }
}

export async function fetchActivityOverview(
  date?: string, thresholdMinutes?: number
): Promise<import("../types").SalesActivityOverview | null> {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (thresholdMinutes) params.set("threshold_minutes", String(thresholdMinutes));
  try {
    const response = await sessionFetch(`${API_BASE}/activity?${params}`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Sales activity unavailable:", error);
    return null;
  }
}

export async function fetchSenderActivity(
  senderId: number, date: string, thresholdMinutes?: number, offset = 0
): Promise<import("../types").SenderActivity | null> {
  const params = new URLSearchParams({ date, limit: "100", offset: String(offset) });
  if (thresholdMinutes) params.set("threshold_minutes", String(thresholdMinutes));
  try {
    const response = await sessionFetch(`${API_BASE}/activity/${senderId}/drops?${params}`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Sender activity unavailable:", error);
    return null;
  }
}

export async function fetchMovementRoutes(
  date: string
): Promise<import("../types").SalesMovementRoutes | null> {
  try {
    const params = new URLSearchParams({ date });
    const response = await sessionFetch(`${API_BASE}/activity/routes?${params}`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Movement routes unavailable:", error);
    return null;
  }
}

export async function fetchActivityFeed(
  date: string, thresholdMinutes?: number, senderId?: number, lateOnly = false
): Promise<import("../types").ActivityFeed | null> {
  const params = new URLSearchParams({ date, limit: "50" });
  if (thresholdMinutes) params.set("threshold_minutes", String(thresholdMinutes));
  if (senderId !== undefined) params.set("sender_id", String(senderId));
  if (lateOnly) params.set("late_only", "true");
  try {
    const response = await sessionFetch(`${API_BASE}/activity/feed?${params}`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Activity feed unavailable:", error);
    return null;
  }
}

export async function fetchDropDetail(dropId: number): Promise<import("../types").DropDetail | null> {
  try {
    const response = await sessionFetch(`${API_BASE}/activity/drops/${dropId}`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Drop details unavailable:", error);
    return null;
  }
}

export async function fetchActivityCalendar(): Promise<import("../types").ActivityCalendar | null> {
  try {
    const response = await sessionFetch(`${API_BASE}/activity/calendar`, {
      headers: authHeaders(), signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.debug("[API] Case drop calendar unavailable:", error);
    return null;
  }
}
