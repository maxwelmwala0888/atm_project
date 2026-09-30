{{ config(materialized='table') }}

WITH daily AS (
    SELECT
        atm_id,
        event_date,
        MIN(cash_level_mwk)              AS min_cash_mwk,
        MAX(cash_level_mwk)              AS max_cash_mwk,
        AVG(cash_level_mwk)              AS avg_cash_mwk,
        SUM(hourly_withdrawal_mwk)       AS total_withdrawal_mwk,
        COUNT(*) FILTER (WHERE was_refilled)     AS refill_count,
        COUNT(*) FILTER (WHERE below_threshold)  AS hours_below_threshold
    FROM {{ ref('stg_atm_cash') }}
    GROUP BY atm_id, event_date
)
SELECT
    atm_id,
    event_date,
    min_cash_mwk,
    max_cash_mwk,
    avg_cash_mwk,
    total_withdrawal_mwk,
    refill_count,
    hours_below_threshold,
    AVG(avg_cash_mwk) OVER (
        PARTITION BY atm_id ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS cash_ma_7d,
    AVG(total_withdrawal_mwk) OVER (
        PARTITION BY atm_id ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS withdrawal_ma_7d,
    LAG(min_cash_mwk)  OVER (PARTITION BY atm_id ORDER BY event_date) AS prev_min_cash,
    CASE
        WHEN min_cash_mwk < 50000 THEN 'critical'
        WHEN min_cash_mwk < 100000 THEN 'low'
        ELSE 'healthy'
    END AS cash_status
FROM daily
