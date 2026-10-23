"""Weekly and daily case-drop counts from the caller's scoped submissions."""
from datetime import date, datetime, timedelta

from .activity import ICT, sender_color


def activity_calendar(conn, today=None):
    today = today or datetime.now(ICT).date()
    first_day = today - timedelta(days=29)
    monday = today - timedelta(days=today.weekday())
    days = [(first_day + timedelta(days=index)).isoformat() for index in range(30)]
    weeks = [
        {
            "start": (monday - timedelta(weeks=index)).isoformat(),
            "end": (monday - timedelta(weeks=index) + timedelta(days=6)).isoformat(),
            "label": "This week" if index == 0 else ("Last week" if index == 1 else f"{index} weeks ago"),
            "current": index == 0,
        }
        for index in range(4)
    ]
    # Both periods are anchored to today, even when the latest sheet row is historical.
    # Group in SQL so the response size depends on people and dates, not report volume.
    grouped = conn.execute(
        """SELECT sender_id, local_date, COUNT(*) AS cases
           FROM sales_submissions WHERE local_date BETWEEN ? AND ?
           GROUP BY sender_id, local_date""",
        (first_day.isoformat(), today.isoformat()),
    ).fetchall()
    counts = {}
    for record in grouped:
        counts.setdefault(record["sender_id"], {})[record["local_date"]] = record["cases"]
    roster = conn.execute(
        """SELECT sender_id, sender_name FROM (
               SELECT sender_id, sender_name,
                      ROW_NUMBER() OVER (PARTITION BY sender_id ORDER BY submitted_at DESC, id DESC) AS position
               FROM sales_submissions WHERE local_date <= ?
           ) WHERE position = 1""",
        (today.isoformat(),),
    ).fetchall()
    senders = []
    for person in roster:
        identity = person["sender_id"]
        own = counts.get(identity, {})
        daily = [own.get(day, 0) for day in days]
        weekly = [
            sum(total for day, total in own.items() if week["start"] <= day <= min(week["end"], today.isoformat()))
            for week in weeks
        ]
        senders.append({
            "sender_id": identity, "sender_name": person["sender_name"],
            "color": sender_color(identity), "daily_counts": daily, "weekly_counts": weekly,
            "total_cases": sum(daily), "active_days": sum(count > 0 for count in daily),
        })
    senders.sort(key=lambda person: (-person["total_cases"], person["sender_name"].casefold(), person["sender_id"]))
    return {
        "today": today.isoformat(), "timezone": "Asia/Phnom_Penh",
        "days": days, "weeks": weeks, "senders": senders,
    }
