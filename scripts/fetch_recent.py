"""
Fetch 2024-2025 flights and weather for the NYC airports and save a compact snapshot.

Runs in GitHub Actions (.github/workflows/fetch-recent.yml), which has open
internet access. The output is committed to snapshots/nyc2024_25/, so the
pipeline, tests and dashboard can run offline from that point on.

Sources
  Flights: US Bureau of Transportation Statistics (BTS), "Reporting Carrier
           On-Time Performance" monthly files - every domestic flight by a
           reporting airline, including official delay-cause minutes.
  Weather: Iowa Environmental Mesonet (IEM) ASOS archive - the hourly METAR
           observations recorded by the weather stations at EWR, JFK and LGA.

The output columns match the nycflights13 schema, so the same pipeline
transforms both datasets.

    python scripts/fetch_recent.py            # all of 2024-2025
    python scripts/fetch_recent.py --months 2 # first 2 months only (quick test)
"""
import argparse
import io
import json
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "snapshots" / "nyc2024_25"

AIRPORTS = ["EWR", "JFK", "LGA"]
YEARS = [2024, 2025]
LOCAL_TZ = "America/New_York"
KNOTS_TO_MPH = 1.15078

BTS_URL = ("https://transtats.bts.gov/PREZIP/"
           "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip")
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
HEADERS = {"User-Agent": "weather-flight-delay-pipeline (github.com/bnabinsu-hash)"}

BTS_COLUMNS = {
    "Year": "year", "Month": "month", "DayofMonth": "day", "FlightDate": "flight_date_str",
    "Reporting_Airline": "carrier", "Flight_Number_Reporting_Airline": "flight",
    "Tail_Number": "tailnum", "Origin": "origin", "Dest": "dest",
    "CRSDepTime": "sched_dep_time", "DepTime": "dep_time", "DepDelay": "dep_delay",
    "CRSArrTime": "sched_arr_time", "ArrTime": "arr_time", "ArrDelay": "arr_delay",
    "AirTime": "air_time", "Distance": "distance",
    "Cancelled": "cancelled", "CancellationCode": "cancellation_code", "Diverted": "diverted",
    "CarrierDelay": "carrier_delay", "WeatherDelay": "weather_delay", "NASDelay": "nas_delay",
    "SecurityDelay": "security_delay", "LateAircraftDelay": "late_aircraft_delay",
}

