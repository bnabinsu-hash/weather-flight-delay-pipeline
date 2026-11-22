"""
Build the README charts from the warehouse.

    python -m analysis.make_charts
"""
import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pipeline.config import IMAGES, WAREHOUSE  # noqa: E402

CLEAR = "#2a78d6"      # series 1: clear weather
BAD = "#eb6834"        # series 2: bad weather
NEUTRAL = "#a3a29c"    # baseline / reference
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
    "axes.titlecolor": INK, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK_2, "ytick.color": INK_2, "font.size": 10,
    "grid.color": GRID, "legend.frameon": False,
})

BAD_WEATHER = "weather_condition NOT IN ('Clear', 'Unknown')"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMAGES / name, dpi=150)
    plt.close(fig)
    print(f"saved images/{name}")


def delay_by_condition(con):
    df = con.sql("SELECT * FROM mart_delay_by_weather ORDER BY delay_rate_pct").df()
    colors = [NEUTRAL if c == "Clear" else BAD for c in df["weather_condition"]]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    ax.barh(df["weather_condition"], df["delay_rate_pct"], color=colors, height=0.6)
    for y, (r, n) in enumerate(zip(df["delay_rate_pct"], df["flights"])):
        ax.text(r + 0.6, y, f"{r:.1f}%   ({n:,} flights)", va="center", color=INK_2, fontsize=9)
    ax.set_title("Share of flights delayed 15+ min, by weather at departure")
    ax.set_xlabel("Delayed flights (%)")
    ax.set_xlim(0, df["delay_rate_pct"].max() * 1.45)
    ax.grid(axis="x"); ax.set_axisbelow(True)
    save(fig, "delay_by_weather.png")


def delay_by_hour(con):
    df = con.sql(f"""
        SELECT sched_dep_hour AS hour,
               {BAD_WEATHER} AS bad,
               100.0 * AVG(is_delayed::INT) AS rate
        FROM fact_flights
        WHERE weather_condition <> 'Unknown' AND sched_dep_hour BETWEEN 5 AND 22
        GROUP BY ALL ORDER BY hour
    """).df()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for bad, color, label in [(False, CLEAR, "Clear weather"), (True, BAD, "Bad weather")]:
        d = df[df["bad"] == bad]
        ax.plot(d["hour"], d["rate"], color=color, linewidth=2, marker="o", markersize=4, label=label)
        last = d.iloc[-1]
        ax.text(last["hour"] + 0.3, last["rate"], label, color=INK, fontsize=9, va="center")
    ax.set_title("Delays build up through the day, in any weather")
    ax.set_xlabel("Scheduled departure hour (local time)")
    ax.set_ylabel("Delayed flights (%)")
    ax.set_xticks(range(5, 23), [f"{h}:00" if h % 3 == 0 else "" for h in range(5, 23)])
    ax.set_xlim(4.5, 24.5)
    ax.set_ylim(0, df["rate"].max() * 1.15)
    ax.legend(loc="upper left")
    ax.grid(axis="y"); ax.set_axisbelow(True)
    save(fig, "delay_by_hour.png")


def airport_sensitivity(con):
    df = con.sql(f"""
        SELECT origin_code AS airport,
               100.0 * AVG(CASE WHEN weather_condition = 'Clear' THEN is_delayed::INT END) AS clear,
               100.0 * AVG(CASE WHEN {BAD_WEATHER} THEN is_delayed::INT END) AS bad
        FROM fact_flights GROUP BY airport ORDER BY airport
    """).df()
    names = {"EWR": "Newark (EWR)", "JFK": "JFK", "LGA": "LaGuardia (LGA)"}
    x = range(len(df))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8, 4.4))
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], df["clear"], width=w, color=CLEAR, label="Clear weather")
    b2 = ax.bar([i + w / 2 + 0.01 for i in x], df["bad"], width=w, color=BAD, label="Bad weather")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.6, f"{b.get_height():.1f}%",
                    ha="center", color=INK, fontsize=9)
    ax.set_xticks(list(x), [names[a] for a in df["airport"]])
    ax.set_title("Delay rate in clear vs bad weather, by airport")
    ax.set_ylabel("Delayed flights (%)")
    ax.set_ylim(0, df["bad"].max() * 1.25)
    ax.legend(loc="upper left", ncols=2)
    ax.grid(axis="y"); ax.set_axisbelow(True)
    save(fig, "airport_sensitivity.png")


def monthly(con):
    df = con.sql("""
        SELECT d.month, d.month_name, 100.0 * AVG(f.is_delayed::INT) AS rate
        FROM fact_flights f JOIN dim_date d USING (date_key)
        GROUP BY ALL ORDER BY d.month
    """).df()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(df["month_name"], df["rate"], color=CLEAR, width=0.62)
    for i, r in enumerate(df["rate"]):
        ax.text(i, r + 0.5, f"{r:.0f}%", ha="center", color=INK_2, fontsize=9)
    ax.set_title("Delay rate by month: summer storms and December peaks")
    ax.set_ylabel("Delayed flights (%)")
    ax.set_ylim(0, df["rate"].max() * 1.18)
    ax.grid(axis="y"); ax.set_axisbelow(True)
    save(fig, "delay_by_month.png")


def main():
    IMAGES.mkdir(exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        delay_by_condition(con)
        delay_by_hour(con)
        airport_sensitivity(con)
        monthly(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
