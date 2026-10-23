"""Phnom Penh Geographic Gazetteer & Smart Location Naming Engine
Maps coordinates to real commercial hubs, major boulevards, and official district zones.
NEVER uses personal merchant names for location titles.
"""

from typing import Dict, Any, List
import math

# Comprehensive Geographic Gazetteer of Phnom Penh Commercial Corridors & Hubs
PHNOM_PENH_GAZETTEER = [
    # =========================================================================
    # 1. MAJOR COMMERCIAL HUBS, MALLS & CENTRAL MARKETS (< 500m radius)
    # =========================================================================
    {"name": "Central Market (Phsar Thmey)", "type": "hub", "lat": 11.5696, "lng": 104.9211, "district": "Doun Penh", "short": "Phsar Thmey"},
    {"name": "Phsar Orussey Market Hub", "type": "hub", "lat": 11.5630, "lng": 104.9152, "district": "7 Makara", "short": "Orussey"},
    {"name": "Russian Market (Phsar Toul Tom Poung)", "type": "hub", "lat": 11.5407, "lng": 104.9151, "district": "Chamkar Mon", "short": "Russian Mkt"},
    {"name": "Olympic Market & Stadium Hub", "type": "hub", "lat": 11.5544, "lng": 104.9126, "district": "7 Makara", "short": "Olympic Hub"},
    {"name": "Aeon Mall 1 Commercial Hub", "type": "hub", "lat": 11.5484, "lng": 104.9351, "district": "Chamkar Mon", "short": "Aeon 1"},
    {"name": "Aeon Mall 2 (Sen Sok Hub)", "type": "hub", "lat": 11.5978, "lng": 104.8778, "district": "Sen Sok", "short": "Aeon 2"},
    {"name": "Aeon Mall 3 (Meanchey Hub)", "type": "hub", "lat": 11.4886, "lng": 104.9287, "district": "Mean Chey", "short": "Aeon 3"},
    {"name": "Chip Mong 271 Mega Mall Area", "type": "hub", "lat": 11.5284, "lng": 104.9168, "district": "Mean Chey", "short": "Chip Mong 271"},
    {"name": "Chip Mong Sen Sok Mall Area", "type": "hub", "lat": 11.5878, "lng": 104.8835, "district": "Sen Sok", "short": "Chip Mong Sen Sok"},
    {"name": "TK Avenue Commercial Hub", "type": "hub", "lat": 11.5833, "lng": 104.8996, "district": "Tuol Kouk", "short": "TK Avenue"},
    {"name": "Phsar Deoum Kor Market Hub", "type": "hub", "lat": 11.5543, "lng": 104.9015, "district": "Tuol Kouk", "short": "Deoum Kor"},
    {"name": "Phsar Kandal Market Area", "type": "hub", "lat": 11.5702, "lng": 104.9298, "district": "Doun Penh", "short": "Phsar Kandal"},
    {"name": "The Olympia Mall Hub", "type": "hub", "lat": 11.5621, "lng": 104.9103, "district": "7 Makara", "short": "Olympia Mall"},
    {"name": "Exchange Square & Vattanac Hub", "type": "hub", "lat": 11.5735, "lng": 104.9205, "district": "Doun Penh", "short": "Vattanac Area"},
    {"name": "Sorya Center Point Area", "type": "hub", "lat": 11.5684, "lng": 104.9228, "district": "Doun Penh", "short": "Sorya Mall"},
    {"name": "Eden Garden / PPCC Area", "type": "hub", "lat": 11.5794, "lng": 104.9152, "district": "Doun Penh", "short": "Eden Garden"},
    {"name": "Phsar Chhouk Meas Market Hub", "type": "hub", "lat": 11.5762, "lng": 104.8631, "district": "Sen Sok", "short": "Chhouk Meas"},
    {"name": "Phsar Samaki Market Area", "type": "hub", "lat": 11.5714, "lng": 104.9077, "district": "Tuol Kouk", "short": "Phsar Samaki"},
    {"name": "Phsar Tuek L'ak Market Area", "type": "hub", "lat": 11.5645, "lng": 104.8966, "district": "Tuol Kouk", "short": "Tuek L'ak"},
    {"name": "Steung Meanchey Market Area", "type": "hub", "lat": 11.5375, "lng": 104.8970, "district": "Mean Chey", "short": "Steung Meanchey"},
    {"name": "Phsar Chbar Ampov Market Hub", "type": "hub", "lat": 11.5361, "lng": 104.9452, "district": "Chbar Ampov", "short": "Chbar Ampov"},

    # =========================================================================
    # 2. MAJOR BOULEVARDS & COMMERCIAL CORRIDORS (Linear Street Arteries)
    # =========================================================================
    {"name": "Street 271 Commercial Corridor", "type": "road", "lat": 11.5360, "lng": 104.9080, "district": "Mean Chey", "short": "St 271"},
    {"name": "Street 271 (Toul Tumpun Section)", "type": "road", "lat": 11.5390, "lng": 104.9120, "district": "Chamkar Mon", "short": "St 271"},
    {"name": "Russian Federation Blvd Corridor", "type": "road", "lat": 11.5670, "lng": 104.8950, "district": "Tuol Kouk", "short": "Russian Blvd"},
    {"name": "Russian Blvd (Airport Section)", "type": "road", "lat": 11.5560, "lng": 104.8620, "district": "Pur SenChey", "short": "Russian Blvd"},
    {"name": "Preah Monivong Blvd Corridor", "type": "road", "lat": 11.5580, "lng": 104.9220, "district": "Doun Penh", "short": "Monivong Blvd"},
    {"name": "Preah Monivong Blvd (South Section)", "type": "road", "lat": 11.5420, "lng": 104.9250, "district": "Chamkar Mon", "short": "Monivong Blvd"},
    {"name": "Preah Sihanouk Blvd Commercial Corridor", "type": "road", "lat": 11.5560, "lng": 104.9250, "district": "Chamkar Mon", "short": "Sihanouk Blvd"},
    {"name": "Mao Tse Toung Blvd Commercial Strip", "type": "road", "lat": 11.5440, "lng": 104.9100, "district": "Chamkar Mon", "short": "Mao Tse Toung"},
    {"name": "Street 2004 Commercial Corridor", "type": "road", "lat": 11.5480, "lng": 104.8690, "district": "Pur SenChey", "short": "St 2004"},
    {"name": "Veng Sreng Blvd Commercial Strip", "type": "road", "lat": 11.5270, "lng": 104.8650, "district": "Pur SenChey", "short": "Veng Sreng"},
    {"name": "Street 315 / 289 Dining Corridor", "type": "road", "lat": 11.5775, "lng": 104.9005, "district": "Tuol Kouk", "short": "St 315/289"},
    {"name": "BKK1 Cafe & Retail Corridor", "type": "road", "lat": 11.5515, "lng": 104.9270, "district": "Boeng Keng Kang", "short": "BKK1 Corridor"},
    {"name": "Kampuchea Krom Blvd Commercial Strip", "type": "road", "lat": 11.5680, "lng": 104.9080, "district": "7 Makara", "short": "Kampuchea Krom"},
    {"name": "Hanoi Blvd (Street 1019) Strip", "type": "road", "lat": 11.5880, "lng": 104.8720, "district": "Sen Sok", "short": "Hanoi Blvd"},
    {"name": "Oknha Mong Reththy Blvd (St 1928)", "type": "road", "lat": 11.5950, "lng": 104.8820, "district": "Sen Sok", "short": "Mong Reththy"},
    {"name": "Chea Sophara Blvd (Street 598)", "type": "road", "lat": 11.6050, "lng": 104.8930, "district": "Russey Keo", "short": "Chea Sophara"},
    {"name": "National Road 1 (Boeung Snor Hub)", "type": "road", "lat": 11.5220, "lng": 104.9650, "district": "Chbar Ampov", "short": "NR 1"},
    {"name": "National Road 2 Commercial Strip", "type": "road", "lat": 11.5050, "lng": 104.9380, "district": "Mean Chey", "short": "NR 2"},
    {"name": "National Road 3 Commercial Hub", "type": "road", "lat": 11.5120, "lng": 104.8250, "district": "Pur SenChey", "short": "NR 3"},
    {"name": "National Road 4 (Chom Chao Hub)", "type": "road", "lat": 11.5240, "lng": 104.8390, "district": "Pur SenChey", "short": "Chom Chao"},
    {"name": "National Road 5 (Kilometre 6 Strip)", "type": "road", "lat": 11.6150, "lng": 104.9080, "district": "Russey Keo", "short": "NR 5"},
    {"name": "National Road 6A Commercial Strip", "type": "road", "lat": 11.6020, "lng": 104.9350, "district": "Chroy Changvar", "short": "NR 6A"},
    {"name": "Chamkar Doung (Street 217) Commercial Corridor", "type": "road", "lat": 11.5150, "lng": 104.8870, "district": "Dangkao", "short": "Chamkar Doung"},
    {"name": "Hun Sen Blvd (60m Road) Strip", "type": "road", "lat": 11.5050, "lng": 104.9220, "district": "Mean Chey", "short": "Hun Sen Blvd"},
    {"name": "Toul Tom Poung St 432 / 450 Corridor", "type": "road", "lat": 11.5385, "lng": 104.9140, "district": "Chamkar Mon", "short": "St 432/450"},

    # =========================================================================
    # 3. REGIONAL SANGKAT COMMERCIAL DISTRICT ZONES (Comprehensive Coverage)
    # =========================================================================
    {"name": "Phnom Penh Thmey Commercial Zone", "type": "sangkat", "lat": 11.5810, "lng": 104.8850, "district": "Sen Sok", "short": "PP Thmey"},
    {"name": "Teuk Thla Commercial Zone", "type": "sangkat", "lat": 11.5580, "lng": 104.8800, "district": "Sen Sok", "short": "Teuk Thla"},
    {"name": "Boeng Tumpun Commercial Zone", "type": "sangkat", "lat": 11.5320, "lng": 104.9050, "district": "Mean Chey", "short": "Boeng Tumpun"},
    {"name": "Chak Angre Krom Commercial Zone", "type": "sangkat", "lat": 11.5120, "lng": 104.9350, "district": "Mean Chey", "short": "Chak Angre"},
    {"name": "Kakab / Airport Commercial Area", "type": "sangkat", "lat": 11.5510, "lng": 104.8480, "district": "Pur SenChey", "short": "Kakab"},
    {"name": "Chaom Chau Industrial / Retail Hub", "type": "sangkat", "lat": 11.5280, "lng": 104.8450, "district": "Pur SenChey", "short": "Chaom Chau"},
    {"name": "Dangkao Commercial Town Strip", "type": "sangkat", "lat": 11.5120, "lng": 104.8820, "district": "Dangkao", "short": "Dangkao"},
    {"name": "Toul Sangke Commercial Zone", "type": "sangkat", "lat": 11.5950, "lng": 104.9050, "district": "Russey Keo", "short": "Toul Sangke"},
    {"name": "Chroy Changvar OCIC Satellite Zone", "type": "sangkat", "lat": 11.5950, "lng": 104.9320, "district": "Chroy Changvar", "short": "Chroy Changvar"},
    {"name": "Prek Pnov Commercial Hub", "type": "sangkat", "lat": 11.6608, "lng": 104.8396, "district": "Prek Pnov", "short": "Prek Pnov"}
]

