# CMCB Market Improvement Google Sheets & FastAPI Backend

The active visit source is now **Google Sheets retail_data**, refreshed automatically
into a separate SQLite query cache. See [GOOGLE_SHEETS.md](GOOGLE_SHEETS.md) for setup.
Authentication uses the **Users** worksheet, with role/is_active checks and server-side
allowed_sources filtering. See the Users-sheet login section in [GOOGLE_SHEETS.md](GOOGLE_SHEETS.md).

The Telegram ingestion documentation below applies when VISIT_DATA_SOURCE=telegram.

Automated ingestion, validation, and geospatial correlation engine for retail merchant visit reports submitted by sales teams via Telegram. 

Extracts structured merchant data, normalizes banking/contact details, performs asynchronous GPS coordinate pairing, classifies Phnom Penh administrative districts, and exposes REST API endpoints for analytics and interactive mapping.

> 📖 **For detailed architecture, offline queue behavior, and data flow explanations, see [`ARCHITECTURE.md`](ARCHITECTURE.md).**

---

## 📌 Architecture

```text
[Sales Rep Posts in Telegram Group]
       │
       ▼ (HTTP Long Polling: Outbound HTTPS to api.telegram.org)
[Async Telegram Bot Client (clients/telegram.py)]
       │
       ▼ Level 1: Ingestion & Audit Log
[Raw Updates Log (data/captured_updates.jsonl)]
       │
       ▼ Level 2: Correlation Engine (core/engine.py)
 ├── 14-Key Form Regex Parser (core/parser.py)
 ├── Phone, Business & Status Normalizers
 ├── Asynchronous GPS Pairing (Sliding Window +/- 15 mins)
 ├── Multi-Photo Album Bundling (photo_count)
 └── Ray-Casting Spatial District Classification (Phnom Penh Khans)
       │
       ▼ Level 3: SQLite Persistence (db/storage.py)
 ├── merchant_reports (Verified visits with exact GPS)
 ├── dead_letter_queue (Real errors: missing GPS pins, unparsed text)
 └── sync_state (Checkpoint tracking)
       │
       ▼ Level 4: FastAPI REST Layer (api/)
 ├── GET /api/reports       ──> Filterable merchant list
 ├── GET /api/reports/stats ──> Real-time operational KPIs
 ├── GET /api/reports/dlq   ──> Quarantined compliance items
 └── GET /api/map/geojson   ──> Leaflet / Google Maps FeatureCollection
```

---

## 🚀 Key Features

* **Zero-Infrastructure Long Polling**: Uses standard Telegram **HTTP Long Polling** via `httpx`. No public IP, domain, or open firewall ports required for local hosting.
* **14-Field Form Extraction**: Parses the standardized retail report template:
  `Name`, `Tel`, `Business`, `Purpose`, `Bank`, `Amount`, `Interest`, `Loan Type`, `Tenure`, `Maturity`, `Status`, `Potential H/M/L`, `Potential Product`, `Remark`.
* **Asynchronous GPS Correlation**: Correlates the photo report and GPS map pin regardless of which message arrives first, supporting delayed pins (up to 15 minutes).
* **Multi-Photo Album Bundling**: Automatically detects Telegram photo albums (`media_group_id`) and groups supporting storefront/counter photos into `photo_count` rather than dumping them into errors.
* **Clean Dead-Letter Queue (DLQ)**: Quarantines genuine sales rep compliance errors (e.g. submitting a form but forgetting to pin GPS location).
* **Edit-Aware (`edited_message`)**: When a salesperson fixes a typo in their merchant name or phone number, the engine updates the record in-place.
* **Spatial District Classification**: Uses a pure-Python ray-casting point-in-polygon engine against Phnom Penh district boundaries to tag Khan names (*Sen Sok*, *Russey Keo*, *Mean Chey*, etc.).
* **Test & Production Isolation**: Supports `ENVIRONMENT=test` (writes to `market_reports_test.db`) and `ENVIRONMENT=production` (writes to `market_reports.db`).

---

## 📁 Repository Structure

