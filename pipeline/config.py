"""Paths and thresholds shared by every pipeline step.

The pipeline can build more than one dataset. Pick one with the
PIPELINE_DATASET environment variable or `python -m pipeline.run --dataset ...`:

  nyc2013     every NYC departure in 2013 (nycflights13 package)
  nyc2024_25  every NYC departure in 2024-2025 (BTS + IEM ASOS snapshot)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
IMAGES = ROOT / "images"
SNAPSHOTS = ROOT / "snapshots"

DATASETS = {
    "nyc2013": "NYC airports, 2013",
    "nyc2024_25": "NYC airports, 2024-2025",
}
DEFAULT_DATASET = "nyc2013"
DATASET = os.environ.get("PIPELINE_DATASET", DEFAULT_DATASET)
if DATASET not in DATASETS:
    raise ValueError(f"Unknown dataset {DATASET!r}; choose from {list(DATASETS)}")


def data_dir(dataset: str) -> Path:
    return ROOT / "data" / dataset


def warehouse_path(dataset: str) -> Path:
    return data_dir(dataset) / "warehouse.duckdb"


DATA = data_dir(DATASET)
RAW = DATA / "raw"              # landing zone: data exactly as extracted
STAGING = DATA / "staging"      # cleaned + joined data, before loading
WAREHOUSE = warehouse_path(DATASET)

SOURCE_TABLES = ["flights", "weather", "airports", "airlines"]

# A departure is "delayed" when it leaves 15+ minutes late (the FAA/BTS definition)
DELAY_THRESHOLD_MIN = 15

# Weather thresholds (US units: mph, inches/hour, miles, °F)
MAX_PLAUSIBLE_WIND_MPH = 150      # anything above this is a sensor error
MEASURABLE_PRECIP_IN = 0.01       # smaller amounts are "trace" = none
HEAVY_PRECIP_IN = 0.10            # heavy rain/snow rate
LOW_VISIBILITY_MI = 1.0           # below 1 mile = instrument flight rules (IFR)
REDUCED_VISIBILITY_MI = 3.0       # 1-3 miles = marginal VFR
HIGH_WIND_MPH = 25
HIGH_GUST_MPH = 35
FREEZING_F = 32
