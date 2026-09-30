{{ config(materialized='view') }}

SELECT
    atm_id,
    event_ts,
    event_date,
    cash_level_mwk,
    hourly_withdrawal_mwk,
    was_refilled,
    below_threshold
FROM silver.atm_cash_levels
WHERE atm_id IS NOT NULL
