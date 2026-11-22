"""
Compare 2013 with 2024-2025, and break down 2024-25 delays by official BTS cause.

Needs both warehouses:
    python -m pipeline.run --dataset nyc2013
    python -m pipeline.run --dataset nyc2024_25
    python -m analysis.compare_periods
"""
import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analysis.make_charts import CLEAR, INK, INK_2, SURFACE  # noqa: E402  (also applies rcParams)
from pipeline import config  # noqa: E402

Y2013 = "#a3a29c"   # older period recedes in neutral grey
Y2425 = CLEAR       # current period in series blue
CAUSE_COLORS = {     # categorical slots 1-4, fixed order
    "Late aircraft": "#2a78d6",
    "Air traffic system (NAS)": "#eb6834",
    "Airline (carrier)": "#1baf7a",
    "Weather (extreme)": "#eda100",
}
BAD = "weather_condition NOT IN ('Clear', 'Unknown')"
ORDER = ["Clear", "Reduced visibility", "Light rain", "Low visibility",
         "High wind", "Heavy rain", "Snow / ice"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(config.IMAGES / name, dpi=150)
    plt.close(fig)
    print(f"saved images/{name}")


def connect():
    con = duckdb.connect(str(config.warehouse_path("nyc2024_25")), read_only=True)
    con.execute(f"ATTACH '{config.warehouse_path('nyc2013')}' AS y13 (READ_ONLY)")
    return con


def yearly_summary(con):
    return con.sql(f"""
        SELECT '2013' AS period, COUNT(*) AS flights,
               ROUND(100 * AVG(is_delayed::INT), 1) AS delay_rate_pct,
               ROUND(100 * AVG(is_cancelled::INT), 2) AS cancel_rate_pct,
               ROUND(AVG(dep_delay_min), 1) AS avg_dep_delay_min,
               ROUND(100 * AVG(({BAD})::INT), 1) AS pct_flights_bad_weather
        FROM y13.fact_flights
        UNION ALL
        SELECT year(date_key)::VARCHAR, COUNT(*),
               ROUND(100 * AVG(is_delayed::INT), 1), ROUND(100 * AVG(is_cancelled::INT), 2),
               ROUND(AVG(dep_delay_min), 1), ROUND(100 * AVG(({BAD})::INT), 1)
        FROM fact_flights GROUP BY 1
        ORDER BY period
    """).df()


def compare_by_weather(con):
    df = con.sql("""
        SELECT a.weather_condition, b.delay_rate_pct AS y2013, a.delay_rate_pct AS y2425
        FROM mart_delay_by_weather a JOIN y13.mart_delay_by_weather b USING (weather_condition)
    """).df().set_index("weather_condition").loc[ORDER]
    y = np.arange(len(df))
    h = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(y + h / 2 + 0.01, df["y2013"], height=h, color=Y2013, label="2013")
    ax.barh(y - h / 2 - 0.01, df["y2425"], height=h, color=Y2425, label="2024-2025")
    for i, (a, b) in enumerate(zip(df["y2013"], df["y2425"])):
        ax.text(a + 0.5, i + h / 2 + 0.01, f"{a:.1f}%", va="center", color=INK_2, fontsize=8.5)
        ax.text(b + 0.5, i - h / 2 - 0.01, f"{b:.1f}%", va="center", color=INK, fontsize=8.5)
    ax.set_yticks(y, df.index)
    ax.set_title("Delay rate by weather at departure: 2013 vs 2024-2025")
    ax.set_xlabel("Flights delayed 15+ min (%)")
    ax.set_xlim(0, df.values.max() * 1.2)
    ax.legend(loc="lower right")
    ax.grid(axis="x"); ax.set_axisbelow(True)
    save(fig, "compare_delay_by_weather.png")


def causes_by_weather(con):
    df = con.sql("""
        SELECT weather_condition,
               AVG(COALESCE(late_aircraft_delay_min, 0)) AS "Late aircraft",
               AVG(COALESCE(nas_delay_min, 0))           AS "Air traffic system (NAS)",
               AVG(COALESCE(carrier_delay_min, 0))       AS "Airline (carrier)",
               AVG(COALESCE(weather_delay_min, 0))       AS "Weather (extreme)"
        FROM fact_flights
        WHERE NOT is_cancelled AND weather_condition <> 'Unknown'
        GROUP BY weather_condition
    """).df().set_index("weather_condition").loc[ORDER]
    fig, ax = plt.subplots(figsize=(9, 5))
    left = np.zeros(len(df))
    for cause, color in CAUSE_COLORS.items():
        ax.barh(df.index, df[cause], left=left, color=color, height=0.62,
                edgecolor=SURFACE, linewidth=1.5, label=cause)
        left += df[cause].values
    for i, total in enumerate(left):
        ax.text(total + 0.8, i, f"{total:.0f} min", va="center", color=INK, fontsize=9)
    ax.set_title("Average arrival-delay minutes per flight, by official BTS cause (2024-2025)")
    ax.set_xlabel("Minutes of delay per flight")
    ax.set_xlim(0, left.max() * 1.15)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(axis="x"); ax.set_axisbelow(True)
    save(fig, "causes_by_weather_2024_25.png")


def main():
    config.IMAGES.mkdir(exist_ok=True)
    con = connect()
    try:
        print(yearly_summary(con).to_string(index=False))
        compare_by_weather(con)
        causes_by_weather(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
