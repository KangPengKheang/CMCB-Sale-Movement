import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from ..db.models import ParsedForm, ParsedLocation, SenderInfo
from .bank_normalizer import normalize_banks
REQUIRED_KEYS = ["Name"]


def extract_sender_info(msg: Dict[str, Any]) -> SenderInfo:
    """
    Extracts the sender identity from a Telegram message dictionary.
    Handles standard users, forwarded channels, and hidden forward names.
    """
    from_user = msg.get("from", {})
    if from_user:
        user_id = from_user.get("id", 0)
        first_name = str(from_user.get("first_name") or "").strip()
        last_name = str(from_user.get("last_name") or "").strip()
        username = from_user.get("username")

        parts = [p for p in [first_name, last_name] if p and p.lower() != "none"]
        display_name = " ".join(parts) if parts else f"User_{user_id}"
        if username:
            display_name += f" (@{username})"

        return SenderInfo(
            sender_id=user_id,
            sender_name=display_name,
            username=username,
            identity_key=f"user:{user_id}",
        )

    # Forwarded sender fallback
    fwd_user = msg.get("forward_from", {})
    if fwd_user:
        user_id = fwd_user.get("id", 0)
        display_name = f"{fwd_user.get('first_name', '')} {fwd_user.get('last_name', '')}".strip() or f"User_{user_id}"
        return SenderInfo(
            sender_id=user_id,
            sender_name=display_name,
            username=fwd_user.get("username"),
            identity_key=f"fwd_user:{user_id}",
        )

    fwd_name = msg.get("forward_sender_name")
    if fwd_name:
        return SenderInfo(
            sender_id=0,
            sender_name=fwd_name.strip(),
            identity_key=f"fwd_name:{fwd_name.strip()}",
        )

    sender_chat = msg.get("sender_chat")
    if sender_chat and isinstance(sender_chat, dict):
        chat_title = sender_chat.get("title", "").strip()
        chat_id = sender_chat.get("id", 0)
        return SenderInfo(
            sender_id=chat_id,
            sender_name=chat_title or f"Channel_{chat_id}",
            identity_key=f"chat:{chat_id}",
        )

    return SenderInfo(sender_id=0, sender_name="Unknown", identity_key="unknown:0")


def parse_location(msg: Dict[str, Any]) -> Optional[ParsedLocation]:
    """
    Extracts latitude and longitude from a Telegram message if present.
    """
    loc = msg.get("location")
    if not loc or not isinstance(loc, dict):
        return None

    lat = loc.get("latitude")
    lng = loc.get("longitude")
    if lat is None or lng is None:
        return None

    try:
        lat_f = float(lat)
        lng_f = float(lng)
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            return None
    except (ValueError, TypeError):
        return None

    msg_id = msg.get("message_id", 0)
    msg_date = msg.get("date", int(datetime.now(timezone.utc).timestamp()))
    iso_date = datetime.fromtimestamp(msg_date, tz=timezone.utc).isoformat()
    is_live = bool(loc.get("live_period"))

    return ParsedLocation(
        latitude=lat_f,
        longitude=lng_f,
        msg_id=msg_id,
        msg_date=msg_date,
        iso_date=iso_date,
        is_live=is_live,
    )


def normalize_phone(raw_tel: Optional[str]) -> str:
    t = str(raw_tel or "").strip()
    if not t or t.upper() in ["N/A", "NA", "NONE", ""]:
        return "N/A"
    if "TG" in t.upper() or "TELEGRAM" in t.upper():
        return "TELEGRAM"
    cleaned = re.sub(r"[^\d+]", "", t)
    return cleaned if cleaned else t


def normalize_business(raw_biz: Optional[str]) -> str:
    b = str(raw_biz or "").strip()
    lower = b.lower()
    if "coffee" in lower or "coffe" in lower or "cafe" in lower:
        return "Coffee Shop / Cafe"
    if "fashion" in lower:
        return "Fashion / Clothing"
    if "restaurant" in lower or "food" in lower:
        return "Restaurant / Food"
    if "phone" in lower:
        return "Phone Shop"
    if "milk tea" in lower or "matcha" in lower:
        return "Beverage / Milk Tea"
    if "shoe" in lower or "shose" in lower:
        return "Shoes Store"
    if "cosmetic" in lower:
        return "Cosmetics"
    return b if b else "General"


def normalize_status(raw_status: Optional[str]) -> str:
    s = str(raw_status or "").strip()
    lower = s.lower()
    if "exsiting" in lower or "existing" in lower:
        return "Existing"
    if "new visit" in lower or lower == "new":
        return "New Visit"
    if "follow up" in lower:
        return "Follow Up"
    if "ap" in lower:
        return "AP"
    if "op" in lower:
        return "OP"
    return s if s else "OP"


