"""
Interactive dashboard for the flight delay warehouse.

    streamlit run dashboard/app.py

Builds the warehouse first if it doesn't exist yet (e.g. on Streamlit Cloud).
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import config  # noqa: E402

st.set_page_config(page_title="NYC Flight Delays & Weather", page_icon="✈️", layout="wide")


@st.cache_resource
def get_connection():
    if not config.WAREHOUSE.exists():
        with st.spinner("Building the warehouse (first run only)..."):
            from pipeline import run
            run.main()
    return duckdb.connect(str(config.WAREHOUSE), read_only=True)


con = get_connection()


def q(sql: str, params=None) -> pd.DataFrame:
    return con.execute(sql, params or []).df()


st.title("✈️ How weather delays NYC flights")
st.caption("336,776 flights from EWR, JFK and LGA in 2013, matched to hourly airport weather.")

# ---------- filters ----------
c1, c2 = st.columns(2)
airports = c1.multiselect("Airport", ["EWR", "JFK", "LGA"], default=["EWR", "JFK", "LGA"])
months = c2.slider("Months", 1, 12, (1, 12))
if not airports:
    st.warning("Pick at least one airport.")
    st.stop()

where = "f.origin_code IN (SELECT UNNEST(?)) AND d.month BETWEEN ? AND ?"
params = [airports, months[0], months[1]]
base = f"FROM fact_flights f JOIN dim_date d USING (date_key) WHERE {where}"

# ---------- KPIs ----------
k = q(f"""
    SELECT COUNT(*) AS flights,
           100.0 * AVG(is_delayed::INT) AS delay_rate,
           100.0 * AVG(is_cancelled::INT) AS cancel_rate,
           AVG(dep_delay_min) AS avg_delay,
           100.0 * AVG((weather_condition NOT IN ('Clear','Unknown'))::INT) AS bad_wx
    {base}""", params).iloc[0]
m = st.columns(5)
m[0].metric("Flights", f"{int(k.flights):,}")
m[1].metric("Delayed 15+ min", f"{k.delay_rate:.1f}%")
m[2].metric("Cancelled", f"{k.cancel_rate:.2f}%")
m[3].metric("Avg departure delay", f"{k.avg_delay:.1f} min")
m[4].metric("Flights in bad weather", f"{k.bad_wx:.1f}%")

# ---------- charts ----------
left, right = st.columns(2)
with left:
    st.subheader("Delay rate by weather condition")
    df = q(f"""
        SELECT weather_condition AS condition, 100.0 * AVG(is_delayed::INT) AS delay_rate_pct
        {base} AND weather_condition <> 'Unknown'
        GROUP BY condition ORDER BY delay_rate_pct DESC""", params)
    st.bar_chart(df, x="condition", y="delay_rate_pct", horizontal=True, color="#eb6834")

with right:
    st.subheader("Delay rate by departure hour")
    df = q(f"""
        SELECT sched_dep_hour AS hour,
               CASE WHEN weather_condition = 'Clear' THEN 'Clear' ELSE 'Bad weather' END AS weather,
               100.0 * AVG(is_delayed::INT) AS delay_rate_pct
        {base} AND weather_condition <> 'Unknown' AND sched_dep_hour BETWEEN 5 AND 22
        GROUP BY ALL ORDER BY hour""", params)
    wide = df.pivot(index="hour", columns="weather", values="delay_rate_pct")
    st.line_chart(wide, color=["#eb6834", "#2a78d6"])

st.subheader("Daily delay rate")
df = q(f"""
    SELECT date_key AS date, 100.0 * AVG(is_delayed::INT) AS delay_rate_pct
    {base} GROUP BY date ORDER BY date""", params)
st.area_chart(df, x="date", y="delay_rate_pct", color="#2a78d6")

st.subheader("Worst days")
st.dataframe(
    q(f"""
        SELECT date_key AS date, COUNT(*) AS flights,
               ROUND(100.0 * AVG(is_delayed::INT), 1) AS delay_rate_pct,
               SUM(is_cancelled::INT) AS cancelled,
               MODE(weather_condition) FILTER (WHERE weather_condition NOT IN ('Clear','Unknown'))
                   AS main_bad_weather
        {base} GROUP BY date ORDER BY delay_rate_pct DESC LIMIT 10""", params),
    hide_index=True, width="stretch",
)
