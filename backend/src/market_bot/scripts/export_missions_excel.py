"""Field Sales Strike Mission Excel Exporter.
Generates an actionable, field-ready Excel checklist with:
1. Walkable Strike Missions (Park Once, Sweep down the street).
2. Linear sweep stop order (eliminates backtracking and U-turns).
3. 1-Tap Google Maps navigation hyperlinks for mobile devices.
4. Native Excel dropdown validation for Visit Status.
5. Executive Manager Summary ranked by uncaptured weekly transaction volume.
"""

from typing import List, Dict, Any, Optional
import math
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


def compute_corridor_linear_sweep(merchants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Orders merchants along the primary principal axis of the corridor
    so field sales reps walk or ride straight down the street with no backtracking.
    """
    if len(merchants) <= 1:
        return merchants
    if len(merchants) == 2:
        return merchants

    # 1. Find the two furthest endpoints in the cluster
    max_dist = -1.0
    pA = merchants[0]
    pB = merchants[0]
    for i in range(len(merchants)):
        for j in range(i + 1, len(merchants)):
            m1, m2 = merchants[i], merchants[j]
            dy = (float(m1.get("latitude", 0)) - float(m2.get("latitude", 0))) * 110574.0
            dx = (float(m1.get("longitude", 0)) - float(m2.get("longitude", 0))) * 108940.0
            d = math.sqrt(dx * dx + dy * dy)
            if d > max_dist:
                max_dist = d
                pA, pB = m1, m2

    v_lat = float(pB.get("latitude", 0)) - float(pA.get("latitude", 0))
    v_lng = float(pB.get("longitude", 0)) - float(pA.get("longitude", 0))
    v_len_sq = v_lat * v_lat + v_lng * v_lng

    if v_len_sq < 1e-12:
        return merchants

    # 2. Project each merchant onto vector V
    scored = []
    for m in merchants:
        m_lat = float(m.get("latitude", 0))
        m_lng = float(m.get("longitude", 0))
        proj = ((m_lat - float(pA.get("latitude", 0))) * v_lat + (m_lng - float(pA.get("longitude", 0))) * v_lng) / v_len_sq
        scored.append((proj, m))

    scored.sort(key=lambda x: x[0])
    return [item[1] for item in scored]


def get_walkability_label(corridor_length_m: float) -> str:
    if corridor_length_m <= 220:
        return f"🚶 Highly Walkable (~{int(corridor_length_m)}m - Park Once)"
    elif corridor_length_m <= 500:
        return f"🚶 Walk or Short Ride (~{int(corridor_length_m)}m)"
    else:
        return f"🛵 Motorbike Corridor (~{int(corridor_length_m)}m)"


def get_priority_tier(txns: int) -> Dict[str, str]:
    if txns >= 100:
        return {"label": "🔥 Flagship (>100)", "fill": "FCE8E6", "color": "C5221F"}
    elif txns >= 50:
        return {"label": "⭐ High-Yield (50-99)", "fill": "FEF7E0", "color": "B06000"}
    else:
        return {"label": "Standard (11-49)", "fill": "F1F3F4", "color": "3C4043"}


def export_strike_missions_to_excel(
    clusters: List[Dict[str, Any]],
    week_label: str = "Latest Snapshot Week",
    output_path: Optional[Path] = None
) -> openpyxl.Workbook:
    """Builds a fully-formatted, actionable Excel workbook with 2 tabs:
    - Tab 1: Field_Sales_Checklist (for sales reps on foot/bike)
    - Tab 2: Manager_Zone_Summary (for sales management)
    """
    wb = openpyxl.Workbook()

    # Shared Styles
    brand_green = "006B3F"
    dark_green = "004D2E"
    thin_border_side = Side(style="thin", color="E0E0E0")
    grid_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    header_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="medium", color=dark_green),
        bottom=Side(style="medium", color=dark_green)
    )

    # =========================================================================
    # TAB 1: FIELD SALES CHECKLIST
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Field_Sales_Checklist"
    ws1.views.sheetView[0].showGridLines = True

    # 1. Banner
    ws1.merge_cells("A1:L1")
    title_cell = ws1["A1"]
    title_cell.value = f"CHIP MONG COMMERCIAL BANK (CMCB) — FIELD SALES TARGET MISSIONS [{week_label}]"
    title_cell.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color=brand_green, end_color=brand_green, fill_type="solid")
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[1].height = 32

    ws1.merge_cells("A2:L2")
    sub_cell = ws1["A2"]
    sub_cell.value = (
        "💡 INSTRUCTIONS: Missions are compact walk-in strike zones (Park Once, Sweep on Foot). "
        "Stores are sequenced linearly down the street to eliminate U-turns. Tap '📍 Open in Google Maps' on your phone to navigate."
    )
    sub_cell.font = Font(name="Calibri", size=9.5, italic=True, color="4A5568")
    sub_cell.fill = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")
    sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[2].height = 24

    headers1 = [
        "Mission ID & Strike Zone",
        "Sweep Stop",
        "Store Name",
        "Bakong ID / Acct",
        "Priority Tier",
        "Weekly Txns",
        "Current Bank",
        "District (Khan)",
        "1-Tap GPS Navigation",
        "Visit Status (Sales Action)",
        "Date Visited",
        "RM Field Notes & Feedback"
    ]

    for col_idx, h_text in enumerate(headers1, 1):
        cell = ws1.cell(row=3, column=col_idx, value=h_text)
        cell.font = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_green, end_color=dark_green, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
    ws1.row_dimensions[3].height = 30

    current_row = 4

    for m_idx, cluster in enumerate(clusters, 1):
        zone_title = cluster.get("title") or cluster.get("short_name") or f"Zone {m_idx}"
        district = cluster.get("district") or "Phnom Penh"
        raw_merchants = cluster.get("merchants", [])
        if not raw_merchants:
            continue

        # Linear sweep ordering down the street
        ordered_merchants = compute_corridor_linear_sweep(raw_merchants)

        # Calculate corridor length
        first_m = ordered_merchants[0]
        last_m = ordered_merchants[-1]
        dy = (float(first_m.get("latitude", 0)) - float(last_m.get("latitude", 0))) * 110574.0
        dx = (float(first_m.get("longitude", 0)) - float(last_m.get("longitude", 0))) * 108940.0
        corridor_len = math.sqrt(dx * dx + dy * dy)

        zone_header_text = f"MISSION {m_idx:02d}: {zone_title.upper()} ({len(ordered_merchants)} Stores • {cluster.get('total_volume', 0)} Weekly Txns)"

        for stop_num, m in enumerate(ordered_merchants, 1):
            txns = int(m.get("transaction_count", 0))
            tier_info = get_priority_tier(txns)
            lat = float(m.get("latitude", 0))
            lng = float(m.get("longitude", 0))
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lng:.6f}"

            is_even = (current_row % 2 == 0)
            row_fill_color = "F9FAFB" if is_even else "FFFFFF"
            row_fill = PatternFill(start_color=row_fill_color, end_color=row_fill_color, fill_type="solid")

            # Col A: Mission Zone
            c_zone = ws1.cell(row=current_row, column=1, value=f"Mission {m_idx:02d}: {zone_title}")
            c_zone.alignment = Alignment(horizontal="left", vertical="center")
            c_zone.font = Font(name="Calibri", size=10, bold=(stop_num == 1))

            # Col B: Stop #
            c_stop = ws1.cell(row=current_row, column=2, value=f"Stop {stop_num}")
            c_stop.alignment = Alignment(horizontal="center", vertical="center")
            c_stop.font = Font(name="Calibri", size=10, bold=True, color="1E3A8A")

            # Col C: Store Name
            c_name = ws1.cell(row=current_row, column=3, value=str(m.get("merchant_name") or "Store"))
            c_name.alignment = Alignment(horizontal="left", vertical="center")
            c_name.font = Font(name="Calibri", size=10.5, bold=True, color="111827")

            # Col D: Bakong ID
            c_id = ws1.cell(row=current_row, column=4, value=str(m.get("merchant_id") or "N/A"))
            c_id.alignment = Alignment(horizontal="left", vertical="center")
            c_id.font = Font(name="Consolas", size=9.5, color="4B5563")

            # Col E: Priority Tier
            c_tier = ws1.cell(row=current_row, column=5, value=tier_info["label"])
            c_tier.alignment = Alignment(horizontal="center", vertical="center")
            c_tier.font = Font(name="Calibri", size=9.5, bold=True, color=tier_info["color"])
            c_tier.fill = PatternFill(start_color=tier_info["fill"], end_color=tier_info["fill"], fill_type="solid")

            # Col F: Txns
            c_tx = ws1.cell(row=current_row, column=6, value=txns)
            c_tx.alignment = Alignment(horizontal="right", vertical="center")
            c_tx.font = Font(name="Calibri", size=10, bold=True)
            c_tx.number_format = "#,##0"

            # Col G: Current Bank
            c_bank = ws1.cell(row=current_row, column=7, value=str(m.get("bank_code") or "Other"))
            c_bank.alignment = Alignment(horizontal="center", vertical="center")
            c_bank.font = Font(name="Calibri", size=10)

            # Col H: District
            c_dist = ws1.cell(row=current_row, column=8, value=district)
            c_dist.alignment = Alignment(horizontal="left", vertical="center")
            c_dist.font = Font(name="Calibri", size=10)

            # Col I: Google Maps Hyperlink
            c_gps = ws1.cell(row=current_row, column=9, value="📍 Open Google Maps")
            c_gps.hyperlink = maps_url
            c_gps.alignment = Alignment(horizontal="center", vertical="center")
            c_gps.font = Font(name="Calibri", size=10, bold=True, color="1A73E8", underline="single")

            # Col J: Visit Status (Blank with dropdown)
            c_status = ws1.cell(row=current_row, column=10, value="")
            c_status.alignment = Alignment(horizontal="center", vertical="center")
            c_status.font = Font(name="Calibri", size=10)

            # Col K: Date Visited
            c_date = ws1.cell(row=current_row, column=11, value="")
            c_date.alignment = Alignment(horizontal="center", vertical="center")
            c_date.font = Font(name="Calibri", size=10)

            # Col L: Notes
            c_notes = ws1.cell(row=current_row, column=12, value="")
            c_notes.alignment = Alignment(horizontal="left", vertical="center")
            c_notes.font = Font(name="Calibri", size=10)

            for col_i in range(1, 13):
                cell_item = ws1.cell(row=current_row, column=col_i)
                cell_item.border = grid_border
                if col_i != 5:  # Preserve tier background
                    cell_item.fill = row_fill
            ws1.row_dimensions[current_row].height = 24
            current_row += 1

    # Add Dropdown Data Validation for Visit Status
    status_dv = DataValidation(
        type="list",
        formula1='"Converted, In Pipeline, Follow-up Needed, Gatekeeper Refused, Store Closed/Relocated"',
        allow_blank=True
    )
    status_dv.error = "Please select a valid visit status from the dropdown list."
    status_dv.errorTitle = "Invalid Status"
    status_dv.prompt = "Select field visit outcome"
    status_dv.promptTitle = "Visit Status"
    ws1.add_data_validation(status_dv)
    status_dv.add(f"J4:J{max(current_row, 10)}")

    # Freeze header rows
    ws1.freeze_panes = "A4"

    # =========================================================================
    # TAB 2: MANAGER ZONE SUMMARY
    # =========================================================================
    ws2 = wb.create_sheet(title="Manager_Zone_Summary")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:J1")
    m_title = ws2["A1"]
    m_title.value = f"CMCB FIELD SALES — CORRIDOR STRIKE MISSIONS SUMMARY [{week_label}]"
    m_title.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
    m_title.fill = PatternFill(start_color=brand_green, end_color=brand_green, fill_type="solid")
    m_title.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws2.row_dimensions[1].height = 32

    headers2 = [
        "Priority Rank",
        "Mission Strike Zone",
        "District (Khan)",
        "Target Stores",
        "Total Weekly Txns",
        "Avg Txns / Store",
        "Anchor Store (Top Txns)",
        "Center Coordinates",
        "1-Click Zone Map",
        "Assigned RM / Team"
    ]

    for col_idx, h_text in enumerate(headers2, 1):
        cell = ws2.cell(row=2, column=col_idx, value=h_text)
        cell.font = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color=dark_green, end_color=dark_green, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = header_border
    ws2.row_dimensions[2].height = 28

    sorted_clusters = sorted(clusters, key=lambda c: int(c.get("total_volume", 0)), reverse=True)

    for rank, cluster in enumerate(sorted_clusters, 1):
        r_num = rank + 2
        zone_title = cluster.get("title") or cluster.get("short_name") or f"Zone {rank}"
        district = cluster.get("district") or "Phnom Penh"
        merchants = cluster.get("merchants", [])
        store_count = len(merchants)
        total_vol = int(cluster.get("total_volume", 0))
        avg_vol = round(total_vol / max(store_count, 1), 1)

        c_lat = float(cluster.get("center_lat", 0))
        c_lng = float(cluster.get("center_lng", 0))
        zone_map_url = f"https://www.google.com/maps/search/?api=1&query={c_lat:.6f},{c_lng:.6f}"

        anchor_store = merchants[0].get("merchant_name") if merchants else "N/A"
        anchor_txns = merchants[0].get("transaction_count") if merchants else 0
        anchor_label = f"{anchor_store} ({anchor_txns} txns)"

        is_even = (r_num % 2 == 0)
        row_fill = PatternFill(start_color="F9FAFB" if is_even else "FFFFFF", end_color="F9FAFB" if is_even else "FFFFFF", fill_type="solid")

        # Rank
        c1 = ws2.cell(row=r_num, column=1, value=rank)
        c1.alignment = Alignment(horizontal="center", vertical="center")
        c1.font = Font(name="Calibri", size=10.5, bold=True, color="1E3A8A")

        # Zone
        c2 = ws2.cell(row=r_num, column=2, value=zone_title)
        c2.alignment = Alignment(horizontal="left", vertical="center")
        c2.font = Font(name="Calibri", size=10.5, bold=True, color="111827")

        # District
        c3 = ws2.cell(row=r_num, column=3, value=district)
        c3.alignment = Alignment(horizontal="left", vertical="center")

        # Stores
        c4 = ws2.cell(row=r_num, column=4, value=store_count)
        c4.alignment = Alignment(horizontal="right", vertical="center")
        c4.font = Font(name="Calibri", size=10, bold=True)
        c4.number_format = "#,##0"

        # Total Volume
        c5 = ws2.cell(row=r_num, column=5, value=total_vol)
        c5.alignment = Alignment(horizontal="right", vertical="center")
        c5.font = Font(name="Calibri", size=10.5, bold=True, color="006B3F")
        c5.number_format = "#,##0"

        # Avg Volume
        c6 = ws2.cell(row=r_num, column=6, value=avg_vol)
        c6.alignment = Alignment(horizontal="right", vertical="center")
        c6.number_format = "#,##0.0"

        # Anchor
        c7 = ws2.cell(row=r_num, column=7, value=anchor_label)
        c7.alignment = Alignment(horizontal="left", vertical="center")
        c7.font = Font(name="Calibri", size=10, bold=True)

        # GPS
        c8 = ws2.cell(row=r_num, column=8, value=f"{c_lat:.6f}, {c_lng:.6f}")
        c8.alignment = Alignment(horizontal="center", vertical="center")
        c8.font = Font(name="Consolas", size=9)

        # Map Link
        c9 = ws2.cell(row=r_num, column=9, value="🗺️ View Zone in Google Maps")
        c9.hyperlink = zone_map_url
        c9.alignment = Alignment(horizontal="center", vertical="center")
        c9.font = Font(name="Calibri", size=10, bold=True, color="1A73E8", underline="single")

        # Assigned RM
        c10 = ws2.cell(row=r_num, column=10, value="")
        c10.alignment = Alignment(horizontal="left", vertical="center")

        for col_i in range(1, 11):
            cell_item = ws2.cell(row=r_num, column=col_i)
            cell_item.border = grid_border
            cell_item.fill = row_fill

        ws2.row_dimensions[r_num].height = 24

    ws2.freeze_panes = "A3"

    # Auto-fit Column Widths on both sheets
    for ws in [ws1, ws2]:
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                if cell.row in [1, 2]:  # Skip banner rows
                    continue
                val_str = str(cell.value or "")
                if cell.hyperlink:
                    val_str = "Google Maps Link"
                max_len = max(max_len, len(val_str))
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 48)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)

    return wb
