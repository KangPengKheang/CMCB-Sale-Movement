# CMCB Market Improvement Platform (Monorepo)

Automated retail merchant visit ingestion, validation, geospatial intelligence, and executive analytics platform for **Chip Mong Commercial Bank (CMCB)**.

The backend now reads the **retail_data Google Sheets tab** and refreshes its local
dashboard cache automatically. See [Google Sheets setup](backend/GOOGLE_SHEETS.md)
for configuration, private-sheet access, validation rules, and switching back to Telegram.

---

## 📁 Repository Structure

```text
.
├── Dockerfile                  # Multi-stage production build recipe
├── .dockerignore               # Build context exclusions
├── .gitignore                  # Git tracking rules
├── backend/                    # FastAPI Ingestion Engine & REST API
│   ├── src/market_bot/         # Core scraper, parser, correlation engine & API routes
│   ├── data/                   # SQLite database & district boundary maps
│   ├── scripts/                # Database migrations & Excel exporters
│   ├── tests/                  # Pytest test suite
│   ├── requirements.txt        # Pinned Python dependencies
│   └── run.py                  # Backend server entrypoint
└── frontend/                   # Modern React + Vite Dashboard
    ├── src/                    # Dashboard views (Coverage, Store Map, RM Performance, Data Explorer)
    ├── public/                 # Brand assets & icons (CMCB Logo)
    └── package.json            # Frontend dependencies
```

---

## 🚀 Quick Start (Local Development)

### 1. Run Backend
```bash
cd backend
python -m pip install -r requirements.txt
# Configure the Users worksheet and a unique AUTH_SECRET_KEY; see backend/GOOGLE_SHEETS.md
python run.py --host 127.0.0.1 --port 8000
```
API Documentation available at: `http://localhost:8000/docs`

Sign in using only the unique password from an active **Users** worksheet account.
`allowed_sources` controls accessible report channels throughout the dashboard and API;
`All` grants every source. Both dashboard and Field Sales views require this login.
For private credentials and reports, restrict workbook sharing and configure read-only
service-account access as described in [Google Sheets setup](backend/GOOGLE_SHEETS.md).

### 2. Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard available at: `http://localhost:5174`

---

## 🐳 Production Single-Image Docker Build

Build both frontend and backend into a single container:

```bash
# 1. Generate Harbor tag from Git branch & commit SHA
TAG="$(git rev-parse --abbrev-ref HEAD)-$(git rev-parse --short HEAD)"

# 2. Build image
docker build -t <harbor-url>/<project>/cmcb-market-insights:${TAG} .

# 3. Push to Harbor
docker push <harbor-url>/<project>/cmcb-market-insights:${TAG}
```