```text
.
├── src/
│   └── market_bot/
│       ├── __init__.py
│       ├── config.py           # Typed settings & environment loading
│       ├── app.py              # FastAPI application factory & lifespan poller
│       ├── core/
│       │   ├── parser.py       # 14-field form parser & data normalizers
│       │   └── engine.py       # Asynchronous photo + location pairing state machine
│       ├── db/
│       │   ├── models.py       # Pydantic REST schemas & record dataclasses
│       │   └── storage.py      # SQLite connection manager & query helpers
│       ├── clients/
│       │   └── telegram.py     # Async HTTP Long Polling client (httpx)
│       └── api/
│           ├── routes_reports.py # REST endpoints: /api/reports, /api/reports/stats
│           └── routes_map.py   # REST endpoints: /api/map/geojson, /api/map/khan-stats
├── data/
│   ├── boundaries/             # Phnom Penh district GeoJSON boundary data
│   └── backups/                # Production database backups
├── scripts/
│   ├── inspect_db.py           # CLI inspection tool for test/production databases
│   └── export_map.py           # Export SQLite records to frontend JSON format
├── tests/
│   ├── test_parser.py          # Unit tests for 14-field form regex & edge cases
│   └── test_engine.py          # Unit tests for async pairing state machine
├── pyproject.toml              # Build system & package specification
├── requirements.txt            # Pinned Python dependencies
├── run.py                      # FastAPI server CLI runner
├── .env.example                # Configuration template
└── .gitignore                  # Git rules protecting secrets and databases
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.9+ installed
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Clone & Create Virtual Environment
```bash
git clone <your-repo-url>
cd market-bot-backend

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```ini
TELEGRAM_BOT_API=1234567890:ABCdefGhIJKlmNoPQRstuVWXyz
TARGET_CHAT_ID=-1001234567890
ENVIRONMENT=test
CORRELATION_WINDOW_SECONDS=900
```

---

## 🏃 Running the Application

### Start the FastAPI Server & Polling Worker
```bash
python run.py --port 8000
```

* **Interactive Swagger API Docs**: `http://localhost:8000/docs`
* **Health Check**: `http://localhost:8000/`

---

## 📊 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service health, active environment mode, and database target. |
| `GET` | `/api/merchants` | List unique merchants with aggregated visit counts and status filters. |
| `GET` | `/api/merchants/{id}` | Detailed merchant profile + full chronological **Visit History Timeline**. |
| `GET` | `/api/rms` | List all Sales Reps (RMs) ranked by performance (`visits`, `onboarded`, `conversion_rate`, `velocity`). |
| `GET` | `/api/rms/{id}` | Detailed RM profile: lifetime KPIs, conversion rate, territory & sector breakdown. |
| `GET` | `/api/rms/{id}/habits` | Deep-dive territory focus (`top_districts`) and category specializations (`top_categories`). |
| `GET` | `/api/rms/{id}/visits` | Chronological visit feed logged by a specific RM. |
| `GET` | `/api/reports` | List all verified individual visits (Supports filters: `khan`, `stage`, `sender`, `limit`, `offset`). |
| `GET` | `/api/reports/{id}` | Retrieve details for a single visit report by ID. |
| `GET` | `/api/reports/stats` | Live operational KPIs (Total visits, stores, deployed count, pipeline, cold zones). |
| `GET` | `/api/reports/dlq` | List quarantined Dead-Letter Queue items (unmatched forms, orphaned pins). |
| `GET` | `/api/reports/export/excel` | Download all verified visits as a formatted Excel workbook (`.xlsx`). |
| `GET` | `/api/map/geojson` | Returns all visit points as a GeoJSON `FeatureCollection`. |
| `GET` | `/api/map/merchants-geojson`| Returns unique merchant points as a GeoJSON `FeatureCollection`. |
| `GET` | `/api/map/khan-stats` | Visit density counts and cold-zone status per Phnom Penh district. |
---

## 🧪 Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 🗄️ CLI Utilities

* **Inspect Database Metrics**:
  ```bash
  python scripts/inspect_db.py --test   # Inspect test database
  python scripts/inspect_db.py --prod   # Inspect production database
  ```
* **Export Map Data**:
  ```bash
  python scripts/export_map.py --test   # Export test data to JSON
  python scripts/export_map.py --prod   # Export production data to JSON
  ```
