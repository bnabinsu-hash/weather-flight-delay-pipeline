"""
LOAD - build a DuckDB warehouse with a star schema, then create analysis marts.

  fact_flights      one row per flight (delay measures + keys)
  dim_weather_hour  one row per airport per hour of weather
  dim_airport       airports (origin + destination)
  dim_carrier       airlines
  dim_date          calendar attributes

The tables are rebuilt from scratch on every run, so the pipeline is idempotent:
running it twice gives the same result.
"""
import logging

import duckdb

from pipeline import config as c

log = logging.getLogger(__name__)


def run() -> dict[str, int]:
    c.WAREHOUSE.unlink(missing_ok=True)
    con = duckdb.connect(str(c.WAREHOUSE))
    try:
        for script in ["schema.sql", "marts.sql"]:
            sql = (c.SQL / script).read_text()
            sql = sql.replace("{raw}", c.RAW.as_posix()).replace("{staging}", c.STAGING.as_posix())
            con.execute(sql)
            log.info("ran sql/%s", script)

        counts = {}
        for (table,) in con.execute(
            "SELECT table_name FROM information_schema.tables ORDER BY table_name"
        ).fetchall():
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            log.info("  %-24s %10s rows", table, f"{counts[table]:,}")
        return counts
    finally:
        con.close()
