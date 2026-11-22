"""
EXTRACT - pull the source tables into the raw landing zone.

Source: the `nycflights13` dataset - every flight that departed New York City
(EWR, JFK, LGA) in 2013, from the US Bureau of Transportation Statistics, plus
hourly weather observations at those three airports from NOAA.

Raw files are written as Parquet, unchanged except for an `_extracted_at`
audit column, so every later step can be re-run without re-downloading.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

from pipeline.config import RAW, SOURCE_TABLES

log = logging.getLogger(__name__)


def fetch_source(table: str) -> pd.DataFrame:
    import nycflights13  # imported here so tests don't need the source package

    return getattr(nycflights13, table).copy()


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
