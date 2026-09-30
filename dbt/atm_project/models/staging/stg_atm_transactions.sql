{{ config(materialized='view') }}

SELECT
    atm_id,
    event_ts,
    event_date,
    tx_type,
    amount_mwk,
    card_type,
    success,
    EXTRACT(HOUR FROM event_ts)  AS tx_hour,
    EXTRACT(DOW  FROM event_ts)  AS day_of_week,
    CASE WHEN success THEN 1 ELSE 0 END AS success_flag
FROM silver.atm_transactions
WHERE atm_id IS NOT NULL
