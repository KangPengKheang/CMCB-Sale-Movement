"""Observed report submission times and intervals, independent of GPS verification."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean, median
from typing import Optional

ICT = timezone(timedelta(hours=7))


def iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def gap_seconds(previous: Optional[str], current: str):
    if not previous:
        return None
    return max(0, int((iso_datetime(current) - iso_datetime(previous)).total_seconds()))


def get_drop_rows(conn, day: str, sender_id: Optional[int] = None):
    params = []
    scope = ""
    if sender_id is not None:
        scope = "WHERE sender_id = ?"
        params.append(sender_id)
    params.append(day)
    return [
        dict(row) for row in conn.execute(
            f"""
            WITH sequence AS (
                SELECT *,
                    LAG(submitted_at) OVER (
                        PARTITION BY sender_id ORDER BY submitted_at, id
                    ) AS previous_drop_at,
                    LAG(local_date) OVER (
                        PARTITION BY sender_id ORDER BY submitted_at, id
                    ) AS previous_drop_date
                FROM sales_submissions {scope}
            )
            SELECT * FROM sequence WHERE local_date = ?
            ORDER BY submitted_at, id
            """, params,
        )
    ]


def decorate_drop(row, threshold_minutes=None):
    gap = gap_seconds(row["previous_drop_at"], row["submitted_at"])
    overnight = bool(row["previous_drop_date"] and row["previous_drop_date"] != row["local_date"])
    return {
        **row, "gap_seconds": gap, "overnight_gap": overnight,
        "above_threshold": bool(
            threshold_minutes and gap is not None and not overnight
            and gap > threshold_minutes * 60
        ),
    }


def interval_stats(drops):
    gaps = [
        drop["gap_seconds"] for drop in drops
        if drop["gap_seconds"] is not None and not drop["overnight_gap"]
    ]
    return {
        "interval_count": len(gaps),
        "average_gap_seconds": round(mean(gaps), 1) if gaps else None,
        "median_gap_seconds": round(median(gaps), 1) if gaps else None,
        "longest_gap_seconds": max(gaps) if gaps else None,
        "above_threshold_count": sum(drop["above_threshold"] for drop in drops),
    }


def classify_daily_starts(drops, day: str):
    """Classify first submissions, never inferred arrival or working time."""
    cutoff = datetime.fromisoformat(day + "T09:30:00").replace(tzinfo=ICT)
    first = {}
    for drop in drops:
        first.setdefault(drop["sender_id"], drop)
    earliest = min((iso_datetime(drop["submitted_at"]) for drop in first.values()), default=None)
    starts = {}
    early_birds = []
    for sender_id, drop in first.items():
        submitted = iso_datetime(drop["submitted_at"])
        late = submitted > cutoff
        champion = submitted == earliest and not late
        starts[sender_id] = {
            "first_drop_id": drop["id"],
            "first_drop_merchant_name": drop["merchant_name"],
            "start_status": "late_start" if late else "on_time",
            "is_early_bird": champion,
        }
        if champion:
            early_birds.append({
                "id": drop["id"], "sender_id": sender_id,
                "sender_name": drop["sender_name"], "submitted_at": drop["submitted_at"],
                "merchant_name": drop["merchant_name"], "has_gps": drop["has_gps"],
                "color": sender_color(sender_id),
            })
    early_birds.sort(key=lambda drop: drop["sender_id"])
    return starts, {
        "cutoff": "09:30", "timezone": "Asia/Phnom_Penh", "early_birds": early_birds,
        "late_start_count": sum(start["start_status"] == "late_start" for start in starts.values()),
        "on_time_count": sum(start["start_status"] == "on_time" for start in starts.values()),
    }


def activity_feed(conn, day: str, threshold_minutes=None, sender_id=None, limit=50, offset=0, late_only=False):
    drops = [decorate_drop(row, threshold_minutes) for row in get_drop_rows(conn, day)]
    starts, recognition = classify_daily_starts(drops, day)
    totals = defaultdict(int)
    for drop in drops:
        totals[drop["sender_id"]] += 1
    counters = defaultdict(int)
    entries = []
    for drop in drops:
        identity = drop["sender_id"]
        counters[identity] += 1
        if sender_id is not None and identity != sender_id:
            continue
        start = starts[identity]
        first = drop["id"] == start["first_drop_id"]
        if late_only and not (first and start["start_status"] == "late_start"):
            continue
        entries.append({
            **drop, "color": sender_color(identity), "drop_number": counters[identity],
            "daily_visit_count": totals[identity],
            "is_first_drop": first, "is_early_bird": first and start["is_early_bird"],
            "start_status": start["start_status"] if first else None,
        })
    entries.reverse()
    return {
        "date": day, "timezone": "Asia/Phnom_Penh", "sender_id": sender_id,
        "total": len(entries), "limit": limit, "offset": offset, "late_only": late_only,
        "has_more": offset + limit < len(entries),
        "entries": entries[offset:offset + limit],
        "recognition": recognition,
    }


def activity_overview(conn, day: str, threshold_minutes=None):
    drops = [decorate_drop(row, threshold_minutes) for row in get_drop_rows(conn, day)]
    starts, recognition = classify_daily_starts(drops, day)
    groups = defaultdict(list)
    channels = {}
    hours = [0] * 24
    for drop in drops:
        groups[drop["sender_id"]].append(drop)
        channel = (drop["source_channel"] or "").strip()
        bucket = channels.setdefault(channel, {"senders": set(), "drop_count": 0})
        bucket["senders"].add(drop["sender_id"])
        bucket["drop_count"] += 1
        hours[iso_datetime(drop["submitted_at"]).astimezone(ICT).hour] += 1
    directory = conn.execute(
        """
        SELECT sender_id, MAX(submitted_at) AS last_drop_at
        FROM sales_submissions GROUP BY sender_id
        """
    ).fetchall()
    senders = []
    for sender in directory:
        sender_id = sender["sender_id"]
        identity = conn.execute(
            "SELECT sender_name FROM sales_submissions WHERE sender_id=? "
            "ORDER BY submitted_at DESC,id DESC LIMIT 1", (sender_id,),
        ).fetchone()
        own = groups.get(sender_id, [])
        senders.append({
            "sender_id": sender_id, "sender_name": identity["sender_name"],
            "color": sender_color(sender_id),
            **starts.get(sender_id, {
                "first_drop_id": None, "first_drop_merchant_name": None,
                "start_status": "no_drop", "is_early_bird": False,
            }),
            "channels": sorted({(drop["source_channel"] or "").strip() for drop in own}),
            "drop_times": [drop["submitted_at"] for drop in own],
            "drop_count": len(own), "gps_count": sum(drop["has_gps"] for drop in own),
            "missing_gps_count": sum(not drop["has_gps"] for drop in own),
            "photo_count": sum(drop["has_image"] for drop in own),
            "first_drop_at": own[0]["submitted_at"] if own else None,
            "last_drop_at": own[-1]["submitted_at"] if own else None,
            "last_drop_merchant_name": own[-1]["merchant_name"] if own else None,
            "last_drop_has_gps": bool(own[-1]["has_gps"]) if own else False,
            "last_gap_seconds": own[-1]["gap_seconds"] if own else None,
            "last_gap_overnight": own[-1]["overnight_gap"] if own else False,
            "latest_observed_drop_at": sender["last_drop_at"],
            **interval_stats(own),
        })
    senders.sort(key=lambda sender: (-sender["drop_count"], sender["sender_name"], sender["sender_id"]))
    dates = [row[0] for row in conn.execute(
        "SELECT DISTINCT local_date FROM sales_submissions ORDER BY local_date DESC"
    )]
    today = datetime.now(ICT).date().isoformat()
    return {
        "date": day, "today": today, "timezone": "Asia/Phnom_Penh",
        "latest_report_date": dates[0] if dates else None,
        "available_dates": dates,
        "threshold_minutes": threshold_minutes, "recognition": recognition,
        "summary": {
            "drop_count": len(drops), "active_senders": len(groups),
            "observed_senders": len(senders), "missing_gps_count": sum(not d["has_gps"] for d in drops),
            **interval_stats(drops),
        },
        "channels": [
            {"name": name, "sender_count": len(bucket["senders"]), "drop_count": bucket["drop_count"]}
            for name, bucket in sorted(channels.items(), key=lambda item: item[0].casefold())
        ],
        "hourly": [{"hour": hour, "drop_count": count} for hour, count in enumerate(hours)],
        "senders": senders,
    }


def sender_activity(conn, sender_id: int, day: str, threshold_minutes=None, limit=100, offset=0):
    drops = [decorate_drop(row, threshold_minutes) for row in get_drop_rows(conn, day, sender_id)]
    history_start = (date.fromisoformat(day) - timedelta(days=13)).isoformat()
    counts = dict(conn.execute(
        "SELECT local_date,COUNT(*) FROM sales_submissions "
        "WHERE sender_id=? AND local_date BETWEEN ? AND ? GROUP BY local_date",
        (sender_id, history_start, day),
    ).fetchall())
    history = []
    for index in range(14):
        history_day = (date.fromisoformat(history_start) + timedelta(days=index)).isoformat()
        history.append({"date": history_day, "drop_count": counts.get(history_day, 0)})
    return {
        "sender_id": sender_id, "date": day, "total": len(drops),
        "limit": limit, "offset": offset,
        "has_more": offset + limit < len(drops),
        "drops": drops[offset:offset + limit],
        "daily_history": history, **interval_stats(drops),
    }



def sender_color(sender_id: int) -> str:
    """A stable color follows a sender across dates, roster order, and views."""
    import colorsys
    import hashlib
    digest = hashlib.sha256(str(sender_id).encode("ascii")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65536
    saturation = 0.65 + digest[2] / 255 * 0.15
    lightness = 0.38 + digest[3] / 255 * 0.10
    channels = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in channels)


def straight_line_distance_meters(first, second) -> float:
    import math
    lat1, lat2 = math.radians(first["latitude"]), math.radians(second["latitude"])
    dlat = lat2 - lat1
    dlng = math.radians(second["longitude"] - first["longitude"])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return round(6371000 * 2 * math.asin(min(1, math.sqrt(value))), 1)


def movement_routes(conn, day: str, sender_id: Optional[int] = None):
    params = [day]
    sender_filter = ""
    if sender_id is not None:
        sender_filter = " AND sender_id=?"
        params.append(sender_id)
    rows = conn.execute(
        f"""
        SELECT id,sender_id,sender_name,submitted_at,merchant_name,latitude,longitude,has_gps
        FROM sales_submissions WHERE local_date=? {sender_filter}
        ORDER BY submitted_at,id
        """, params,
    ).fetchall()
    groups = {}
    gps_count = 0
    for row in rows:
        identity = row["sender_id"]
        if identity not in groups:
            groups[identity] = {
                "sender_id": identity, "sender_name": row["sender_name"],
                "color": sender_color(identity), "drop_count": 0,
                "missing_gps_count": 0, "points": [], "segments": [],
            }
        track = groups[identity]
        track["sender_name"] = row["sender_name"]
        track["drop_count"] += 1
        if not row["has_gps"] or row["latitude"] is None or row["longitude"] is None:
            track["missing_gps_count"] += 1
            continue
        point = {
            "id": row["id"], "drop_number": track["drop_count"],
            "submitted_at": row["submitted_at"], "merchant_name": row["merchant_name"],
            "latitude": row["latitude"], "longitude": row["longitude"],
        }
        if track["points"]:
            previous = track["points"][-1]
            track["segments"].append({
                "from_id": previous["id"], "to_id": point["id"],
                "from_drop_number": previous["drop_number"], "to_drop_number": point["drop_number"],
                "from_time": previous["submitted_at"], "to_time": point["submitted_at"],
                "gap_seconds": gap_seconds(previous["submitted_at"], point["submitted_at"]),
                "missing_gps_between": point["drop_number"] - previous["drop_number"] - 1,
                "distance_meters": straight_line_distance_meters(previous, point),
            })
        track["points"].append(point)
        gps_count += 1
    tracks = [track for track in groups.values() if track["points"]]
    tracks.sort(key=lambda track: (track["sender_name"], track["sender_id"]))
    return {
        "date": day, "timezone": "Asia/Phnom_Penh",
        "gps_drop_count": gps_count, "drop_count": len(rows),
        "missing_gps_count": len(rows) - gps_count,
        "sender_count": len(tracks), "tracks": tracks,
    }

def drop_detail(conn, drop_id: int):
    """Return this submission's details, never the merchant's latest aggregated visit."""
    submission = conn.execute(
        "SELECT id,sender_id,sender_name,submitted_at,local_date,merchant_name,business,"
        "source_channel,latitude,longitude,has_gps FROM sales_submissions WHERE id=?",
        (drop_id,),
    ).fetchone()
    if submission is None:
        return None
    fields = ("tel", "bank", "amount", "interest", "loan_type", "maturity", "status")
    report = conn.execute(
        "SELECT " + ",".join(fields) + " FROM merchant_reports WHERE id=?", (drop_id,)
    ).fetchone()
    return {**dict(submission), **{field: report[field] if report else None for field in fields},
            "report_available": report is not None}
