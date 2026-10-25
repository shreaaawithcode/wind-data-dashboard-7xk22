"""Central configuration. Everything overridable via environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
SNAPSHOT = DATA_DIR / "jan2026_snapshot.json"      # real Elexon data (scripts/fetch_snapshot.py)
SYNTHETIC = DATA_DIR / "synthetic_sample.json"     # fake data for demos/tests only

BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")

# Purchase decisions are made in January 2026 (decision day D-1 -> delivery day D).
DECISION_START = "2026-01-01"
DECISION_END = "2026-01-31"
FIRST_DELIVERY = "2026-01-02"
LAST_DELIVERY = "2026-02-01"

# Day-ahead gate closure, London local time, on the day before delivery.
# EPEX GB day-ahead auction closes ~09:20 UK time; 09:00 gives a safety margin.
DEFAULT_CUTOFF = os.getenv("DEFAULT_CUTOFF", "09:00")

# Ignore very low-wind periods in MAPE (percentage errors explode near zero).
MAPE_MIN_ACTUAL_MW = 100.0
