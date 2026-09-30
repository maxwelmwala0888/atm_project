CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS silver.atm_transactions (
    atm_id        VARCHAR(20),
    event_ts      TIMESTAMP,
    event_date    DATE,
    tx_type       VARCHAR(30),
    amount_mwk    BIGINT,
    card_type     VARCHAR(20),
    success       BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.atm_fault_events (
    atm_id        VARCHAR(20),
    event_ts      TIMESTAMP,
    event_date    DATE,
    fault_type    VARCHAR(50),
    component     VARCHAR(50),
    event_class   VARCHAR(20),
    duration_mins INT,
    resolved      BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.atm_cash_levels (
    atm_id                VARCHAR(20),
    event_ts              TIMESTAMP,
    event_date            DATE,
    cash_level_mwk        BIGINT,
    hourly_withdrawal_mwk BIGINT,
    was_refilled          BOOLEAN,
    below_threshold       BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.replenishments (
    atm_id             VARCHAR(20),
    refill_ts          TIMESTAMP,
    amount_loaded_mwk  BIGINT,
    cit_team           VARCHAR(20),
    downtime_mins      INT
);

CREATE TABLE IF NOT EXISTS silver.dim_atm_network (
    atm_id         VARCHAR(20) PRIMARY KEY,
    city           VARCHAR(50),
    region         VARCHAR(30),
    latitude       DOUBLE PRECISION,
    longitude      DOUBLE PRECISION,
    atm_type       VARCHAR(30),
    atm_model      VARCHAR(50),
    bank           VARCHAR(80),
    installed_date DATE,
    is_active      BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_tx_atm_date    ON silver.atm_transactions (atm_id, event_date);
CREATE INDEX IF NOT EXISTS idx_fault_atm_date ON silver.atm_fault_events (atm_id, event_date);
CREATE INDEX IF NOT EXISTS idx_cash_atm_date  ON silver.atm_cash_levels  (atm_id, event_date);
