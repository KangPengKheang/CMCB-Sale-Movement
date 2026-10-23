"""
Comprehensive Cambodian Banking Institution & Channel Normalizer.

Standardizes messy sales rep Telegram inputs (e.g. 'AC, ABA (KHQR, POS)', 'ACKEDA KHQR', 'BAB')
into canonical commercial bank entities, distinct payment channels, and flag aggregates.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class NormalizedBankResult:
    raw: str
    institutions: List[str] = field(default_factory=list)  # e.g. ["ABA Bank", "ACLEDA Bank"]
    bank_codes: List[str] = field(default_factory=list)    # e.g. ["ABA", "ACLEDA"]
    products: List[str] = field(default_factory=list)      # e.g. ["KHQR", "POS"]
    has_aba: int = 0
    has_acleda: int = 0
    has_cmcb: int = 0
    has_wing: int = 0
    has_canadia: int = 0
    has_kb_prasac: int = 0
    has_sathapana: int = 0
    has_other_bank: int = 0
    canonical_summary: str = "N/A"                         # e.g. "ABA Bank, ACLEDA Bank"
    products_summary: str = "None"                         # e.g. "KHQR, POS"


# Standardized bank definitions with canonical naming and regex patterns
# Ordered with specific/longer names first to avoid greedy substring collisions
BANK_DEFINITIONS = [
    {
        "code": "CMCB",
        "name": "Chip Mong Bank",
        "patterns": [
            r"\bcmcb\b",
            r"chip\s*mong",
            r"chipmong",
        ],
    },
    {
        "code": "ABA",
        "name": "ABA Bank",
        "patterns": [
            r"\baba\b",
            r"\bbab\b",  # common RM typo
            r"advanced\s*bank\s*of\s*asia",
        ],
    },
    {
        "code": "ACLEDA",
        "name": "ACLEDA Bank",
        "patterns": [
            r"\bacleda\b",
            r"\backeda\b",   # common RM typo
            r"\bacelida\b",  # common RM typo
            r"\bac\b",       # standard shorthand
        ],
    },
    {
        "code": "WING",
        "name": "Wing Bank",
        "patterns": [
            r"\bwing\b",
            r"wing\s*bank",
        ],
    },
    {
        "code": "KBPRASAC",
        "name": "KB Prasac Bank",
        "patterns": [
            r"kb\s*prasac",
            r"\bprasac\b",
            r"\bkb\b",
        ],
    },
    {
        "code": "CANADIA",
        "name": "Canadia Bank",
        "patterns": [
            r"\bcanadia\b",
            r"\bcnb\b",
        ],
    },
    {
        "code": "SATHAPANA",
        "name": "Sathapana Bank",
        "patterns": [
            r"\bsathapana\b",
            r"\bspn\b",
        ],
    },
    {
        "code": "AMRET",
        "name": "Amret MFI",
        "patterns": [
            r"\bamret\b",
        ],
    },
    {
        "code": "PHILLIP",
        "name": "Phillip Bank",
        "patterns": [
            r"\bphillip\b",
            r"\bphilip\b",
            r"\bfilip\b",  # phonetic Khmer typo
        ],
    },
    {
        "code": "WOORI",
        "name": "Woori Bank",
        "patterns": [
            r"\bwoori\b",
            r"\bworri\b",  # common RM typo
        ],
    },
    {
        "code": "DGB",
        "name": "DGB Bank",
        "patterns": [
            r"\bdgb\b",
        ],
    },
    {
        "code": "MB",
        "name": "MB Bank",
        "patterns": [
            r"\bmb\s*bank\b",
            r"\bmb\b",
        ],
    },
    {
        "code": "BOC",
        "name": "Bank of China",
        "patterns": [
            r"bank\s*of\s*china",
            r"china\s*bank",
            r"\bboc\b",
        ],
    },
    {
        "code": "MAYBANK",
        "name": "Maybank",
        "patterns": [
            r"may\s*bank",
            r"\bmaybank\b",
        ],
    },
    {
        "code": "FTB",
        "name": "FTB Bank",
        "patterns": [
            r"\bftb\b",
            r"foreign\s*trade\s*bank",
        ],
    },
    {
        "code": "PRINCE",
        "name": "Prince Bank",
        "patterns": [
            r"\bprince\b",
        ],
    },
    {
        "code": "PPCBANK",
        "name": "PPCBank",
        "patterns": [
            r"\bppc\b",
            r"\bppcbank\b",
        ],
    },
    {
        "code": "JTRUST",
        "name": "J Trust Royal Bank",
        "patterns": [
            r"j\s*trust",
            r"jtrust",
        ],
    },
    {
        "code": "VATTANAC",
        "name": "Vattanac Bank",
        "patterns": [
            r"\bvattanac\b",
        ],
    },
    {
        "code": "SHINHAN",
        "name": "Shinhan Bank",
        "patterns": [
            r"\bshinhan\b",
        ],
    },
]


def normalize_banks(raw_bank: Optional[str]) -> NormalizedBankResult:
    """
    Parses messy sales rep bank text into structured bank entities and products.

    Examples:
        'AC, ABA(KHQR)' -> institutions: ['ACLEDA Bank', 'ABA Bank'], products: ['KHQR']
        'CMCB (KHQR ,POS)' -> institutions: ['Chip Mong Bank'], products: ['KHQR', 'POS']
        'ABA ,KB(POS)' -> institutions: ['ABA Bank', 'KB Prasac Bank'], products: ['POS']
        'Filip KHQR' -> institutions: ['Phillip Bank'], products: ['KHQR']
    """
    raw_str = str(raw_bank or "").strip()
    if not raw_str or raw_str.upper() in ["N/A", "NA", "NONE", "NO", "EMPTY", "0", "-", "?"]:
        return NormalizedBankResult(raw=raw_str, canonical_summary="None", products_summary="None")

    text_lower = raw_str.lower()

    # 1. Detect Products / Channels
    products: List[str] = []
    if "khqr" in text_lower or "qr" in text_lower:
        products.append("KHQR")
    if "pos" in text_lower or "terminal" in text_lower:
        products.append("POS")
    if "loan" in text_lower or "credit" in text_lower:
        products.append("LOAN")

    # 2. Detect Institutions
    detected_codes: List[str] = []
    detected_names: List[str] = []

    for bank_def in BANK_DEFINITIONS:
        matched = False
        for pattern in bank_def["patterns"]:
            if re.search(pattern, text_lower):
                matched = True
                break
        if matched:
            detected_codes.append(bank_def["code"])
            detected_names.append(bank_def["name"])

    # 3. Individual specific bank flags
    has_aba = 1 if "ABA" in detected_codes else 0
    has_acleda = 1 if "ACLEDA" in detected_codes else 0
    has_cmcb = 1 if "CMCB" in detected_codes else 0
    has_wing = 1 if "WING" in detected_codes else 0
    has_canadia = 1 if "CANADIA" in detected_codes else 0
    has_kb = 1 if "KBPRASAC" in detected_codes else 0
    has_sathapana = 1 if "SATHAPANA" in detected_codes else 0

    # 'Other' is any competitor bank other than ABA and ACLEDA
    competitor_codes = [c for c in detected_codes if c not in ["CMCB", "ABA", "ACLEDA"]]
    has_other_bank = 1 if len(competitor_codes) > 0 else 0

    canonical_summary = ", ".join(detected_names) if detected_names else (raw_str if raw_str else "None")
    products_summary = ", ".join(products) if products else "None"

    return NormalizedBankResult(
        raw=raw_str,
        institutions=detected_names,
        bank_codes=detected_codes,
        products=products,
        has_aba=has_aba,
        has_acleda=has_acleda,
        has_cmcb=has_cmcb,
        has_wing=has_wing,
        has_canadia=has_canadia,
        has_kb_prasac=has_kb,
        has_sathapana=has_sathapana,
        has_other_bank=has_other_bank,
        canonical_summary=canonical_summary,
        products_summary=products_summary,
    )
