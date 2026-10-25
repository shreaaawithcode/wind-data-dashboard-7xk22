"""Generate FAKE wind data in the same shape as the Elexon snapshot, for demos and tests only.

Forecast error grows with lead time. The app shows a warning banner when this data is used.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
t = pd.date_range("2025-12-29", "2026-02-03", freq="30min", tz="UTC")
x = np.zeros(len(t))
for i in range(1, len(t)):
    x[i] = 0.996 * x[i - 1] + rng.normal(0, 0.05)
x = (x - x.mean()) / x.std()
actual = np.clip(7500 + 4200 * x, 150, 14500)
a = pd.Series(actual, index=t)

actuals = [{"startTime": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "generation": round(float(v), 0)}
           for ts, v in a.items() if "2026-01-02" <= ts.strftime("%Y-%m-%d") <= "2026-02-01"]

forecasts = []
for pub in pd.date_range("2026-01-01", "2026-02-01", freq="3h", tz="UTC", inclusive="left"):
    bias = rng.normal(0, 150)
    for k in range(1, 97):
        tgt = pub + pd.Timedelta(minutes=30 * k)
        if tgt not in a.index:
            continue
        lead = k / 2
        v = max(a[tgt] + bias + rng.normal(0, 250 + 55 * lead), 0)
        forecasts.append({"startTime": tgt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "publishTime": pub.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "generation": round(float(v), 0)})

out = Path(__file__).resolve().parents[1] / "data" / "synthetic_sample.json"
out.write_text(json.dumps({"meta": {"source": "synthetic"}, "actuals": actuals, "forecasts": forecasts}))
print(len(actuals), "actuals,", len(forecasts), "forecasts ->", out)
