import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import analysis  # noqa: E402


def raw():
    # Delivery slot 2026-01-10 12:00Z. Cutoff (D-1 09:00 London == 09:00Z in January).
    slot = "2026-01-10T12:00:00Z"
    return {
        "actuals": [{"startTime": slot, "generation": 5000},
                    {"startTime": "2026-01-10T12:30:00Z", "generation": 6000}],
        "forecasts": [
            {"startTime": slot, "publishTime": "2026-01-08T21:00:00Z", "generation": 4000},  # old
            {"startTime": slot, "publishTime": "2026-01-09T08:59:00Z", "generation": 5500},  # LATEST usable
            {"startTime": slot, "publishTime": "2026-01-09T09:01:00Z", "generation": 5000},  # after cutoff
            {"startTime": slot, "publishTime": "2026-01-10T06:00:00Z", "generation": 5000},  # hindsight
            {"startTime": "2026-01-10T12:30:00Z", "publishTime": "2026-01-09T06:00:00Z", "generation": 5000},
        ],
    }


def test_picks_latest_forecast_before_cutoff():
    df = analysis.decision_table(raw(), "09:00")
    row = df[df["startTime"].dt.strftime("%H:%M") == "12:00"].iloc[0]
    assert row["forecast"] == 5500
    assert row["error"] == 500


def test_later_cutoff_uses_later_forecast():
    df = analysis.decision_table(raw(), "09:30")
    row = df[df["startTime"].dt.strftime("%H:%M") == "12:00"].iloc[0]
    assert row["forecast"] == 5000  # the 09:01 publication is now visible


def test_metrics_values():
    m = analysis.metrics(analysis.decision_table(raw(), "09:00"))
    # errors: +500 and -1000
    assert m["n"] == 2
    assert m["mae"] == 750.0
    assert m["bias"] == -250.0
    assert m["rmse"] == round(((500**2 + 1000**2) / 2) ** 0.5, 1)
    assert m["pct_over_forecast"] == 50.0
    assert m["mean_shortfall"] == 250.0  # only the +500 error counts


def test_day_view_band_and_energy():
    df = analysis.decision_table(raw(), "09:00")
    band = analysis.metrics(df)
    v = analysis.day_view(df, date(2026, 1, 10), band)
    assert len(v["points"]) == 2
    assert v["forecast_mwh"] == (5500 + 5000) * 0.5
    p = v["points"][0]
    # error quantiles are [-1000, +500] so band = [forecast-q95, forecast-q05]
    assert p["lower"] <= p["upper"]
    assert p["upper"] == round(p["forecast"] - band["err_p05"], 1)


def test_horizon_buckets_nonnegative_lead():
    out = analysis.by_horizon(raw())
    assert all(b["lead_start"] >= 0 for b in out)
