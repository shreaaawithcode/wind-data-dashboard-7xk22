"""Data loading with a clear priority order, and an explicit label of where data came from.

1. DEMO_DATA=synthetic        -> data/synthetic_sample.json  (never real; UI shows a warning)
2. data/jan2026_snapshot.json -> real Elexon data saved by scripts/fetch_snapshot.py
3. otherwise                  -> fetch live from Elexon once, keep in memory
"""
import json
import os
from functools import lru_cache

from . import elexon
from .config import SNAPSHOT, SYNTHETIC


@lru_cache(maxsize=1)
def load_raw() -> tuple[dict, str]:
    if os.getenv("DEMO_DATA") == "synthetic":
        return json.loads(SYNTHETIC.read_text()), "synthetic"
    if SNAPSHOT.exists():
        return json.loads(SNAPSHOT.read_text()), "elexon-snapshot"
    return elexon.fetch_raw(), "elexon-live"
