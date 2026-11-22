"""
EXTRACT - pull the source tables into the raw landing zone.

nyc2013
    The `nycflights13` dataset: every flight that departed EWR, JFK or LGA in
    2013 (BTS on-time data) plus hourly NOAA weather at those airports.

nyc2024_25
    The snapshot in snapshots/nyc2024_25/, built by scripts/fetch_recent.py in
    GitHub Actions from BTS on-time data and IEM ASOS airport weather.

Raw files are written as Parquet with an `_extracted_at` audit column, so every
later step can be re-run without fetching again.
"""
import importlib.util
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline import config as c

log = logging.getLogger(__name__)


def nycflights13_dir() -> Path:
    """Locate the CSV files bundled with the nycflights13 package.

    The package's own __init__ imports `pkg_resources`, which newer Python
    environments no longer ship, so we find its data folder without importing it.
    """
    spec = importlib.util.find_spec("nycflights13")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("nycflights13 is not installed - run: pip install -r requirements.txt")
    return Path(spec.submodule_search_locations[0]) / "data"


def read_nycflights13(table: str) -> pd.DataFrame:
    folder = nycflights13_dir()
    path = folder / f"{table}.csv.zip"
    if not path.exists():
        path = folder / f"{table}.csv"
    return pd.read_csv(path)


def read_snapshot(table: str) -> pd.DataFrame:
    folder = c.SNAPSHOTS / "nyc2024_25"
    if table == "airports":           # airport reference data doesn't change
        return read_nycflights13("airports")
    if table == "airlines":
        return pd.read_csv(folder / "airlines.csv")
    path = folder / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - run the 'fetch-recent-data' GitHub Action "
            "or `python scripts/fetch_recent.py` to build the snapshot")
    df = pd.read_parquet(path)
    for col in df.select_dtypes("category").columns:   # plain strings, like nycflights13
        df[col] = df[col].astype("string")
    return df


def fetch_source(table: str, dataset: str = c.DATASET) -> pd.DataFrame:
    if dataset == "nyc2013":
        return read_nycflights13(table)
    return read_snapshot(table)


def run() -> dict[str, int]:
    c.RAW.mkdir(parents=True, exist_ok=True)
    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    counts = {}
    for table in c.SOURCE_TABLES:
        df = fetch_source(table)
        df["_extracted_at"] = extracted_at
        df.to_parquet(c.RAW / f"{table}.parquet", index=False)
        counts[table] = len(df)
        log.info("extracted %-8s %10s rows  [%s]", table, f"{len(df):,}", c.DATASET)
    return counts
