"""Download the real January-2026 Elexon data once and save it to data/jan2026_snapshot.json.

Run from the repo root:   python scripts/fetch_snapshot.py
The snapshot makes the app fast and lets it run on Vercel (no live API calls at cold start).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import elexon  # noqa: E402
from backend.app.config import SNAPSHOT  # noqa: E402

raw = elexon.fetch_raw()
print(f"actuals: {len(raw['actuals'])}  forecasts: {len(raw['forecasts'])}")
if not raw["actuals"] or not raw["forecasts"]:
    sys.exit("Empty result - check network access / Elexon API response before using this snapshot.")
SNAPSHOT.parent.mkdir(exist_ok=True)
SNAPSHOT.write_text(json.dumps(raw))
print("saved", SNAPSHOT)
