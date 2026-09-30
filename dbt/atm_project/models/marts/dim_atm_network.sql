{{ config(materialized='table') }}

WITH base AS (
    SELECT * FROM {{ ref('stg_dim_atm') }}
),
tx_stats AS (
    SELECT
        atm_id,
        COUNT(*)                                          AS total_tx,
        COUNT(*) FILTER (WHERE success_flag = 0)          AS failed_tx,
        AVG(amount_mwk) FILTER (WHERE tx_type = 'withdrawal') AS avg_withdrawal_mwk,
        MAX(event_date)                                   AS last_tx_date
    FROM {{ ref('stg_atm_transactions') }}
    GROUP BY atm_id
),
fault_stats AS (
    SELECT
        atm_id,
        COUNT(*) FILTER (WHERE is_fault = 1)              AS lifetime_faults,
        MAX(event_date) FILTER (WHERE is_fault = 1)       AS last_fault_date
    FROM {{ ref('stg_atm_faults') }}
    GROUP BY atm_id
)
SELECT
    b.atm_id,
    b.city,
    b.region,
    b.latitude,
    b.longitude,
    b.atm_type,
    b.atm_model,
    b.bank,
    b.installed_date,
    b.age_years,
    b.is_active,
    COALESCE(t.total_tx, 0)            AS total_tx,
    COALESCE(t.failed_tx, 0)           AS failed_tx,
    COALESCE(t.failed_tx, 0)::float / NULLIF(t.total_tx, 0) AS failure_rate,
    COALESCE(t.avg_withdrawal_mwk, 0)  AS avg_withdrawal_mwk,
    t.last_tx_date,
    COALESCE(f.lifetime_faults, 0)     AS lifetime_faults,
    f.last_fault_date
FROM base b
LEFT JOIN tx_stats    t ON t.atm_id = b.atm_id
LEFT JOIN fault_stats f ON f.atm_id = b.atm_id