AIRLINES = {
    "9E": "Endeavor Air Inc.", "AA": "American Airlines Inc.", "AS": "Alaska Airlines Inc.",
    "B6": "JetBlue Airways", "DL": "Delta Air Lines Inc.", "F9": "Frontier Airlines Inc.",
    "G4": "Allegiant Air", "HA": "Hawaiian Airlines Inc.", "MQ": "Envoy Air",
    "NK": "Spirit Air Lines", "OH": "PSA Airlines Inc.", "OO": "SkyWest Airlines Inc.",
    "UA": "United Air Lines Inc.", "WN": "Southwest Airlines Co.", "YX": "Republic Airline",
    "QX": "Horizon Air", "ZW": "Air Wisconsin Airlines Corp", "C5": "CommuteAir",
    "G7": "GoJet Airlines", "PT": "Piedmont Airlines", "EV": "ExpressJet Airlines Inc.",
}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def get(url: str, params=None, attempts: int = 4, timeout: int = 300) -> requests.Response:
    for i in range(1, attempts + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            if r.status_code == 404:
                return r
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == attempts:
                raise
            wait = 10 * i
            log(f"  attempt {i} failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- flights

def fetch_bts_month(year: int, month: int) -> pd.DataFrame | None:
    url = BTS_URL.format(year=year, month=month)
    r = get(url)
    if r.status_code == 404 or not r.content.startswith(b"PK"):
        log(f"  {year}-{month:02d}: not published yet (status {r.status_code})")
        return None
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as f:
            header = pd.read_csv(f, nrows=0).columns
        missing = [c for c in BTS_COLUMNS if c not in header]
        if missing:
            raise RuntimeError(f"BTS file is missing columns {missing}; has {list(header)}")
        with z.open(name) as f:
            df = pd.read_csv(f, usecols=list(BTS_COLUMNS), low_memory=False,
                             dtype={"CancellationCode": "string", "Tail_Number": "string"})
    df = df[df["Origin"].isin(AIRPORTS)].rename(columns=BTS_COLUMNS)
    log(f"  {year}-{month:02d}: {len(df):,} NYC departures ({len(r.content) / 1e6:.0f} MB file)")
    return df


def to_utc_hour_key(local_naive: pd.Series) -> pd.Series:
    """Local wall-clock time -> 'YYYY-MM-DDTHH:00:00Z' key, the nycflights13 time_hour format."""
    utc = (local_naive.dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="shift_forward")
           .dt.tz_convert("UTC"))
    return utc.dt.strftime("%Y-%m-%dT%H:00:00Z")


def normalize_flights(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    sched = df["sched_dep_time"].astype(int).clip(upper=2359)
    df["hour"] = sched // 100
    df["minute"] = sched % 100
    local_hour = pd.to_datetime(df["flight_date_str"]) + pd.to_timedelta(df["hour"], unit="h")
    df["time_hour"] = to_utc_hour_key(local_hour)
    # BTS reports cancelled flights with no departure time; make sure of it
    df.loc[df["cancelled"] == 1, ["dep_time", "dep_delay"]] = pd.NA
    df = df.drop(columns=["flight_date_str"])
    for col in ["carrier", "origin", "dest", "cancellation_code"]:
        df[col] = df[col].astype("category")
    for col in ["year", "month", "day", "hour", "minute", "cancelled", "diverted"]:
        df[col] = df[col].astype("int16")
    for col in ["sched_dep_time", "sched_arr_time", "flight", "distance"]:
        df[col] = df[col].astype("int32")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- weather

def fetch_iem(station: str, year: int) -> pd.DataFrame:
    params = [("station", station), ("tz", "Etc/UTC"), ("format", "onlycomma"),
              ("latlon", "no"), ("elev", "no"), ("missing", "null"), ("trace", "0.0001"),
              ("direct", "no"), ("report_type", "3"), ("report_type", "4"),
              ("year1", year), ("month1", 1), ("day1", 1),
              ("year2", year + 1), ("month2", 1), ("day2", 1)]
    for field in ["tmpf", "dwpf", "relh", "drct", "sknt", "gust", "p01i", "vsby", "mslp"]:
        params.append(("data", field))
    r = get(IEM_URL, params=params)
    df = pd.read_csv(io.StringIO(r.text), na_values=["null", "M"])
    log(f"  {station} {year}: {len(df):,} observations")
    time.sleep(2)  # IEM asks for polite, sequential requests
    return df


def normalize_weather(obs: pd.DataFrame) -> pd.DataFrame:
    """Pick one observation per station-hour, preferring the routine :51 METAR."""
    w = obs.copy()
    w["valid"] = pd.to_datetime(w["valid"], utc=True)
    w["key"] = (w["valid"] + pd.Timedelta(minutes=9)).dt.floor("h")
    w["dist"] = (w["valid"] - (w["key"] - pd.Timedelta(minutes=9))).abs()
    w = w.sort_values(["station", "key", "dist"]).drop_duplicates(["station", "key"])
    local = w["key"].dt.tz_convert(LOCAL_TZ)
    out = pd.DataFrame({
        "origin": w["station"].astype(str),
        "year": local.dt.year, "month": local.dt.month,
        "day": local.dt.day, "hour": local.dt.hour,
        "temp": w["tmpf"], "dewp": w["dwpf"], "humid": w["relh"], "wind_dir": w["drct"],
        "wind_speed": w["sknt"] * KNOTS_TO_MPH, "wind_gust": w["gust"] * KNOTS_TO_MPH,
        "precip": w["p01i"], "pressure": w["mslp"], "visib": w["vsby"],
        "time_hour": w["key"].dt.strftime("%Y-%m-%dT%H:00:00Z"),
    })
    return out[out["year"].isin(YEARS)].reset_index(drop=True)


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=12, help="months per year to fetch")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    log("Fetching BTS on-time performance files")
    frames, months_loaded = [], []
    for year in YEARS:
        for month in range(1, args.months + 1):
            df = fetch_bts_month(year, month)
            if df is not None:
                frames.append(df)
                months_loaded.append(f"{year}-{month:02d}")
    if not frames:
        sys.exit("No BTS data could be downloaded")
    flights = normalize_flights(pd.concat(frames, ignore_index=True))

    log("Fetching IEM ASOS weather observations")
    obs = pd.concat([fetch_iem(s, y) for s in AIRPORTS for y in YEARS], ignore_index=True)
    weather = normalize_weather(obs)

    flights.to_parquet(OUT / "flights.parquet", index=False, compression="zstd")
    weather.to_parquet(OUT / "weather.parquet", index=False, compression="zstd")
    carriers = sorted(flights["carrier"].astype(str).unique())
    pd.DataFrame({"carrier": carriers, "name": [AIRLINES.get(c, c) for c in carriers]}) \
        .to_csv(OUT / "airlines.csv", index=False)

    meta = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "airports": AIRPORTS,
        "months": months_loaded,
        "flights": len(flights),
        "weather_hours": len(weather),
        "sources": {"flights": BTS_URL, "weather": IEM_URL},
    }
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2))
    log(f"Saved {len(flights):,} flights and {len(weather):,} weather hours "
        f"({len(months_loaded)} months) to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
