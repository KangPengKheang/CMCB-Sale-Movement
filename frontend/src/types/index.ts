export type KHQRStage = "CONVERTED" | "PIPELINE" | "TARGET" | "EXISTING";

export interface MerchantVisit {
  visit_id: number;
  report_time: string;
  sales_rep: string;
  status: string;
  khqr_stage: KHQRStage | string;
  bank?: string;
  remark?: string;
  photo_count?: number;
  latitude: number;
  longitude: number;
}

export interface Merchant {
  id: number;
  merchant_id?: number;
  canonical_name: string;
  merchant_name?: string;
  business_category: string;
  business?: string;
  tel?: string;
  district_khan: string;
  khan_name?: string;
  latitude: number;
  longitude: number;
  map_url?: string;
  total_visits: number;
  first_visit_date?: string;
  latest_visit_date: string;
  current_status: string;
  status?: string;
  current_khqr_stage: KHQRStage | string;
  khqr_stage?: KHQRStage | string;
  is_onboarded: number | boolean;
  competitor_banks?: string;
  bank?: string;
  has_aba: number;
  has_acleda: number;
  has_cmcb: number;
  has_other_bank: number;
  assigned_reps?: string;
  sender_name?: string;
  latest_remark?: string;
  remark?: string;
  visits?: MerchantVisit[];
}

export interface RMVisit {
  visit_id: number;
  merchant_id: number;
  rm_id: number;
  report_time: string;
  merchant_name?: string;
  business?: string;
  district_khan?: string;
  status: string;
  khqr_stage: KHQRStage | string;
  latitude: number;
  longitude: number;
  remark?: string;
  bank?: string;
  photo_count?: number;
}

export interface RM {
  id: number;
  rm_id?: number;
  telegram_user_id: number;
  canonical_name: string;
  name?: string;
  username?: string;
  first_active_date: string;
  latest_active_date: string;
  total_visits_logged: number;
  unique_merchants_reached: number;
  onboarded_count: number;
  pipeline_count: number;
  target_count: number;
  conversion_rate: number;
  active_working_days: number;
  daily_visit_velocity: number;
  compliance_errors?: number;
  top_districts?: Record<string, number>;
  top_categories?: Record<string, number>;
  visits?: RMVisit[];
}

export interface KhanStat {
  khan_name: string;
  khan_code?: string;
  visit_count: number;
  is_cold_zone: boolean;
  unique_merchants?: number;
  cmcb_count?: number;
  penetration_rate?: number;
}

export interface StatsSummary {
  total_merchants: number;
  total_visits: number;
  total_rms: number;
  cmcb_deployed: number;
  in_pipeline: number;
  competitor_only?: number;
  active_districts: number;
  cold_districts: number;
}

export interface RawVisitReport {
  id: number;
  merchant_id?: number;
  rm_id?: number;
  report_time: string;
  sender_id: number;
  sender_name: string;
  merchant_name: string;
  tel?: string;
  tel_clean?: string;
  business?: string;
  business_clean?: string;
  purpose?: string;
  bank?: string;
  has_aba: number;
  has_acleda: number;
  has_cmcb: number;
  has_other_bank: number;
  amount?: string;
  interest?: string;
  loan_type?: string;
  tenure?: string;
  maturity?: string;
  status?: string;
  status_clean?: string;
  khqr_stage: string;
  potential_level?: string;
  potential_product?: string;
  remark?: string;
  latitude: number;
  longitude: number;
  district_khan: string;
  map_url?: string;
  photo_count: number;
}

export interface DeadLetterItem {
  id: number;
  msg_id: number | null;
  msg_date: string;
  sender_name: string;
  sender_id?: number;
  message_type: string;
  reason: string;
  raw_content?: string;
}

export type ActiveTab = "performance" | "data-explorer" | "live-pulse" | "drop-calendar";


// --- Target Acquisition & Transaction Pipeline Types ---

export type ChangeStatus = "NEW_POPUP" | "SURGING" | "COOLING" | "STABLE" | "BASELINE";
export type MerchantTier = "CORPORATE" | "SME";

