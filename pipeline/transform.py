"""
TRANSFORM - clean flights and weather, then join them hour by hour.

Every flight is matched to the weather observed at its origin airport during
its scheduled departure hour. Each weather hour is labelled with one
`weather_condition`, so delays can be compared across conditions.
"""
import logging

import numpy as np
import pandas as pd

from pipeline import config as c

log = logging.getLogger(__name__)

# Highest-impact condition wins when several apply in the same hour
CONDITION_ORDER = [
    "Snow / ice",
    "Heavy rain",
    "Low visibility",
    "High wind",
    "Light rain",
    "Reduced visibility",
    "Clear",
]


def clean_weather(weather: pd.DataFrame) -> pd.DataFrame:
    w = weather.drop(columns=["_extracted_at"], errors="ignore").copy()

    # One reading reports 1,048 mph wind - a sensor error. Null out impossible values.
    bad_wind = w["wind_speed"] > c.MAX_PLAUSIBLE_WIND_MPH
    if bad_wind.any():
        log.info("nulled %d impossible wind_speed readings", int(bad_wind.sum()))
    w.loc[bad_wind, "wind_speed"] = np.nan

    w["precip"] = w["precip"].fillna(0.0)
    w = w.drop_duplicates(subset=["origin", "time_hour"])
    w["weather_condition"] = classify_condition(w)
    return w


def classify_condition(w: pd.DataFrame) -> pd.Series:
    """Label each hour with its single most disruptive weather condition."""
    precip = w["precip"].fillna(0)
    gust = w["wind_gust"].fillna(0)
    wind = w["wind_speed"].fillna(0)
    rules = [
        (precip > 0) & (w["temp"] <= c.FREEZING_F),                          # Snow / ice
        precip >= c.HEAVY_PRECIP_IN,                                          # Heavy rain
        w["visib"] < c.LOW_VISIBILITY_MI,                                     # Low visibility
        (wind >= c.HIGH_WIND_MPH) | (gust >= c.HIGH_GUST_MPH),                # High wind
        precip > 0,                                                           # Light rain
        w["visib"] < c.REDUCED_VISIBILITY_MI,                                 # Reduced visibility
    ]
    return pd.Series(
        np.select(rules, CONDITION_ORDER[:-1], default="Clear"), index=w.index
    )


def clean_flights(flights: pd.DataFrame) -> pd.DataFrame:
    f = flights.drop(columns=["_extracted_at"], errors="ignore").copy()
    f["flight_date"] = pd.to_datetime(f[["year", "month", "day"]]).dt.date
    f["is_cancelled"] = f["dep_time"].isna()
    f["is_delayed"] = (f["dep_delay"] >= c.DELAY_THRESHOLD_MIN) & ~f["is_cancelled"]
    f["flight_id"] = np.arange(1, len(f) + 1)
    f = f.rename(columns={"hour": "sched_dep_hour"})
    return f


def join_flights_weather(flights: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    weather_cols = [
        "origin", "time_hour", "temp", "humid", "wind_speed", "wind_gust",
        "precip", "visib", "pressure", "weather_condition",
    ]
    joined = flights.merge(weather[weather_cols], on=["origin", "time_hour"], how="left")
    missing = joined["weather_condition"].isna()
    joined["weather_condition"] = joined["weather_condition"].fillna("Unknown")
    log.info("joined weather to %s flights (%s had no weather reading)",
             f"{(~missing).sum():,}", f"{missing.sum():,}")
    return joined


def run() -> pd.DataFrame:
    flights = pd.read_parquet(c.RAW / "flights.parquet")
    weather = pd.read_parquet(c.RAW / "weather.parquet")

    weather_clean = clean_weather(weather)
    flights_clean = clean_flights(flights)
    joined = join_flights_weather(flights_clean, weather_clean)

    c.STAGING.mkdir(parents=True, exist_ok=True)
    weather_clean.to_parquet(c.STAGING / "weather_clean.parquet", index=False)
    joined.to_parquet(c.STAGING / "flights_weather.parquet", index=False)
    return joined