def get_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculates approximate ground distance in meters."""
    dy = (lat1 - lat2) * 110574.0
    dx = (lng1 - lng2) * 108940.0
    return math.sqrt(dx * dx + dy * dy)

def resolve_cluster_name(center_lat: float, center_lng: float, top_merchant_name: str = None, fallback_idx: int = 0) -> Dict[str, str]:
    """
    Intelligently resolves real, official geographic titles for cluster centers.
    Priority 1: Major Commercial Malls & Markets (< 500m)
    Priority 2: Major Boulevards & Commercial Arteries (< 450m)
    Priority 3: Official Sangkat & District Zone (< 1500m)
    NEVER returns raw merchant names.
    """
    nearest_hub = None
    min_hub_dist = float("inf")

    nearest_road = None
    min_road_dist = float("inf")

    nearest_sangkat = None
    min_sangkat_dist = float("inf")

    for loc in PHNOM_PENH_GAZETTEER:
        d = get_distance_meters(center_lat, center_lng, loc["lat"], loc["lng"])
        if loc["type"] == "hub" and d < min_hub_dist:
            min_hub_dist = d
            nearest_hub = loc
        elif loc["type"] == "road" and d < min_road_dist:
            min_road_dist = d
            nearest_road = loc
        elif loc["type"] == "sangkat" and d < min_sangkat_dist:
            min_sangkat_dist = d
            nearest_sangkat = loc

    # Priority 1: Commercial Hubs / Markets / Malls within 500m
    if nearest_hub and min_hub_dist <= 500.0:
        prefix = "" if min_hub_dist <= 220.0 else "Near "
        return {
            "title": f"{prefix}{nearest_hub['name']}",
            "district": nearest_hub["district"],
            "short_name": nearest_hub["short"]
        }

    # Priority 2: Major Boulevard / Road Arteries within 450m
    if nearest_road and min_road_dist <= 450.0:
        return {
            "title": nearest_road["name"],
            "district": nearest_road["district"],
            "short_name": nearest_road["short"]
        }

    # Priority 3: Official Sangkat Commercial Zone
    if nearest_sangkat and min_sangkat_dist <= 1500.0:
        return {
            "title": nearest_sangkat["name"],
            "district": nearest_sangkat["district"],
            "short_name": nearest_sangkat["short"]
        }

    # Fallback: Nearest geographic location from gazetteer (Never merchant name!)
    best = nearest_road or nearest_sangkat or nearest_hub or PHNOM_PENH_GAZETTEER[0]
    name = best["name"]
    suffix = "" if any(name.endswith(w) for w in ["Area", "Hub", "Corridor", "Strip", "Zone", "Market"]) else " Area"
    return {
        "title": f"{name}{suffix}",
        "district": best["district"],
        "short_name": best["short"]
    }
