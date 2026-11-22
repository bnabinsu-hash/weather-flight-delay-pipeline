"""Paths and thresholds shared by every pipeline step."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"              # landing zone: data exactly as extracted
STAGING = DATA / "staging"      # cleaned + joined data, before loading
WAREHOUSE = DATA / "warehouse.duckdb"
SQL = ROOT / "sql"
IMAGES = ROOT / "images"

SOURCE_TABLES = ["flights", "weather", "airports", "airlines", "planes"]

# A departure is "delayed" when it leaves 15+ minutes late (the FAA/BTS definition)
DELAY_THRESHOLD_MIN = 15

# Weather thresholds (US units: mph, inches/hour, miles, °F)
MAX_PLAUSIBLE_WIND_MPH = 150      # anything above this is a sensor error
HEAVY_PRECIP_IN = 0.10            # heavy rain/snow rate
LOW_VISIBILITY_MI = 1.0           # below 1 mile = instrument flight rules (IFR)
REDUCED_VISIBILITY_MI = 3.0       # 1-3 miles = marginal VFR
HIGH_WIND_MPH = 25
HIGH_GUST_MPH = 35
FREEZING_F = 32
