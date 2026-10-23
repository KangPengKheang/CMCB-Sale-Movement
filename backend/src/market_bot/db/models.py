from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


@dataclass
class SenderInfo:
    sender_id: int
    sender_name: str
    username: Optional[str] = None
    identity_key: str = ""


@dataclass
class ParsedLocation:
    latitude: float
    longitude: float
    msg_id: int
    msg_date: int  # unix epoch
    iso_date: str
    is_live: bool = False


@dataclass
class ParsedForm:
    name: str = ""
    tel: str = ""
    tel_clean: str = ""
    business: str = ""
    business_clean: str = ""
    purpose: str = "CMCB Products"
    bank: str = ""
    has_aba: int = 0
    has_acleda: int = 0
    has_cmcb: int = 0
    has_other_bank: int = 0
    amount: str = "N/A"
    interest: str = "N/A"
    loan_type: str = "N/A"
    tenure: str = "N/A"
    maturity: str = "N/A"
    status: str = "OP"
    status_clean: str = "OP"
    khqr_stage: str = "TARGET"
    potential_level: str = "L"
    potential_product: str = "KHQR"
    remark: str = ""
    raw_text: str = ""
    is_valid: bool = False


@dataclass
class MerchantReportRecord:
    id: Optional[int] = None
    merchant_id: Optional[int] = None
    rm_id: Optional[int] = None
    report_time: str = ""
    sender_id: int = 0
    sender_name: str = ""
    merchant_name: str = ""
    tel: str = ""
    tel_clean: str = ""
    business: str = ""
    business_clean: str = ""
    purpose: str = ""
    bank: str = ""
    has_aba: int = 0
    has_acleda: int = 0
    has_cmcb: int = 0
    has_other_bank: int = 0
    amount: str = "N/A"
    interest: str = "N/A"
    loan_type: str = "N/A"
    tenure: str = "N/A"
    maturity: str = "N/A"
    status: str = ""
    status_clean: str = ""
    khqr_stage: str = "TARGET"
    potential_level: str = "L"
    potential_product: str = ""
    remark: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    district_khan: str = "Other / Outside PP"
    map_url: str = ""
    location_time: str = ""
    location_diff_seconds: float = 0.0
    form_msg_id: Optional[int] = None
    location_msg_id: Optional[int] = None
    photo_count: int = 1
    photo_msg_ids: str = "[]"
    raw_text: str = ""


@dataclass
class MerchantRecord:
    id: Optional[int] = None
    canonical_name: str = ""
    business_category: str = "General"
    tel: str = "N/A"
    district_khan: str = "Other / Outside PP"
    latitude: float = 0.0
    longitude: float = 0.0
    map_url: str = ""
    total_visits: int = 1
    first_visit_date: str = ""
    latest_visit_date: str = ""
    current_status: str = "OP"
    current_khqr_stage: str = "TARGET"
    is_onboarded: int = 0
    competitor_banks: str = ""
    has_aba: int = 0
    has_acleda: int = 0
    has_cmcb: int = 0
    has_other_bank: int = 0
    assigned_reps: str = ""
    latest_remark: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class RMRecord:
    id: Optional[int] = None
    telegram_user_id: int = 0
    canonical_name: str = ""
    username: Optional[str] = None
    first_active_date: str = ""
    latest_active_date: str = ""
    total_visits_logged: int = 1
    unique_merchants_reached: int = 1
    onboarded_count: int = 0
    pipeline_count: int = 0
    target_count: int = 0
    conversion_rate: float = 0.0
    active_working_days: int = 1
    daily_visit_velocity: float = 1.0
    top_districts: str = "{}"   # JSON: {"Sen Sok": 18, ...}
    top_categories: str = "{}"  # JSON: {"Coffee Shop / Cafe": 12, ...}
    compliance_errors: int = 0
    created_at: str = ""
    updated_at: str = ""


# Pydantic Schemas for FastAPI REST Responses

class VisitTimelineItem(BaseModel):
    visit_id: int
    merchant_id: Optional[int] = None
    rm_id: Optional[int] = None
    visit_no: int
    report_time: str
    sales_rep: str
    status: str
    khqr_stage: str
    bank: Optional[str] = None
    remark: Optional[str] = None
    photo_count: int = 1
    latitude: float
    longitude: float
    map_url: Optional[str] = None
    # Populated by the RM visit feed so the route trail can label each stop.
    merchant_name: Optional[str] = None
    business: Optional[str] = None
    district_khan: Optional[str] = None


class MerchantResponse(BaseModel):
    id: int
    canonical_name: str
    business_category: str
    tel: str
    district_khan: str
    latitude: float
    longitude: float
    map_url: Optional[str] = None
    total_visits: int
    first_visit_date: str
    latest_visit_date: str
    current_status: str
    current_khqr_stage: str
    is_onboarded: int
    has_aba: int
    has_acleda: int
    has_cmcb: int
    has_other_bank: int
    assigned_reps: str
    latest_remark: Optional[str] = None


class MerchantDetailResponse(MerchantResponse):
    visits: List[VisitTimelineItem] = []


class RMResponse(BaseModel):
    id: int
    rm_id: Optional[int] = None
    telegram_user_id: int
    canonical_name: str
    name: Optional[str] = None
    username: Optional[str] = None
    first_active_date: str
    latest_active_date: str
    total_visits_logged: int
    unique_merchants_reached: int
    onboarded_count: int
    pipeline_count: int
    target_count: int
    conversion_rate: float
    active_working_days: int
    daily_visit_velocity: float
    compliance_errors: int
    top_districts: Dict[str, int] = {}
    top_categories: Dict[str, int] = {}
    visits: List[Dict[str, Any]] = []

class RMHabitsResponse(BaseModel):
    rm_id: int
    rm_name: str
    top_districts: Dict[str, int]
    top_categories: Dict[str, int]
    daily_visit_velocity: float
    active_working_days: int


class RMDetailResponse(RMResponse):
    top_districts: Dict[str, int] = {}
    top_categories: Dict[str, int] = {}
    recent_visits: List[VisitTimelineItem] = []


class MerchantReportResponse(BaseModel):
    id: int
    merchant_id: Optional[int] = None
    rm_id: Optional[int] = None
    report_time: str
    sender_id: Optional[int] = None
    sender_name: str
    merchant_name: str
    tel: Optional[str] = None
    tel_clean: Optional[str] = None
    business: Optional[str] = None
    business_clean: Optional[str] = None
    purpose: Optional[str] = None
    bank: Optional[str] = None
    has_aba: int = 0
    has_acleda: int = 0
    has_cmcb: int = 0
    has_other_bank: int = 0
    amount: Optional[str] = None
    interest: Optional[str] = None
    loan_type: Optional[str] = None
    tenure: Optional[str] = None
    maturity: Optional[str] = None
    status: Optional[str] = None
    status_clean: Optional[str] = None
    khqr_stage: str
    potential_level: Optional[str] = None
    potential_product: Optional[str] = None
    remark: Optional[str] = None
    latitude: float
    longitude: float
    district_khan: Optional[str] = None
    map_url: Optional[str] = None
    photo_count: int = 1


class DeadLetterResponse(BaseModel):
    id: int
    msg_id: Optional[int] = None
    msg_date: str
    sender_name: str
    message_type: str
    reason: str
    raw_content: Optional[str] = None


class StatsSummaryResponse(BaseModel):
    total_visits: int
    total_merchants: int = 0
    total_rms: int = 0
    cmcb_deployed: int
    in_pipeline: int
    competitor_only: int
    active_districts: int
    cold_districts: int
    total_photos_linked: int
    total_dlq_items: int
