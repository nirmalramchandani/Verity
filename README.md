# 🐋 Verity — Smart Money Detector & Analyst (SMDA)

A full-stack, AI-powered platform that tracks **institutional "whale" investor activity** in Indian equity markets, generates high-conviction buy/sell signals, and delivers actionable intelligence through a dual-portal dashboard.

> New to the project? [**Read the Concept & Philosophy doc →**](./CONCEPT.md) for the idea behind Verity — the "Digital Twin," the Truth Ledger, and how the Signal Engine thinks — before diving into setup and code.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [Data Pipeline](#data-pipeline)
- [Signal Engine](#signal-engine)
- [API Reference](#api-reference)
- [Deployment](#deployment)

---

## Overview

Verity ingests bulk-deal transaction data from Indian stock exchanges — 13,000+ transactions per session — runs it through a multi-phase cleaning and ingestion pipeline, and applies a proprietary **Signal Engine** to detect high-conviction trade patterns from institutional investors (whales).

The system surfaces two things:
1. **Who** the smart money is — ranked investor profiles with hit ratios, sector exposure, and portfolio snapshots.
2. **What** they're doing right now — real-time BUY/SELL signals with confidence scores, strategy breakdowns, and AI-generated summaries.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│   ┌──────────────────┐        ┌──────────────────────────┐  │
│   │  Admin Portal    │        │     User Portal          │  │
│   │  (frontend_admin)│        │     (frontend_user)      │  │
│   │  Vite + React    │        │     Vite + React         │  │
│   │  Pipeline mgmt   │        │  Signal Command Center   │  │
│   │  Data viewer     │        │  Whale Scanner & Profiles│  │
│   └────────┬─────────┘        └────────────┬─────────────┘  │
└────────────┼─────────────────────────────  │ ───────────────┘
             │                               │
             └──────────────┬────────────────┘
                            │ REST API / SSE
                    ┌───────▼────────┐
                    │  FastAPI (BE)  │
                    │  Verity API    │
                    └───────┬────────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
     ┌───────▼──────┐ ┌─────▼──────┐ ┌───▼──────────────┐
     │  Data Pipeline│ │Signal Engine│ │  AI Contextualist│
     │  Phase 1+2   │ │Strategies  │ │  (LangChain+     │
     │  Clean+Ingest│ │Orchestrator│ │   Tavily+OpenAI) │
     └───────┬──────┘ └─────┬──────┘ └──────────────────┘
             │              │
     ┌───────▼──────────────▼──────┐
     │         Databases           │
     │  MongoDB (investor profiles)│
     │  PostgreSQL (transactions,  │
     │  snapshots, sell records)   │
     └─────────────────────────────┘
```

---

## Features

### 🔄 Data Pipeline (Admin)
- **Phase 1 – Clean**: Upload single or batch bulk-deal CSVs; validates, normalises, deduplicates, filters intraday pairs, and applies investor/symbol alias mappings. Streams live progress via Server-Sent Events (SSE).
- **Phase 2 – Ingest**: FIFO lot-matching engine replays the full transaction timeline row-by-row, applies corporate-action adjustments (splits, bonuses), updates open lots, and flushes all data to MongoDB + PostgreSQL. Supports pause/resume with SHA-256 file-hash checkpointing.
- **AI Scoring**: After ingestion, a scoring engine computes Smart Money Scores for every investor based on hit ratio, return magnitude, holding duration, and sector diversity.

### 🧠 Signal Engine
Four concurrent strategies evaluate every new bulk-deal transaction:

| Strategy | What It Detects |
|---|---|
| **Institutional Herding** | Multiple independent whales entering the same stock within 14 days, weighted by their historical hit ratios |
| **Whale Conviction** | A whale averaging-up (buying more at >5% premium to their weighted average price) |
| **Relative Volume Intensity** | Deal value >5× the stock's median deal size, or >10% of 30-day average daily volume |
| **Whale Exit** | High-hit-ratio whales liquidating a position — a high-conviction SELL signal |

Strategies run concurrently, scores are weighted and aggregated, and a consensus filter assigns a confidence label: **SPECULATIVE → MODERATE → HIGH → CRITICAL**.

### 📊 User-Facing Dashboards
- **Signal Command Center** — live feed of high-conviction BUY/SELL signals with strategy breakdowns
- **Whale Scanner** — leaderboard of top institutional investors ranked by Smart Money Score
- **Whale Profiles** — deep-dive into any investor: holdings, hit ratio, sector exposure, PnL history
- **Herd Radar** — visualise clustering events across stocks
- **Alpha Table** — sortable table of all tracked signals
- **Live Activity** — real-time transaction feed for the latest trading day

### 🔔 Alerting
- Email alerts (Gmail SMTP) for pipeline crashes and ingestion completion
- Telegram bot notifications for signal dispatch and system health
- Dashboard URL embedded in alerts for one-click access

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, FastAPI, Uvicorn/Gunicorn |
| **Data processing** | Pandas, PyArrow (Parquet) |
| **Databases** | MongoDB (Atlas), PostgreSQL |
| **AI / RAG** | LangChain-OpenAI, Tavily (web search) |
| **Frontend** | React 19, Vite 8, React Router 7, Recharts |
| **Deployment** | Render (backend), Vercel (frontends) |

---

## Project Structure

```
Verity/
├── backend/
│   ├── api/
│   │   ├── app.py            # FastAPI application & middleware
│   │   └── routes.py         # All REST API endpoints
│   ├── pipeline/
│   │   ├── runner.py         # Phase 1 (clean) & Phase 2 (ingest) orchestrators
│   │   ├── cleaner.py        # CSV normalisation, dedup, alias mapping
│   │   ├── scoring_engine.py # Smart Money Score computation
│   │   ├── notifier.py       # Email & Telegram alerting
│   │   ├── task_manager.py   # Background task registry & SSE buffer
│   │   ├── investor_aliases.json
│   │   └── sector_mapping.json
│   ├── signal_engine/
│   │   ├── pipeline.py       # EndToEndPipeline – daily batch runner
│   │   ├── orchestrator.py   # SignalEngine – strategy execution & consensus
│   │   ├── strategy.py       # Four concrete strategy implementations
│   │   ├── dal.py            # Data access layer (Mongo + Postgres queries)
│   │   ├── alerting.py       # Signal alert dispatch
│   │   ├── backtest.py       # Backtesting framework
│   │   ├── exit_engine.py    # Target price / stop-loss / exit date generation
│   │   └── models.py         # Pydantic schemas
│   ├── ingestion/
│   │   └── processor.py      # Row-by-row FIFO engine with checkpoint support
│   ├── db/
│   │   ├── mongo.py          # MongoDB client & collection references
│   │   └── postgres.py       # PostgreSQL connection pool
│   ├── migrations/           # Database schema migrations
│   ├── requirements.txt
│   ├── render.yaml           # Render deployment manifest
│   └── .env.example          # Environment variable template
├── frontend_admin/           # Admin portal (Vite + React)
│   └── src/
│       └── pages/
│           ├── PipelinePage.jsx   # Upload, clean, ingest UI with live SSE progress
│           └── DashboardPage.jsx  # Data viewer (investors, transactions, signals)
├── frontend_user/            # User-facing portal (Vite + React)
│   └── src/
│       └── pages/
│           ├── SignalCommandCenter.jsx
│           ├── WhaleScanner.jsx
│           ├── WhaleProfile.jsx
│           ├── HerdRadar.jsx
│           ├── AlphaTable.jsx
│           ├── CommandCenter.jsx
│           └── LiveActivity.jsx
├── CONCEPT.md                # The idea, philosophy, and reasoning behind Verity
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.13** (managed via `uv` or `pyenv`)
- **Node.js 20+** and npm
- A **MongoDB Atlas** cluster
- A **PostgreSQL** database (Supabase, Render Postgres, or local)

### Backend Setup

```bash
cd backend

# 1. Create a virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 2. Configure environment variables
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section)

# 3. Start the development server
python run_api.py
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### Frontend Setup

Both frontends follow the same steps. Run them in separate terminals.

**Admin Portal**
```bash
cd frontend_admin
npm install
npm run dev
# Available at http://localhost:5173
```

**User Portal**
```bash
cd frontend_user
npm install
npm run dev
# Available at http://localhost:5174
```

> Make sure the `VITE_API_URL` variable in each frontend's `.env` points to your running backend (e.g., `http://localhost:8000`).

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the values:

| Variable | Description |
|---|---|
| `MONGO_URI` | MongoDB Atlas connection string |
| `POSTGRES_URL` | PostgreSQL connection string (with `sslmode=require` for Supabase/Render) |
| `ALERT_EMAIL_TO` | Recipient email for crash/completion alerts |
| `ALERT_EMAIL_FROM` | Gmail sender address |
| `ALERT_EMAIL_PASSWORD` | Gmail App Password (16-char, **not** your login password) |
| `DASHBOARD_URL` | Public URL of the user dashboard (embedded in alerts) |
| `OPENAI_API_KEY` | OpenAI API key for the AI Contextualist |
| `TAVILY_API_KEY` | Tavily API key for real-time web search |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (use @userinfobot) |

---

## Data Pipeline

The pipeline is triggered from the **Admin Portal → Pipeline** page and runs in two phases:

```
CSV Upload
    │
    ▼ Phase 1: CLEAN (synchronous, SSE stream)
    ├─ Column normalisation & type coercion
    ├─ Investor name alias mapping
    ├─ Stock symbol remapping
    ├─ Duplicate row removal
    ├─ Intraday buy/sell pair filtering
    ├─ Corporate events cleaning (optional)
    └─ Save cleaned Parquet files to disk
    │
    ▼ Phase 2: INGEST (background task, SSE stream)
    ├─ SHA-256 checkpointing (pause/resume support)
    ├─ Chronological row-by-row replay
    ├─ FIFO lot matching (open_lots → closed_lots)
    ├─ Corporate action adjustments (splits, bonuses)
    ├─ Short-sell guard
    ├─ PostgreSQL flush (sell_transactions, investor_snapshots)
    ├─ MongoDB flush (investor profiles, open lots, positions)
    ├─ AI Smart Money Score calculation
    └─ Signal Engine trigger (high-conviction detection)
```

Batch upload is supported — multiple CSVs are merged in order before processing.

> For the reasoning behind FIFO lot matching and corporate-action handling — not just the mechanics — see [Concept: The Math That Can't Lie](./CONCEPT.md#the-math-that-cant-lie-fifo-and-corporate-actions).

---

## Signal Engine

After each ingestion, the Signal Engine runs a **daily batch** over all recent transactions:

1. For each new bulk deal, four strategies evaluate concurrently (`asyncio.gather`).
2. Strategies that lack historical data are excluded and weights are renormalised dynamically.
3. A **consensus score** (weighted sum) is computed.
4. Signals that pass the noise threshold (≥60 score from ≥2 strategies) are persisted to MongoDB.
5. For BUY signals, an **Exit Metadata** object is generated (target price, stop-loss, estimated exit date) based on the triggering whale's historical statistics.
6. Alerts are dispatched via Telegram and email.

Signals can also be manually triggered from the Admin Dashboard via `POST /data/signals/generate`.

---

## API Reference

The full interactive API documentation is available at `/docs` (Swagger UI) when the backend is running.

**Key endpoints:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/upload/clean` | Phase 1: upload & clean a single CSV |
| `POST` | `/upload/clean-batch` | Phase 1: upload & clean multiple CSVs |
| `POST` | `/upload/ingest` | Phase 2: start background ingestion |
| `GET` | `/upload/ingest/stream` | SSE stream for ingestion progress |
| `GET` | `/upload/task/status` | Poll background task status |
| `POST` | `/upload/pause` | Pause running ingestion |
| `POST` | `/upload/resume` | Resume paused ingestion |
| `GET` | `/data/investors` | List investors ranked by Smart Money Score |
| `GET` | `/data/investors/{id}` | Single investor profile |
| `GET` | `/data/investors/{id}/portfolio` | Full portfolio with lot breakdown |
| `GET` | `/data/signals` | Fetch latest high-conviction signals |
| `POST` | `/data/signals/generate` | Manually trigger the Signal Engine |
| `GET` | `/data/transactions` | Latest trading-day transactions |
| `GET` | `/data/sells` | Historical sell transactions |
| `POST` | `/data/clear` | ⚠️ Purge all data from both databases |
| `GET` | `/health` | Health check |

---

## Deployment

### Backend → Render

The `backend/render.yaml` file configures a Render web service:

```yaml
startCommand: gunicorn api.app:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 600
```

Set all environment variables in the Render dashboard (they are listed in `render.yaml` as `sync: false`).

### Frontends → Vercel

Both frontends include a `vercel.json` for SPA routing rewrites. Deploy by connecting the Vercel project to the respective subdirectory (`frontend_admin` or `frontend_user`) and setting `VITE_API_URL` in the Vercel environment settings.

---

> Built with ❤️ to make institutional intelligence accessible. See [`CONCEPT.md`](./CONCEPT.md) for the thinking behind it.