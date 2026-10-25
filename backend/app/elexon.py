"""Thin client for the Elexon Insights (BMRS) stream endpoints.

FUELHH  -> actual half-hourly generation by fuel type (we keep fuelType == WIND)
WINDFOR -> wind generation forecasts (startTime, publishTime, generation)

Requests are made one day at a time to stay inside the stream endpoints' range limits.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx

from .config import BASE_URL, DECISION_END, DECISION_START, FIRST_DELIVERY, LAST_DELIVERY


def _days(start: str, end: str):
    d, e = date.fromisoformat(start), date.fromisoformat(end)
    while d <= e:
        yield d
        d += timedelta(days=1)


def _get(client: httpx.Client, path: str, params: dict) -> list:
    for attempt in range(3):
        try:
            r = client.get(f"{BASE_URL}{path}", params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise
    return []


def _actuals_for(day: date) -> list:
    with httpx.Client() as c:
        rows = _get(c, "/datasets/FUELHH/stream", {
            "settlementDateFrom": day.isoformat(),
            "settlementDateTo": day.isoformat(),
            "fuelType": "WIND",
        })
    return [{"startTime": r["startTime"], "generation": r["generation"]}
            for r in rows if r.get("fuelType", "WIND") == "WIND"]


def _forecasts_for(day: date) -> list:
    frm = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    to = frm + timedelta(days=1)
    with httpx.Client() as c:
        rows = _get(c, "/datasets/WINDFOR/stream", {
            "publishDateTimeFrom": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return [{"startTime": r["startTime"], "publishTime": r["publishTime"],
             "generation": r["generation"]} for r in rows]


def fetch_raw() -> dict:
    """Actuals for every delivery day, forecasts published on every decision day."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        actuals = [x for chunk in pool.map(_actuals_for, _days(FIRST_DELIVERY, LAST_DELIVERY)) for x in chunk]
        forecasts = [x for chunk in pool.map(_forecasts_for, _days(DECISION_START, DECISION_END)) for x in chunk]
    return {
        "meta": {"fetchedAt": datetime.now(timezone.utc).isoformat(), "source": "elexon"},
        "actuals": actuals,
        "forecasts": forecasts,
    }
