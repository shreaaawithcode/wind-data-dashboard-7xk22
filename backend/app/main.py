from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analysis
from .config import DEFAULT_CUTOFF, FIRST_DELIVERY, LAST_DELIVERY, ROOT
from .data import load_raw

app = FastAPI(title="UK wind forecast accuracy", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

CutoffParam = Query(DEFAULT_CUTOFF, pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
                    description="Day-ahead cutoff on D-1, London time HH:MM")


@lru_cache(maxsize=64)
def _table(cutoff: str):
    raw, _ = load_raw()
    return analysis.decision_table(raw, cutoff)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    raw, source = load_raw()
    return {
        "first_delivery": FIRST_DELIVERY,
        "last_delivery": LAST_DELIVERY,
        "default_cutoff": DEFAULT_CUTOFF,
        "data_source": source,
        "n_actuals": len(raw.get("actuals", [])),
        "n_forecasts": len(raw.get("forecasts", [])),
        "fetched_at": raw.get("meta", {}).get("fetchedAt"),
    }


@app.get("/api/forecast")
def forecast(delivery_date: date, cutoff: str = CutoffParam):
    df = _table(cutoff)
    if delivery_date not in set(df["delivery_date"]):
        raise HTTPException(404, f"No data for {delivery_date}")
    band = analysis.metrics(df)
    return analysis.day_view(df, delivery_date, band)


@app.get("/api/metrics")
def get_metrics(cutoff: str = CutoffParam):
    df = _table(cutoff)
    return {
        "cutoff": cutoff,
        "overall": analysis.metrics(df),
        "by_day": analysis.by_day(df),
        "by_hour": analysis.by_hour(df),
    }


@app.get("/api/horizon")
def horizon():
    raw, _ = load_raw()
    return {"buckets": analysis.by_horizon(raw)}


# Serve the built React app when present (Docker / local single-process mode).
_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = _dist / path
        return FileResponse(f if f.is_file() else _dist / "index.html")
