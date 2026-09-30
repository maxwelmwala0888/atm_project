{{ config(materialized='table') }}

WITH base AS (
    SELECT * FROM {{ ref('stg_atm_faults') }}
),
daily AS (
    SELECT
        atm_id,
        event_date,
        COUNT(*) FILTER (WHERE is_fault = 1)       AS faults,
        COUNT(*) FILTER (WHERE event_class='warning') AS warnings,
        COUNT(*) FILTER (WHERE unresolved_flag = 1)   AS unresolved,
        AVG(duration_mins) FILTER (WHERE is_fault=1)  AS avg_duration_mins,
        SUM(duration_mins) FILTER (WHERE is_fault=1)  AS total_downtime_mins
    FROM base
    GROUP BY atm_id, event_date
),
by_component AS (
    SELECT
        atm_id,
        event_date,
        component,
        COUNT(*) AS component_events
    FROM base
    GROUP BY atm_id, event_date, component
),
pivoted AS (
    SELECT
        atm_id,
        event_date,
        SUM(CASE WHEN component='card_reader' THEN component_events ELSE 0 END) AS card_reader,
        SUM(CASE WHEN component='dispenser'   THEN component_events ELSE 0 END) AS dispenser,
        SUM(CASE WHEN component='printer'     THEN component_events ELSE 0 END) AS printer,
        SUM(CASE WHEN component='network'     THEN component_events ELSE 0 END) AS network,
        SUM(CASE WHEN component='display'     THEN component_events ELSE 0 END) AS display,
        SUM(CASE WHEN component='power_unit'  THEN component_events ELSE 0 END) AS power_unit,
        SUM(CASE WHEN component='sensors'     THEN component_events ELSE 0 END) AS sensors
    FROM by_component
    GROUP BY atm_id, event_date
)
SELECT
    d.atm_id,
    d.event_date,
    d.faults,
    d.warnings,
    d.unresolved,
    COALESCE(d.avg_duration_mins, 0)   AS avg_duration_mins,
    COALESCE(d.total_downtime_mins, 0) AS total_downtime_mins,
    COALESCE(p.card_reader, 0) AS card_reader_events,
    COALESCE(p.dispenser,   0) AS dispenser_events,
    COALESCE(p.printer,     0) AS printer_events,
    COALESCE(p.network,     0) AS network_events,
    COALESCE(p.display,     0) AS display_events,
    COALESCE(p.power_unit,  0) AS power_unit_events,
    COALESCE(p.sensors,     0) AS sensors_events,
    SUM(d.faults) OVER (
        PARTITION BY d.atm_id ORDER BY d.event_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS faults_ma_30d,
    CASE
        WHEN d.faults >= 2 THEN 'high'
        WHEN d.warnings >= 5 THEN 'medium'
        ELSE 'low'
    END AS severity
FROM daily d
LEFT JOIN pivoted p ON p.atm_id = d.atm_id AND p.event_date = d.event_date