export interface TransactionMerchant {
  id: number;
  snapshot_week: string;
  week_start_date: string;
  week_end_date: string;
  week_label: string;
  merchant_id: string;
  merchant_name: string;
  bank_code: string;
  transaction_count: number;
  prev_week_txns: number;
  txn_delta: number;
  growth_pct: number;
  change_status: ChangeStatus | string;
  latitude: number | null;
  longitude: number | null;
  is_in_pp: boolean;
  tier?: MerchantTier;
  is_visited_1to1?: boolean;
  matched_visit_name?: string;
  /** Business category, populated for visit-only entries. */
  business_type?: string;
  /** True when this entry represents an RM field visit rather than a target. */
  is_visit_only?: boolean;
}

export interface TransactionWeek {
  iso_week: string;
  week_start_date: string;
  week_end_date: string;
  week_label: string;
  merchant_count: number;
  total_volume: number;
  merchants_in_pp: number;
  merchants_20plus: number;
}

export interface TargetStoreCard {
  rank: number;
  merchant_id: string;
  merchant_name: string;
  bank_code: string;
  transaction_count: number;
  latitude: number;
  longitude: number;
  tier?: MerchantTier;
  is_visited_1to1?: boolean;
}

export interface ClusterZoneItem {
  id: number;
  title: string;
  district: string;
  short_name: string;
  center_lat: number;
  center_lng: number;
  polygon: [number, number][];
  store_count: number;
  total_volume: number;
  merchants: TargetStoreCard[];
}

export interface UploadResult {
  status: string;
  message: string;
  filename: string;
  raw_rows: number;
  clean_transactions: number;
  snapshot_records: number;
  unique_merchants: number;
  weeks_processed: string[];
  target_20plus_stores: number;
  change_distribution: Record<string, number>;
}

// ============================================================================
// SALES PORTAL (FIELDWORK TMA) TYPES
// ============================================================================

export type SalesTab = "today" | "store-map" | "customers" | "visits";

export interface SalesRMProfile {
  id: number;
  telegram_user_id: number;
  name: string;
  username?: string;
  initials: string;
  total_visits: number;
  unique_merchants: number;
  onboarded_count: number;
  pipeline_count: number;
  target_count: number;
  conversion_rate: number;
  active_working_days: number;
  daily_velocity: number;
  top_districts: Record<string, number>;
  top_categories: Record<string, number>;
}

export interface AvailableRM {
  id: number;
  telegram_user_id: number;
  name: string;
  username?: string;
  initials: string;
  total_visits: number;
  onboarded_count: number;
  conversion_rate: number;
}

export interface TodayKPIs {
  visits_today: number;
  new_visits_today?: number;
  daily_goal?: number;
  onboardings_today: number;
  recent_onboarded_name?: string;
  followups_due: number;
  overdue_count: number;
  scheduled_today_count: number;
  total_customers: number;
}

export interface NearbyStore {
  id: number;
  name: string;
  stage: string;
  status: string;
  latitude: number;
  longitude: number;
  is_assigned_to_me: boolean;
}

export interface TerritoryInfo {
  primary_khan: string;
  center_latitude: number;
  center_longitude: number;
  nearby_stores: NearbyStore[];
}

export interface NextStopItem {
  id: number;
  name: string;
  district: string;
  distance_label: string;
  latitude: number;
  longitude: number;
  action_note: string;
}

export interface PriorityFollowupItem {
  id: number;
  name: string;
  contact_name: string;
  phone: string;
  status: string;
  khqr_stage: string;
  district: string;
  last_visit_date: string;
  due_badge: string;
  due_label: string;
  is_overdue: boolean;
  action_note: string;
  latitude: number;
  longitude: number;
}

export interface VisitTodayItem {
  id: number;
  merchant_id: number;
  name: string;
  time: string;
  outcome: string;
  khqr_stage: string;
  business: string;
  district: string;
  remark: string;
  latitude: number;
  longitude: number;
  map_url?: string;
  phone?: string;
}

export interface TeamActivityItem {
  id: number;
  merchant_name: string;
  rm_name: string;
  rm_initials: string;
  is_you: boolean;
  time: string;
  status: string;
  stage: string;
  district: string;
  remark: string;
  latitude: number;
  longitude: number;
  merchant_id?: number;
  rm_id?: number;
  message: string;
}

export interface TodayDashboardData {
  date_label: string;
  rm_name: string;
  rm_initials: string;
  kpis: TodayKPIs;
  territory: TerritoryInfo;
  next_stop?: NextStopItem | null;
  followups_to_prioritize: PriorityFollowupItem[];
  visits_today: VisitTodayItem[];
  team_activity: TeamActivityItem[];
}

