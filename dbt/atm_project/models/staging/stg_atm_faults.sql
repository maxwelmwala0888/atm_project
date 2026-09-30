{{ config(materialized='view') }}

SELECT
    atm_id,
    event_ts,
    event_date,
    fault_type,
    component,
    event_class,
    duration_mins,
    resolved,
    CASE WHEN event_class = 'fault' THEN 1 ELSE 0 END AS is_fault,
    CASE WHEN resolved = false     THEN 1 ELSE 0 END AS unresolved_flag
FROM silver.atm_fault_events
WHERE atm_id IS NOT NULL
