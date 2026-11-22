-- Analysis marts: small, ready-to-use tables built on the star schema.
-- The dashboard and the charts read from these, not from the raw fact table.

-- Delay performance by weather condition
CREATE TABLE mart_delay_by_weather AS
SELECT
    weather_condition,
    COUNT(*)                                                 AS flights,
    ROUND(100.0 * AVG(is_delayed::INT), 1)                   AS delay_rate_pct,
    ROUND(100.0 * AVG(is_cancelled::INT), 2)                 AS cancel_rate_pct,
    ROUND(AVG(dep_delay_min), 1)                             AS avg_dep_delay_min
FROM fact_flights
WHERE weather_condition <> 'Unknown'
GROUP BY weather_condition;

-- One row per airport per day: volume, delays and the day's worst weather
CREATE TABLE mart_daily_airport AS
SELECT
    f.date_key,
    f.origin_code,
    COUNT(*)                                                 AS flights,
    SUM(f.is_delayed::INT)                                   AS delayed_flights,
    SUM(f.is_cancelled::INT)                                 AS cancelled_flights,
    ROUND(100.0 * AVG(f.is_delayed::INT), 1)                 AS delay_rate_pct,
    ROUND(AVG(f.dep_delay_min), 1)                           AS avg_dep_delay_min,
    ROUND(MAX(w.precip_in), 2)                               AS max_precip_in,
    ROUND(MIN(w.visibility_mi), 2)                           AS min_visibility_mi,
    ROUND(MAX(w.wind_speed_mph), 1)                          AS max_wind_mph
FROM fact_flights f
LEFT JOIN dim_weather_hour w USING (weather_key)
GROUP BY f.date_key, f.origin_code;

-- Delay rate by scheduled departure hour (shows delays cascading through the day)
CREATE TABLE mart_delay_by_hour AS
SELECT
    sched_dep_hour,
    COUNT(*)                                                 AS flights,
    ROUND(100.0 * AVG(is_delayed::INT), 1)                   AS delay_rate_pct,
    ROUND(AVG(dep_delay_min), 1)                             AS avg_dep_delay_min
FROM fact_flights
WHERE sched_dep_hour BETWEEN 5 AND 23
GROUP BY sched_dep_hour;
