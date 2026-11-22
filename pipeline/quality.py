"""
DATA QUALITY - checks that must pass before anything is loaded.

A failing check stops the pipeline, so bad data never reaches the warehouse.
"""
import logging

import pandas as pd

from pipeline import config as c
from pipeline.transform import CONDITION_ORDER

log = logging.getLogger(__name__)


class DataQualityError(Exception):
    pass


def checks(df: pd.DataFrame, source_rows: int) -> list[tuple[str, bool]]:
    valid_conditions = set(CONDITION_ORDER) | {"Unknown"}
    return [
        ("no flights lost or duplicated in the join", len(df) == source_rows),
        ("flight_id is unique", df["flight_id"].is_unique),
        ("origin is EWR, JFK or LGA", df["origin"].isin(["EWR", "JFK", "LGA"]).all()),
        ("cancelled flights have no departure delay",
         df.loc[df["is_cancelled"], "dep_delay"].isna().all()),
        ("weather matched for at least 99% of flights",
         (df["weather_condition"] != "Unknown").mean() >= 0.99),
        ("weather_condition values are all known labels",
         df["weather_condition"].isin(valid_conditions).all()),
        ("wind speeds are physically plausible",
         (df["wind_speed"].dropna() <= c.MAX_PLAUSIBLE_WIND_MPH).all()),
        ("visibility is between 0 and 10 miles", df["visib"].dropna().between(0, 10).all()),
        ("scheduled hour is 0-23", df["sched_dep_hour"].between(0, 23).all()),
    ]


def run(df: pd.DataFrame | None = None) -> None:
    if df is None:
        df = pd.read_parquet(c.STAGING / "flights_weather.parquet")
    source_rows = len(pd.read_parquet(c.RAW / "flights.parquet", columns=["flight"]))

    results = checks(df, source_rows)
    for name, passed in results:
        log.info("  [%s] %s", "PASS" if passed else "FAIL", name)
    failed = [name for name, passed in results if not passed]
    if failed:
        raise DataQualityError(f"{len(failed)} check(s) failed: {failed}")
    log.info("all %d data quality checks passed", len(results))
