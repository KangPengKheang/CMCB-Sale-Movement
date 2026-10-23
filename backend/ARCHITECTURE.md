# CMCB Market Improvement Bot — Architecture & Ingestion Guide

The default visit source is now Google Sheets. See [GOOGLE_SHEETS.md](GOOGLE_SHEETS.md)
for the current refresh and cache architecture. The Telegram ingestion guide below
describes the optional VISIT_DATA_SOURCE=telegram mode.

This document explains the technical architecture, long-polling behavior, offline queue catch-up, asynchronous GPS correlation, and local data flow of the backend system.

---

## 📌 Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Why We Don't Need Delays (Local SQLite vs. Remote APIs)](#2-why-we-dont-need-delays-local-sqlite-vs-remote-apis)
3. [How Offline Catch-Up Works (The 24-Hour Queue)](#3-how-offline-catch-up-works-the-24-hour-queue)
4. [Asynchronous Pairing & Correlation Engine](#4-asynchronous-pairing--correlation-engine)
5. [In-Place Message Edits (Zero Duplicates)](#5-in-place-message-edits-zero-duplicates)
6. [Photo Album Bundling & Clean DLQ](#6-photo-album-bundling--clean-dlq)
7. [Frontend Connection (FastAPI REST API)](#7-frontend-connection-fastapi-rest-api)
8. [Operations & Environment Modes](#8-operations--environment-modes)

---

## 1. System Architecture Overview

```text
[Sales Rep Posts in Telegram Company Group]
       │
       ▼ (Long Polling: Outbound HTTPS to api.telegram.org)
[Async Telegram Bot Client (clients/telegram.py)]
       │
       ▼ Level 1: Audit Archive
[data/captured_updates.jsonl (Raw Telegram Payloads)]
       │
       ▼ Level 2: Correlation Engine (core/engine.py)
 ├── 14-Key Form Regex Parser (core/parser.py)
 ├── Phone, Business & Status Normalizers
 ├── Asynchronous GPS Pairing (Sliding Window +/- 15 mins)
 ├── Multi-Photo Album Bundling (photo_count)
 └── Ray-Casting Spatial District Classification (Phnom Penh Khans)
       │
       ▼ Level 3: SQLite Persistence (db/storage.py)
 ├── merchant_reports (Verified visits with exact coordinates)
 ├── dead_letter_queue (Real errors: missing GPS pins, unparsed text)
 └── sync_state (Tracking checkpoint)
       │
       ▼ Level 4: FastAPI REST Layer (api/)
 ├── GET /api/reports       ──> Filterable merchant list
 ├── GET /api/reports/stats ──> Live operational KPIs
 ├── GET /api/reports/dlq   ──> Quarantined compliance items
 └── GET /api/map/geojson   ──> Leaflet / Google Maps FeatureCollection
```

---

## 2. Why We Don't Need Delays (Local SQLite vs. Remote APIs)

In systems syncing to remote third-party APIs (such as Google Sheets), write delays are required because:
* Google Sheets enforces strict rate limits (60 write requests per minute per project).
* Writing immediately on every keystroke causes quota exhaustion and row-locking conflicts.

### Our Architecture (Zero-Delay Local Persistence):
* **Direct SQLite Writes**: Writing to local SQLite takes **under 1 millisecond**.
* **Zero Quotas**: There are no third-party rate limits, quotas, or cloud service fees.
* **Immediate Availability**: As soon as a photo form and GPS pin are paired, the visit is saved and instantly accessible to the REST API and map.

---

## 3. How Offline Catch-Up Works (The 24-Hour Queue)

Telegram’s official Bot API servers maintain an internal backlog queue of all updates sent to your group for **up to 24 hours**.

```text
[10:00 AM] Sales Rep posts visit form + GPS pin in group.
           (Your backend server is offline / turned off)
                  │
                  ▼
[Telegram Cloud Servers] ──> Holds messages in your Bot's queue (up to 24h).
                  │
                  │ (4 hours later...)
                  ▼
[2:00 PM]  You start your backend: 'python run.py --port 8000'
                  │
                  ▼
[Your Bot Client] ──────────> Calls getUpdates(offset=None)
                  │
                  ▼
[Telegram Delivers Backlog] ─> All messages sent between 10:00 AM and 2:00 PM
                               arrive chronologically in sequence.
```

### Why Timestamps Stay Accurate:
* When calculating whether a photo and GPS pin belong together, the engine uses the **message creation timestamp recorded by Telegram (`msg.date`)**, not your local computer's clock.
* Even if your bot starts 5 hours late, it sees that the photo was sent at `10:00:00` and the GPS pin at `10:00:15` ($\Delta t = 15\text{s} \le 15\text{ mins}$).
* The pair matches and records with its original visit time.

---

## 4. Asynchronous Pairing & Correlation Engine

Sales reps do not always send their messages in the exact same order. The correlation engine handles three real-world transmission patterns:

### Scenario A: Standard Sequence (Photo First $\rightarrow$ Location Second)
1. Salesperson sends a photo album with the 14-field report on Photo #1.
2. The engine parses the form, checks for an existing location from that sender, finds none, and places the form in the `pending_events` table.
3. 10 seconds later, the rep pins their GPS location.
4. The engine checks `pending_events`, finds the matching form, calculates distance/time, tags the Phnom Penh Khan, and moves the complete record into `merchant_reports`.

### Scenario B: Reverse Sequence (Location First $\rightarrow$ Photo Second)
1. Salesperson pins their GPS location upon arriving at the shop.
2. The location is buffered in `pending_events`.
3. 2 minutes later, the rep takes photos and sends the 14-key caption.
4. The engine finds the buffered location, pairs them, and saves the report.

### Scenario C: Concurrent Senders
* When two sales reps (e.g. *Liza Soy* and *Sreyphim Nuth*) post at the exact same minute, their messages arrive interleaved.
* Because the buffer indexes events by **`sender_id`**, Liza's GPS pin will only pair with Liza's report, and Sreyphim's pin will only pair with Sreyphim's report.

---

## 5. In-Place Message Edits (Zero Duplicates)

If a sales rep notices a typo in the merchant name, telephone, or status and edits their message in Telegram:

1. Telegram issues an **`edited_message`** update with the original `message_id`.
2. The engine re-parses the updated text and normalizes the fields.
3. It performs an atomic `INSERT OR REPLACE` (UPSERT) keyed on `form_msg_id`.
4. **Outcome**: The existing database row is updated in-place without creating duplicate visit entries.

---

## 6. Photo Album Bundling & Clean DLQ

### Album Handling:
* When multiple photos are sent as an album (`media_group_id`), Photo #1 carries the text form, while Photos #2, #3, and #4 are blank.
* The engine groups all photos in the album into `photo_count` (e.g. `3`) and records their IDs (`photo_msg_ids`) directly on the report row.

### Clean Dead-Letter Queue (DLQ):
Supporting photos are **not** treated as errors. The `dead_letter_queue` table is strictly reserved for genuine compliance failures:
* **`unmatched_report`**: Sales rep submitted text but forgot the GPS pin after 15 minutes.
* **`orphaned_location`**: GPS pin sent with no accompanying visit description.
* **`chatter`**: Non-report conversation or stickers.
* **`orphaned_photo`**: Standalone photo sent with no report anywhere near it.

---

## 7. Frontend Connection (FastAPI REST API)

The React frontend (`khqr-map`) connects directly to the FastAPI endpoints:

```text
[React Frontend Map (khqr-map)]
       │
       ▼ (HTTP GET /api/map/geojson)
[FastAPI Backend Server (:8000)]
       │
       ▼ (Reads SQLite in < 1ms)
[data/market_reports.db]
```

### Key API Endpoints:
* **`GET /api/reports`**: Filter reports by `khan`, `stage`, `sender`, `limit`, and `offset`.
* **`GET /api/reports/stats`**: Live operational metrics (Total visits, deployed count, pipeline, cold zones).
* **`GET /api/reports/dlq`**: List compliance errors.
* **`GET /api/map/geojson`**: Standard GeoJSON FeatureCollection for Leaflet / Google Maps.
* **`GET /api/map/khan-stats`**: Territory coverage breakdown across all 14 Phnom Penh Khans.

---

## 8. Operations & Environment Modes

### Switching Environments:
Controlled via `backend/.env`:

* **Testing Mode (`ENVIRONMENT=test`)**:
  * Reads/writes to `data/market_reports_test.db`.
  * Allows testing with your test bot without modifying real data.
* **Production Mode (`ENVIRONMENT=production`)**:
  * Reads/writes to `data/market_reports.db` (containing your verified production records).

### Essential Commands:
```bash
# Start the Backend & Polling Engine
python run.py --port 8000

# Inspect Database Records & DLQ
python scripts/inspect_db.py --test   # Inspect test database
python scripts/inspect_db.py --prod   # Inspect production database

# Export SQLite Data to Map JSON
python scripts/export_map.py --test
python scripts/export_map.py --prod

# Run Automated Test Suite
python -m unittest discover -s tests -p "test_*.py" -v
```
