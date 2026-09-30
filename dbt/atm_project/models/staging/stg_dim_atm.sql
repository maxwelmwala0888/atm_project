{{ config(materialized='view') }}

SELECT
    atm_id,
    city,
    region,
    latitude,
    longitude,
    atm_type,
    atm_model,
    bank,
    installed_date,
    is_active,
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, installed_date))::int AS age_years
FROM silver.dim_atm_network
