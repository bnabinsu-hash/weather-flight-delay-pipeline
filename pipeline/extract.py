"""
EXTRACT - pull the source tables into the raw landing zone.

Source: the `nycflights13` dataset - every flight that departed New York City
(EWR, JFK, LGA) in 2013, from the US Bureau of Transportation Statistics, plus
hourly weather observations at those three airports from NOAA.

Raw files are written as Parquet, unchanged except for an `_extracted_at`
audit column, so every later step can be re-run without re-downloading.
"""
import importlib.util
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.config import RAW, SOURCE_TABLES

log = logging.getLogger(__name__)


def source_dir() -> Path:
    """Locate the CSV files bundled with the nycflights13 package.

    The package's own __init__ imports `pkg_resources`, which newer Python
    environments no longer ship, so we find its data folder without importing it.
    """
    spec = importlib.util.find_spec("nycflights13")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("nycflights13 is not installed - run: pip install -r requirements.txt")
    return Path(spec.submodule_search_locations[0]) / "data"


def fetch_source(table: str) -> pd.DataFrame:
    folder = source_dir()
    path = folder / f"{table}.csv.zip"
    if not path.exists():
        path = folder / f"{table}.csv"
    return pd.read_csv(path)


def run() -> dict[str, int]:
    RAW.mkdir(parents=True, exist_ok=True)
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    counts = {}
    for table in SOURCE_TABLES:
        df = fetch_source(table)
        df["_extracted_at"] = extracted_at
        df.to_parquet(RAW / f"{table}.parquet", index=False)
        counts[table] = len(df)
        log.info("extracted %-8s %8s rows", table, f"{len(df):,}")
    return counts
