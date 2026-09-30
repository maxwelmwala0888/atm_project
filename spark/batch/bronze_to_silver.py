"""Spark batch: Bronze Parquet -> PostgreSQL silver schema"""
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, to_timestamp, to_date, lit, current_timestamp
)

PG_URL = "jdbc:postgresql://postgres:5432/atm_warehouse"
PG_PROPS = {
    "user": "atm",
    "password": "atm_pass",
    "driver": "org.postgresql.Driver",
}
BRONZE = "/data/bronze"

def write_pg(df, table, mode="overwrite"):
    (df.write
       .mode("overwrite")
       .option("truncate", "true")
       .jdbc(PG_URL, f"silver.{table}", properties=PG_PROPS))
    print(f"  -> wrote silver.{table}: {df.count():,} rows")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True,
                    choices=["transactions","cash","faults",
                             "replenishments","dim"])
    args = ap.parse_args()

    spark = (SparkSession.builder
             .appName(f"bronze_to_silver_{args.table}")
             .config("spark.sql.shuffle.partitions", "4")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    t = args.table
    print(f"=== Processing {t} ===")

    if t == "transactions":
        df = spark.read.parquet(f"{BRONZE}/atm_transactions")
        out = (df.select(
                    col("atm_id"),
                    to_timestamp("timestamp").alias("event_ts"),
                    to_date("timestamp").alias("event_date"),
                    col("tx_type"),
                    col("amount_mwk"),
                    col("card_type"),
                    col("success"))
                 .filter(col("atm_id").isNotNull()))

    elif t == "cash":
        df = spark.read.parquet(f"{BRONZE}/atm_cash")
        out = (df.select(
                    col("atm_id"),
                    to_timestamp("timestamp").alias("event_ts"),
                    to_date("timestamp").alias("event_date"),
                    col("cash_level_mwk"),
                    col("hourly_withdrawal_mwk"),
                    col("was_refilled"),
                    col("below_threshold"))
                 .filter(col("atm_id").isNotNull()))

    elif t == "faults":
        df = spark.read.parquet(f"{BRONZE}/atm_faults")
        out = (df.select(
                    col("atm_id"),
                    to_timestamp("event_timestamp").alias("event_ts"),
                    to_date("event_timestamp").alias("event_date"),
                    col("fault_type"),
                    col("component"),
                    col("event_class"),
                    col("duration_mins").cast("int"),
                    col("resolved"),
                    lit(None).cast("int").alias("fault_occurred"))
                 .drop("fault_occurred")
                 .filter(col("atm_id").isNotNull()))
        out = out.withColumn("fault_occurred", lit(1))

    elif t == "replenishments":
        df = spark.read.parquet(f"{BRONZE}/atm_replenishments")
        out = (df.select(
                    col("atm_id"),
                    to_timestamp("refill_timestamp").alias("refill_ts"),
                    col("amount_loaded_mwk"),
                    col("cit_team"),
                    col("downtime_mins").cast("int"))
                 .filter(col("atm_id").isNotNull()))

    elif t == "dim":
        df = spark.read.parquet(f"{BRONZE}/atm_dim")
        out = (df.select(
                    col("atm_id"),
                    col("city"),
                    col("region"),
                    col("latitude").cast("double"),
                    col("longitude").cast("double"),
                    col("atm_type"),
                    col("atm_model"),
                    col("bank"),
                    to_date("installed_date").alias("installed_date"),
                    col("is_active"))
                 .filter(col("atm_id").isNotNull())
                 .dropDuplicates(["atm_id"]))

    else:
        raise ValueError(f"unknown table {t}")

    table_map = {
        "transactions":   "atm_transactions",
        "cash":           "atm_cash_levels",
        "faults":         "atm_fault_events",
        "replenishments": "replenishments",
        "dim":            "dim_atm_network",
    }
    target = table_map[t]

    print(f"  writing to silver.{target} ...")
    write_pg(out, target, mode="overwrite")
    print(f"=== {t} DONE ===")
    spark.stop()

if __name__ == "__main__":
    main()
