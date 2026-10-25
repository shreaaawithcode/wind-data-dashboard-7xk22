"""Pure analysis functions (no I/O) so they are easy to unit test.

Key idea
--------
For each half-hour of delivery day D the buyer must decide on day D-1, at a gate
closure time (default 09:00 London). The forecast they can actually use is the
LATEST one with publishTime <= that cutoff. Using any later forecast would be
hindsight. `decision_table` builds exactly that view, joined to actuals.

Sign convention: error = forecast - actual (MW).
  error > 0  -> wind over-forecast -> buyer under-procures -> exposed to a shortfall
  error < 0  -> wind under-forecast -> buyer over-procures  -> surplus to sell back
"""
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from .config import FIRST_DELIVERY, LAST_DELIVERY, MAPE_MIN_ACTUAL_MW

LONDON = ZoneInfo("Europe/London")


# ---------- helpers ----------
def _num(x, nd=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def _frames(raw: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    a = pd.DataFrame(raw.get("actuals", []), columns=["startTime", "generation"])
    f = pd.DataFrame(raw.get("forecasts", []), columns=["startTime", "publishTime", "generation"])
    a["startTime"] = pd.to_datetime(a["startTime"], utc=True)
    a["generation"] = a["generation"].astype(float)
    a = a.drop_duplicates("startTime", keep="last").rename(columns={"generation": "actual"})
    f["startTime"] = pd.to_datetime(f["startTime"], utc=True)
    f["publishTime"] = pd.to_datetime(f["publishTime"], utc=True)
    f["generation"] = f["generation"].astype(float)
    f = f.drop_duplicates(["startTime", "publishTime"], keep="last").rename(columns={"generation": "forecast"})
    return a, f


def _cutoffs(local_dates, cutoff: str) -> dict:
    """Map delivery date -> UTC timestamp of the day-ahead cutoff (D-1 at HH:MM London)."""
    h, m = (int(p) for p in cutoff.split(":"))
    out = {}
    for d in local_dates:
        naive = datetime.combine(d - timedelta(days=1), time(h, m))
        out[d] = pd.Timestamp(naive.replace(tzinfo=LONDON)).tz_convert("UTC")
    return out


# ---------- core ----------
def decision_table(raw: dict, cutoff: str) -> pd.DataFrame:
    """One row per delivery half-hour: latest forecast known at the cutoff + actual + error."""
    a, f = _frames(raw)
    if f.empty:
        return pd.DataFrame(columns=["startTime", "forecast", "publishTime", "delivery_date",
                                     "actual", "error", "lead_h"])
    f["delivery_date"] = f["startTime"].dt.tz_convert(LONDON).dt.date
    cmap = _cutoffs(f["delivery_date"].unique(), cutoff)
    f["cutoff"] = f["delivery_date"].map(cmap)
    known = f[f["publishTime"] <= f["cutoff"]].sort_values("publishTime")
    latest = known.groupby("startTime", as_index=False).last()
    df = latest.merge(a, on="startTime", how="left")
    lo, hi = pd.Timestamp(FIRST_DELIVERY).date(), pd.Timestamp(LAST_DELIVERY).date()
    df = df[(df["delivery_date"] >= lo) & (df["delivery_date"] <= hi)].copy()
    df["error"] = df["forecast"] - df["actual"]
    df["lead_h"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    return df.sort_values("startTime").reset_index(drop=True)


def metrics(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["actual", "forecast"])
    if d.empty:
        return {"n": 0}
    e, ae = d["error"], d["error"].abs()
    big = d["actual"] >= MAPE_MIN_ACTUAL_MW
    mean_actual = d["actual"].mean()
    q = e.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n": int(len(d)),
        "mae": _num(ae.mean()),
        "rmse": _num(np.sqrt((e ** 2).mean())),
        "bias": _num(e.mean()),
        "mape": _num((ae[big] / d.loc[big, "actual"]).mean() * 100) if big.any() else None,
        "nmae_pct": _num(ae.mean() / mean_actual * 100) if mean_actual else None,
        "median_ae": _num(ae.median()),
        "p90_ae": _num(ae.quantile(0.9)),
        "p95_ae": _num(ae.quantile(0.95)),
        "mean_actual": _num(mean_actual),
        "pct_over_forecast": _num((e > 0).mean() * 100),
        "mean_shortfall": _num(e.clip(lower=0).mean()),
        "err_p05": _num(q[0.05]), "err_p25": _num(q[0.25]), "err_p50": _num(q[0.5]),
        "err_p75": _num(q[0.75]), "err_p95": _num(q[0.95]),
    }


def _group(df: pd.DataFrame, key) -> list[dict]:
    d = df.dropna(subset=["actual", "forecast"])
    out = []
    for k, g in d.groupby(key):
        m = metrics(g)
        out.append({"key": k if not hasattr(k, "isoformat") else k.isoformat(),
                    **{x: m[x] for x in ("n", "mae", "rmse", "bias")}})
    return out


def by_day(df): return _group(df, "delivery_date")


def by_hour(df):
    d = df.copy()
    d["hour"] = d["startTime"].dt.tz_convert(LONDON).dt.hour
    return _group(d, "hour")


def by_horizon(raw: dict, bucket_h: int = 6) -> list[dict]:
    """Accuracy of ALL January-published forecasts against actuals, by lead time.

    Shows how error grows with horizon - useful to judge how stale a forecast is.
    """
    a, f = _frames(raw)
    d = f.merge(a, on="startTime", how="inner")
    if d.empty:
        return []
    d["error"] = d["forecast"] - d["actual"]
    d["lead_h"] = (d["startTime"] - d["publishTime"]).dt.total_seconds() / 3600
    d = d[d["lead_h"] >= 0]
    d["bucket"] = (d["lead_h"] // bucket_h * bucket_h).astype(int)
    out = []
    for b, g in d.groupby("bucket"):
        out.append({"key": f"{b}-{b + bucket_h}h", "lead_start": int(b), "n": int(len(g)),
                    "mae": _num(g["error"].abs().mean()),
                    "rmse": _num(np.sqrt((g["error"] ** 2).mean())),
                    "bias": _num(g["error"].mean())})
    return out


def day_view(df: pd.DataFrame, delivery_date, band: dict) -> dict:
    """Series for one delivery day, with an uncertainty band from historical error quantiles.

    actual = forecast - error, so with error in [q05, q95] the actual should fall in
    [forecast - q95, forecast - q05] about 90% of the time.
    """
    d = df[df["delivery_date"] == delivery_date]
    q05, q95 = band.get("err_p05"), band.get("err_p95")
    pts = []
    for r in d.itertuples():
        fc = float(r.forecast)
        pts.append({
            "t": r.startTime.isoformat(),
            "forecast": _num(fc),
            "actual": _num(r.actual),
            "error": _num(r.error),
            "lower": _num(max(fc - q95, 0)) if q95 is not None else None,
            "upper": _num(fc - q05) if q05 is not None else None,
            "publishTime": r.publishTime.isoformat(),
        })
    energy = _num(d["forecast"].sum() * 0.5, 0) if len(d) else None  # MW x 0.5h = MWh
    return {
        "delivery_date": delivery_date.isoformat(),
        "points": pts,
        "forecast_mwh": energy,
        "latest_publish": d["publishTime"].max().isoformat() if len(d) else None,
        "earliest_publish": d["publishTime"].min().isoformat() if len(d) else None,
        "summary": metrics(d),
    }
