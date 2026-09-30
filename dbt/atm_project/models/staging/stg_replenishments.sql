{{ config(materialized='view') }}

SELECT
    atm_id,
    refill_ts,
    DATE(refill_ts) AS refill_date,
    amount_loaded_mwk,
    cit_team,
    downtime_mins
FROM silver.replenishments
WHERE atm_id IS NOT NULL