export interface SalesStoreItem {
  id: number;
  name: string;
  category: string;
  address: string;
  district_khan: string;
  latitude: number;
  longitude: number;
  map_url?: string;
  total_visits: number;
  latest_visit_date: string;
  status: string;
  stage: string;
  is_onboarded: boolean;
  is_signed?: boolean;
  days_since_last_visit?: number;
  status_category?: "SIGNED" | "UNSIGNED_RECENT" | "UNSIGNED_DORMANT" | string;
  assigned_reps: string;
  assigned_name: string;
  assigned_initials: string;
  is_assigned_to_me: boolean;
  is_unassigned: boolean;
  latest_remark: string;
  phone: string;
  has_cmcb: boolean;
  has_aba: boolean;
  has_acleda: boolean;
  visit_history?: Array<{
    id: number;
    date: string;
    date_label: string;
    time: string;
    sales_rep: string;
    sales_rep_initials: string;
    status: string;
    stage: string;
    remark: string;
  }>;
}

export interface SalesStoreMapData {
  total_stores_in_view: number;
  unassigned_count: number;
  contacted_count: number;
  onboarded_count: number;
  stores: SalesStoreItem[];
  team_today_summary: Array<{
    rm_id: number;
    name: string;
    initials: string;
    visits: number;
    onboarded: number;
    is_you: boolean;
  }>;
}

export interface SalesCustomerItem {
  id: number;
  name: string;
  contact_name: string;
  business_category: string;
  district: string;
  phone: string;
  status: string;
  stage: string;
  is_onboarded: boolean;
  latest_visit_date: string;
  due_badge: string;
  due_label: string;
  action_note: string;
  days_since_last_visit?: number;
  duration_label?: string;
  total_visits: number;
  latitude: number;
  longitude: number;
}

export interface SalesCustomersData {
  summary: {
    all_count: number;
    total_customers?: number;
    pipeline_count?: number;
    converted_count?: number;
    target_count?: number;
    followups_count?: number;
    overdue_count?: number;
    today_count?: number;
    coming_up_count?: number;
  };
  overdue: SalesCustomerItem[];
  today: SalesCustomerItem[];
  coming_up: SalesCustomerItem[];
  all_customers: SalesCustomerItem[];
  next_cursor?: string | null;
  has_more?: boolean;
  total?: number;
  page_size?: number;
}

export interface SalesVisitItem {
  id: number;
  merchant_id: number;
  name: string;
  date?: string;
  time: string;
  outcome: string;
  khqr_stage: string;
  district: string;
  remark: string;
  phone: string;
  photo_count: number;
  latitude: number;
  longitude: number;
  map_url?: string;
}

export interface SalesVisitGroup {
  date_heading: string;
  date_slug?: string;
  count: number;
  visits: SalesVisitItem[];
}

export interface SalesVisitsData {
  total_visits: number;
  page_count?: number;
  insight_banner: string;
  grouped_sections: SalesVisitGroup[];
  next_cursor?: string | null;
  has_more?: boolean;
  page_size?: number;
}

export interface SalesMerchantTimelineItem {
  id: number;
  rm_name: string;
  rm_initials: string;
  is_you: boolean;
  date: string;
  date_label: string;
  time: string;
  status: string;
  stage: string;
  remark: string;
  photo_count: number;
  latitude: number;
  longitude: number;
}

export interface SalesMerchantDetail {
  id: number;
  name: string;
  category: string;
  district: string;
  address: string;
  stage: string;
  status: string;
  is_onboarded: boolean;
  assigned_reps: string;
  is_assigned_to_me: boolean;
  last_visit_date: string;
  total_visits: number;
  latitude: number;
  longitude: number;
  map_url: string;
  contact: {
    name: string;
    role: string;
    phone: string;
    telegram?: string | null;
  };
  onboarding: {
    current_step: number;
    total_steps: number;
    step_title: string;
    step_description: string;
    steps: string[];
  };
  latest_note: {
    text: string;
    author: string;
    date: string;
  };
  timeline: SalesMerchantTimelineItem[];
}

export interface DropIntervalStats {
  interval_count: number;
  average_gap_seconds: number | null;
  median_gap_seconds: number | null;
  longest_gap_seconds: number | null;
  above_threshold_count: number;
}

