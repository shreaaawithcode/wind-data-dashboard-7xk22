# UK Wind Forecast Desk

A web app for a day-ahead power buying desk. It answers two questions about GB national wind generation (Elexon BMRS data only):

1. **What is the latest wind forecast I can actually use when I make my day-ahead decision?**
2. **How accurate have those forecasts been, quantitatively?**

Scope: purchase decisions made in **January 2026** (decision on day D-1, delivery on day D, i.e. delivery days 2 Jan – 1 Feb 2026).

> **AI disclosure:** this project was built with AI assistance (Claude by Anthropic) for code generation and scaffolding. Design decisions and the analysis logic should be reviewed by the author before submission.

**Live app:** https://kjhwr-nu.vercel.app

## How the analysis works

- Actuals: `FUELHH` filtered to `fuelType == WIND` (30-min `startTime`, `generation` MW).
- Forecasts: `WINDFOR` (`startTime`, `publishTime`, `generation` MW).
- **Decision-time forecast:** for every delivery half-hour, take the forecast with the **latest `publishTime` at or before the cutoff** on the previous day (default **09:00 London**, adjustable in the UI; the EPEX GB day-ahead auction closes around 09:20). Anything published later is hindsight and is never used.
- `error = forecast − actual`. Positive means wind was over-forecast, so the buyer under-procures and faces a shortfall.
- Metrics: MAE, RMSE, bias, normalised MAE, MAPE (only where actual ≥ 100 MW), P90/P95 absolute error, error percentiles, share of over-forecast half-hours.
- The shaded band on the chart is `forecast − P95 error … forecast − P05 error`: where the actual landed 90% of the time across January.
- "Error vs forecast age" uses **all** January-published forecasts grouped by lead time, to show why the cutoff time matters.

Assumptions to confirm with the client: the cutoff time, and that the 90% band is built from the whole month (so it is in-sample, not a rolling out-of-sample estimate).

## Repository layout

```
backend/
  app/config.py      constants and env config (cutoff, date window, data paths)
  app/elexon.py      Elexon API client (FUELHH, WINDFOR), one request per day, threaded
  app/data.py        data loading: synthetic / snapshot / live, with a source label
  app/analysis.py    pure pandas functions: decision_table, metrics, by_day/hour/horizon
  app/main.py        FastAPI routes; also serves the built UI when frontend/dist exists
  tests/             pytest unit tests for the analysis logic
frontend/            Vite + React + Recharts dashboard
api/index.py         Vercel serverless entrypoint (imports the FastAPI app)
scripts/
  fetch_snapshot.py  download real Elexon data -> data/jan2026_snapshot.json
  make_synthetic.py  generate FAKE data for demos/tests -> data/synthetic_sample.json
data/                snapshot and synthetic data files
Dockerfile, docker-compose.yml, vercel.json
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/config` | date window, default cutoff, data source label |
| `GET /api/forecast?delivery_date=2026-01-15&cutoff=09:00` | decision-time forecast vs actual for one day, with band |
| `GET /api/metrics?cutoff=09:00` | overall metrics plus by day and by hour |
| `GET /api/horizon` | error by forecast age |

## Run it

### 1. Get the real data (do this first)

```bash
pip install -r backend/requirements.txt
python scripts/fetch_snapshot.py     # writes data/jan2026_snapshot.json
```

Without a snapshot the backend fetches live from Elexon on first request (slow, about 60 requests). Commit the snapshot so the Vercel deployment is fast and does not depend on the API at runtime.

### 2. Docker

```bash
docker compose up --build
# open http://localhost:8000
```

To try the UI on fake data: `python scripts/make_synthetic.py` then `DEMO_DATA=synthetic docker compose up --build`. A warning banner is shown whenever synthetic data is in use.

### 3. Without Docker

```bash
# backend
pip install -r backend/requirements-dev.txt
uvicorn backend.app.main:app --reload --port 8000
# frontend (separate terminal; proxies /api to :8000)
cd frontend && npm install && npm run dev
# tests
python -m pytest backend/tests -q
```

### Deploy to Vercel

Import the repo in Vercel (framework preset: Other). `vercel.json` builds the frontend to `frontend/dist`, serves it statically, and routes `/api/*` to `api/index.py`. Make sure `data/jan2026_snapshot.json` is committed. Add the resulting URL at the top of this README.

## Limitations / next steps

- Single month, national wind only, by design of the brief.
- The band is in-sample; a rolling or per-wind-level error model would be better.
- No demand data, so the app shows how much wind to expect and how wrong it may be, not the net volume to buy.