def classify_khqr_stage(status_clean: str, remark: str, bank: str) -> str:
    s = (status_clean or "").lower()
    r = (remark or "").lower()
    b = (bank or "").upper()

    # 1. Converted/Signed: Matches signed, sign, sign khqr, deployed, account opening, etc.
    # Uses word boundary regex or specific phrases so words like 'design' or 'consignment' are not falsely matched
    is_signed = bool(
        re.search(r"\b(sign|signed|signing)\b", r)
        or any(k in r for k in ["deployed", "deploy", "account opening", "acount opening", "open khqr", "replace new khqr"])
        or "existing" in s
    )
    if is_signed:
        return "CONVERTED"

    # 2. Pipeline: In discussions, follow up, partnership exploration
    if "follow up" in s or "discuss" in r or "partnership" in r or "contact" in r or "interest" in r:
        return "PIPELINE"

    # 3. Existing CMCB presence
    bank_info = normalize_banks(bank)
    if bank_info.has_cmcb:
        return "EXISTING"
    return "TARGET"


def parse_competitor_banks(raw_bank: Optional[str]) -> Tuple[int, int, int, int]:
    norm = normalize_banks(raw_bank)
    return norm.has_aba, norm.has_acleda, norm.has_cmcb, norm.has_other_bank

def parse_merchant_form(text: Optional[str]) -> ParsedForm:
    """
    Extracts the standardized 14-field visit report from text/caption.
    """
    if not text:
        return ParsedForm(is_valid=False)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    fields: Dict[str, str] = {}

    for line in lines:
        # 1. Match standard "Key: Value" or "Key; Value" (handles Remark; Deployed KHQR)
        match = re.match(r"^([^:;]+)[:;]\s*(.*)$", line)
        if match:
            raw_k = match.group(1).strip()
            v = match.group(2).strip()
            clean_k = raw_k.replace(r"\_", "_").replace(r"\*", "*").strip()
            fields[clean_k] = v
            continue

        # 2. Tolerant pattern: "Name John Doe" (handles missing colon on Name)
        name_match = re.match(r"^Name\s+([^:].*)$", line, re.IGNORECASE)
        if name_match and "Name" not in fields:
            fields["Name"] = name_match.group(1).strip()
            continue

        # 3. Tolerant pattern: "Business Cafe" (handles missing colon on Business)
        biz_match = re.match(r"^Business\s+([^:].*)$", line, re.IGNORECASE)
        if biz_match and "Business" not in fields:
            fields["Business"] = biz_match.group(1).strip()
            continue

    # Check required key (Name is mandatory)
    name = (fields.get("Name") or fields.get("name") or "").strip()
    if not name:
        return ParsedForm(is_valid=False, raw_text=text)

    tel = (fields.get("Tel") or fields.get("tel") or "").strip()
    business = (fields.get("Business") or fields.get("business") or "General").strip()
    purpose = (fields.get("Purpose") or fields.get("The Purpose") or fields.get("purpose") or "CMCB Products").strip()
    bank = (fields.get("Bank") or fields.get("bank") or "").strip()
    status = (fields.get("Status") or fields.get("status") or "OP").strip()
    potential_level = (fields.get("Potential H/M/L") or fields.get("Potential") or "L").strip()
    potential_product = (
        fields.get("Potential Product")
        or fields.get("Potential Produce")
        or fields.get("Potential product")
        or fields.get("potential product")
        or "KHQR"
    ).strip()
    remark = (
        fields.get("Remark")
        or fields.get("Remarks")
        or fields.get("remark")
        or fields.get("remarks")
        or ""
    ).strip()

    tel_clean = normalize_phone(tel)
    biz_clean = normalize_business(business)
    status_clean = normalize_status(status)
    khqr_stage = classify_khqr_stage(status_clean, remark, bank)
    has_aba, has_acleda, has_cmcb, has_other = parse_competitor_banks(bank)

    return ParsedForm(
        name=name,
        tel=tel,
        tel_clean=tel_clean,
        business=business,
        business_clean=biz_clean,
        purpose=purpose,
        bank=bank,
        has_aba=has_aba,
        has_acleda=has_acleda,
        has_cmcb=has_cmcb,
        has_other_bank=has_other,
        amount=(fields.get("Amount") or fields.get("amount") or fields.get("Estimated_USD") or "N/A").strip(),
        interest=(fields.get("Interest") or fields.get("interest") or "N/A").strip(),
        loan_type=(fields.get("Loan Type") or fields.get("loan_type") or "N/A").strip(),
        tenure=(fields.get("Tenure") or fields.get("tenure") or "N/A").strip(),
        maturity=(fields.get("Maturity") or fields.get("maturity") or "N/A").strip(),
        status=status,
        status_clean=status_clean,
        khqr_stage=khqr_stage,
        potential_level=potential_level,
        potential_product=potential_product,
        remark=remark,
        raw_text=text,
        is_valid=True,
    )


def point_in_polygon(x: float, y: float, poly_coords: List[List[float]]) -> bool:
    inside = False
    n = len(poly_coords)
    p1x, p1y = poly_coords[0]
    for i in range(1, n + 1):
        p2x, p2y = poly_coords[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def match_khan_boundary(lng: float, lat: float, features: List[Dict[str, Any]]) -> str:
    for f in features:
        geom = f.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype == "Polygon" and coords:
            if point_in_polygon(lng, lat, coords[0]):
                return f.get("properties", {}).get("hrname", "Other / Outside PP")
        elif gtype == "MultiPolygon" and coords:
            for poly in coords:
                if point_in_polygon(lng, lat, poly[0]):
                    return f.get("properties", {}).get("hrname", "Other / Outside PP")
    return "Other / Outside PP"
