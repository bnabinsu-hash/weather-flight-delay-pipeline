-- Business questions answered against a dataset's warehouse
-- Run in the DuckDB CLI:   duckdb data/nyc2024_25/warehouse.duckdb < sql/analysis_queries.sql
--                    or:  duckdb data/nyc2013/warehouse.duckdb < sql/analysis_queries.sql

-- Q1. Headline numbers
SELECT
    COUNT(*)                                        AS flights,
    ROUND(100.0 * AVG(is_delayed::INT), 1)          AS delay_rate_pct,
    ROUND(100.0 * AVG(is_cancelled::INT), 2)        AS cancel_rate_pct,
    ROUND(AVG(dep_delay_min), 1)                    AS avg_dep_delay_min
FROM fact_flights;

-- Q2. How much worse are delays in each weather condition than in clear weather?
SELECT
    weather_condition,
    flights,
    delay_rate_pct,
    cancel_rate_pct,
    avg_dep_delay_min,
    ROUND(delay_rate_pct / (SELECT delay_rate_pct FROM mart_delay_by_weather
                            WHERE weather_condition = 'Clear'), 2) AS times_clear_rate
FROM mart_delay_by_weather
ORDER BY delay_rate_pct DESC;

-- Q3. Delay rate as visibility drops
SELECT
    CASE
        WHEN w.visibility_mi < 1  THEN '1) under 1 mi'
        WHEN w.visibility_mi < 3  THEN '2) 1-3 mi'
        WHEN w.visibility_mi < 6  THEN '3) 3-6 mi'
        WHEN w.visibility_mi < 10 THEN '4) 6-10 mi'
        ELSE                           '5) 10 mi (clear)'
    END                                             AS visibility_band,
    COUNT(*)                                        AS flights,
    ROUND(100.0 * AVG(f.is_delayed::INT), 1)        AS delay_rate_pct,
    ROUND(100.0 * AVG(f.is_cancelled::INT), 2)      AS cancel_rate_pct
FROM fact_flights f
JOIN dim_weather_hour w USING (weather_key)
GROUP BY visibility_band
ORDER BY visibility_band;

-- Q4. Which airport is most sensitive to bad weather?
WITH by_airport AS (
    SELECT
        origin_code,
        weather_condition = 'Clear'                 AS is_clear,
        AVG(is_delayed::INT)                        AS delay_rate
    FROM fact_flights
    WHERE weather_condition <> 'Unknown'
    GROUP BY origin_code, is_clear
)
SELECT
    a.airport_name,
    ROUND(100 * MAX(CASE WHEN is_clear THEN delay_rate END), 1)     AS clear_delay_pct,
    ROUND(100 * MAX(CASE WHEN NOT is_clear THEN delay_rate END), 1) AS bad_weather_delay_pct,
    ROUND(100 * (MAX(CASE WHEN NOT is_clear THEN delay_rate END)
               - MAX(CASE WHEN is_clear THEN delay_rate END)), 1)   AS increase_pts
FROM by_airport b
JOIN dim_airport a ON a.airport_code = b.origin_code
GROUP BY a.airport_name
ORDER BY increase_pts DESC;

-- Q5. Month by month: delays vs share of flights in bad weather
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(*)                                                        AS flights,
    ROUND(100.0 * AVG(f.is_delayed::INT), 1)                        AS delay_rate_pct,
    ROUND(100.0 * AVG((f.weather_condition NOT IN ('Clear', 'Unknown'))::INT), 1)
                                                                    AS pct_in_bad_weather
FROM fact_flights f
JOIN dim_date d USING (date_key)
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- Q6. Delays build up through the day
SELECT sched_dep_hour, flights, delay_rate_pct, avg_dep_delay_min
FROM mart_delay_by_hour
ORDER BY sched_dep_hour;

-- Q7. Airlines in bad weather: who holds up best? (carriers with 5,000+ flights)
SELECT
    c.carrier_name,
    COUNT(*)                                                        AS flights,
    ROUND(100.0 * AVG(CASE WHEN f.weather_condition = 'Clear'
                           THEN f.is_delayed::INT END), 1)          AS clear_delay_pct,
    ROUND(100.0 * AVG(CASE WHEN f.weather_condition NOT IN ('Clear', 'Unknown')
                           THEN f.is_delayed::INT END), 1)          AS bad_weather_delay_pct
FROM fact_flights f
JOIN dim_carrier c USING (carrier_code)
GROUP BY c.carrier_name
HAVING COUNT(*) >= 5000
ORDER BY bad_weather_delay_pct;

-- Q8. The 10 worst days of the year, with the weather behind them
SELECT
    date_key,
    SUM(flights)                                                    AS flights,
    ROUND(100.0 * SUM(delayed_flights) / SUM(flights), 1)           AS delay_rate_pct,
    SUM(cancelled_flights)                                          AS cancelled,
    MAX(max_precip_in)                                              AS max_precip_in,
    MIN(min_visibility_mi)                                          AS min_visibility_mi,
    MAX(max_wind_mph)                                               AS max_wind_mph
FROM mart_daily_airport
GROUP BY date_key
ORDER BY delay_rate_pct DESC
LIMIT 10;

-- Q9. Official BTS delay causes - share of all delay minutes (2024-25 data only)
SELECT
    ROUND(100 * SUM(late_aircraft_delay_min) / total, 1) AS late_aircraft_pct,
    ROUND(100 * SUM(carrier_delay_min)       / total, 1) AS carrier_pct,
    ROUND(100 * SUM(nas_delay_min)           / total, 1) AS air_traffic_system_pct,
    ROUND(100 * SUM(weather_delay_min)       / total, 1) AS extreme_weather_pct,
    ROUND(100 * SUM(security_delay_min)      / total, 1) AS security_pct
FROM fact_flights,
     (SELECT SUM(COALESCE(late_aircraft_delay_min, 0) + COALESCE(carrier_delay_min, 0)
               + COALESCE(nas_delay_min, 0) + COALESCE(weather_delay_min, 0)
               + COALESCE(security_delay_min, 0)) AS total
      FROM fact_flights)
GROUP BY total;

-- Q10. Cancellations by official cause code (2024-25 data only)
SELECT
    CASE cancellation_code
        WHEN 'A' THEN 'Airline' WHEN 'B' THEN 'Weather'
        WHEN 'C' THEN 'Air traffic system' WHEN 'D' THEN 'Security'
    END                                                  AS cause,
    COUNT(*)                                             AS cancellations,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct
FROM fact_flights
WHERE is_cancelled AND cancellation_code IS NOT NULL
GROUP BY cause
ORDER BY cancellations DESC;
