-- Star schema for the flight delay warehouse.
-- {raw} and {staging} are replaced with the data folders by pipeline/load.py.

-- ---------- dimensions ----------
CREATE TABLE dim_airport AS
SELECT
    faa        AS airport_code,
    name       AS airport_name,
    lat, lon,
    alt        AS altitude_ft,
    tzone      AS timezone
FROM read_parquet('{raw}/airports.parquet');

CREATE TABLE dim_carrier AS
SELECT carrier AS carrier_code, name AS carrier_name
FROM read_parquet('{raw}/airlines.parquet');

CREATE TABLE dim_date AS
SELECT
    d::DATE                         AS date_key,
    EXTRACT(year FROM d)::INT       AS year,
    EXTRACT(month FROM d)::INT      AS month,
    strftime(d, '%b')               AS month_name,
    EXTRACT(quarter FROM d)::INT    AS quarter,
    EXTRACT(isodow FROM d)::INT     AS day_of_week,     -- 1 = Monday
    strftime(d, '%a')               AS day_name,
    EXTRACT(isodow FROM d) >= 6     AS is_weekend,
    CASE
        WHEN EXTRACT(month FROM d) IN (12, 1, 2) THEN 'Winter'
        WHEN EXTRACT(month FROM d) IN (3, 4, 5)  THEN 'Spring'
        WHEN EXTRACT(month FROM d) IN (6, 7, 8)  THEN 'Summer'
        ELSE 'Fall'
    END                             AS season
FROM generate_series(DATE '2013-01-01', DATE '2013-12-31', INTERVAL 1 DAY) AS t(d);

CREATE TABLE dim_weather_hour AS
SELECT
    origin || '|' || time_hour      AS weather_key,
    origin                          AS airport_code,
    time_hour::TIMESTAMPTZ          AS observed_at_utc,
    temp                            AS temp_f,
    humid                           AS humidity_pct,
    wind_speed                      AS wind_speed_mph,
    wind_gust                       AS wind_gust_mph,
    precip                          AS precip_in,
    visib                           AS visibility_mi,
    pressure                        AS pressure_mb,
    weather_condition
FROM read_parquet('{staging}/weather_clean.parquet');

-- ---------- fact ----------
CREATE TABLE fact_flights AS
SELECT
    flight_id,
    flight_date::DATE                       AS date_key,
    origin                                  AS origin_code,
    dest                                    AS dest_code,
    carrier                                 AS carrier_code,
    CASE WHEN weather_condition = 'Unknown' THEN NULL
         ELSE origin || '|' || time_hour END AS weather_key,
    flight                                  AS flight_number,
    tailnum,
    sched_dep_hour,
    sched_dep_time,
    dep_delay                               AS dep_delay_min,
    arr_delay                               AS arr_delay_min,
    air_time                                AS air_time_min,
    distance                                AS distance_mi,
    is_cancelled,
    is_delayed,
    weather_condition
FROM read_parquet('{staging}/flights_weather.parquet');