export interface ActivitySender extends DropIntervalStats {
  channels: string[];
  last_drop_merchant_name: string | null;
  last_drop_has_gps: boolean;
  last_gap_seconds: number | null;
  last_gap_overnight: boolean;
  first_drop_id: number | null;
  first_drop_merchant_name: string | null;
  start_status: "on_time" | "late_start" | "no_drop";
  is_early_bird: boolean;
  drop_times: string[];
  color: string;
  sender_id: number;
  sender_name: string;
  drop_count: number;
  gps_count: number;
  missing_gps_count: number;
  photo_count: number;
  first_drop_at: string | null;
  last_drop_at: string | null;
  latest_observed_drop_at: string;
}

export interface SalesActivityOverview {
  channels: Array<{ name: string; sender_count: number; drop_count: number }>;
  recognition: DailyRecognition;
  source_status: { state: string; last_success: string | null; last_checked?: string | null; refresh_seconds?: number; error?: string | null };
  date: string;
  today: string;
  timezone: string;
  latest_report_date: string | null;
  available_dates: string[];
  threshold_minutes: number | null;
  summary: DropIntervalStats & {
    drop_count: number;
    active_senders: number;
    observed_senders: number;
    missing_gps_count: number;
  };
  hourly: Array<{ hour: number; drop_count: number }>;
  senders: ActivitySender[];
}

export interface SalesDrop {
  source_channel: string;
  id: number;
  sender_id: number;
  sender_name: string;
  submitted_at: string;
  local_date: string;
  merchant_name: string;
  business: string;
  remark: string;
  has_gps: number;
  has_image: number;
  previous_drop_at: string | null;
  previous_drop_date: string | null;
  gap_seconds: number | null;
  overnight_gap: boolean;
  above_threshold: boolean;
}

export interface SenderActivity extends DropIntervalStats {
  sender_id: number;
  date: string;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  drops: SalesDrop[];
  daily_history: Array<{ date: string; drop_count: number }>;
}

export interface MovementPoint {
  id: number;
  drop_number: number;
  submitted_at: string;
  merchant_name: string;
  latitude: number;
  longitude: number;
}

export interface DropDetail {
  id: number;
  sender_id: number;
  sender_name: string;
  submitted_at: string;
  local_date: string;
  merchant_name: string;
  business: string;
  source_channel: string;
  latitude: number | null;
  longitude: number | null;
  has_gps: number;
  tel: string | null;
  bank: string | null;
  amount: string | null;
  interest: string | null;
  loan_type: string | null;
  maturity: string | null;
  status: string | null;
  report_available: boolean;
}

export interface MovementSegment {
  from_id: number;
  to_id: number;
  from_drop_number: number;
  to_drop_number: number;
  from_time: string;
  to_time: string;
  gap_seconds: number;
  missing_gps_between: number;
  distance_meters: number;
}

export interface SalesMovementTrack {
  sender_id: number;
  sender_name: string;
  color: string;
  drop_count: number;
  missing_gps_count: number;
  points: MovementPoint[];
  segments: MovementSegment[];
}

export interface SalesMovementRoutes {
  date: string;
  timezone: string;
  gps_drop_count: number;
  drop_count: number;
  missing_gps_count: number;
  sender_count: number;
  tracks: SalesMovementTrack[];
}

export interface DailyFirstDrop {
  id: number;
  sender_id: number;
  sender_name: string;
  submitted_at: string;
  merchant_name: string;
  has_gps: number;
  color: string;
}

export interface DailyRecognition {
  cutoff: string;
  timezone: string;
  early_birds: DailyFirstDrop[];
  late_start_count: number;
  on_time_count: number;
}

export interface ActivityFeedEntry extends SalesDrop {
  daily_visit_count: number;
  color: string;
  drop_number: number;
  is_first_drop: boolean;
  is_early_bird: boolean;
  start_status: "on_time" | "late_start" | null;
}

export interface ActivityFeed {
  late_only: boolean;
  date: string;
  timezone: string;
  sender_id: number | null;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  entries: ActivityFeedEntry[];
  recognition: DailyRecognition;
}

export interface ActivityCalendar {
  today: string;
  timezone: string;
  days: string[];
  weeks: Array<{ start: string; end: string; label: string; current: boolean }>;
  senders: Array<{
    sender_id: number;
    sender_name: string;
    color: string;
    daily_counts: number[];
    weekly_counts: number[];
    total_cases: number;
    active_days: number;
  }>;
}
