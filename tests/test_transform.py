"""Unit tests for the transform and quality logic, using tiny hand-made data."""
import numpy as np
import pandas as pd
import pytest

from pipeline import quality
from pipeline.transform import (
    classify_condition,
    clean_flights,
    clean_weather,
    join_flights_weather,
)


def weather_row(**overrides):
    row = dict(origin="JFK", time_hour="2013-01-01T10:00:00Z", temp=50.0, humid=60.0,
               wind_speed=10.0, wind_gust=np.nan, precip=0.0, visib=10.0, pressure=1015.0)
    row.update(overrides)
    return row


@pytest.mark.parametrize("overrides, expected", [
    ({}, "Clear"),
    ({"precip": 0.02}, "Light rain"),
    ({"precip": 0.25}, "Heavy rain"),
    ({"precip": 0.05, "temp": 28.0}, "Snow / ice"),
    ({"visib": 0.5}, "Low visibility"),
    ({"visib": 2.0}, "Reduced visibility"),
    ({"wind_speed": 30.0}, "High wind"),
    ({"wind_gust": 40.0}, "High wind"),
    # priority: snow beats low visibility, heavy rain beats high wind
    ({"precip": 0.05, "temp": 30.0, "visib": 0.25}, "Snow / ice"),
    ({"precip": 0.3, "wind_speed": 35.0}, "Heavy rain"),
])
def test_classify_condition(overrides, expected):
    df = pd.DataFrame([weather_row(**overrides)])
    assert classify_condition(df).iloc[0] == expected


def test_clean_weather_nulls_impossible_wind_and_dedupes():
    df = pd.DataFrame([
        weather_row(wind_speed=1048.0),
        weather_row(),  # duplicate key
    ])
    out = clean_weather(df)
    assert len(out) == 1
    assert out["wind_speed"].isna().all()


def flights_df():
    return pd.DataFrame({
        "year": [2013] * 3, "month": [1] * 3, "day": [1] * 3,
        "dep_time": [905.0, np.nan, 1030.0],
        "dep_delay": [5.0, np.nan, 45.0],
        "hour": [9, 9, 10],
        "origin": ["JFK", "JFK", "LGA"],
        "time_hour": ["2013-01-01T10:00:00Z", "2013-01-01T10:00:00Z", "2013-01-01T11:00:00Z"],
    })


def test_clean_flights_flags():
    out = clean_flights(flights_df())
    assert out["is_cancelled"].tolist() == [False, True, False]
    assert out["is_delayed"].tolist() == [False, False, True]
    assert out["flight_id"].is_unique


def test_join_keeps_every_flight_and_marks_missing_weather():
    flights = clean_flights(flights_df())
    weather = clean_weather(pd.DataFrame([weather_row()]))  # only JFK 10:00 exists
    joined = join_flights_weather(flights, weather)
    assert len(joined) == len(flights)
    assert joined["weather_condition"].tolist() == ["Clear", "Clear", "Unknown"]


def test_quality_checks_catch_lost_rows():
    flights = clean_flights(flights_df())
    weather = clean_weather(pd.DataFrame([weather_row()]))
    joined = join_flights_weather(flights, weather)
    results = dict(quality.checks(joined, source_rows=len(joined) + 1))
    assert results["no flights lost or duplicated in the join"] is False
