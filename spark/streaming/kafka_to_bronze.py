"""Spark Structured Streaming: Kafka -> Bronze Parquet"""
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    BooleanType, IntegerType, DoubleType
)

BROKER = "kafka:29092"
BRONZE = "/data/bronze"

SCHEMAS = {
    "atm.dim": StructType([
        StructField("atm_id", StringType()),
        StructField("city", StringType()),
        StructField("region", StringType()),
        StructField("latitude", DoubleType()),
        StructField("longitude", DoubleType()),
        StructField("atm_type", StringType()),
        StructField("atm_model", StringType()),
        StructField("bank", StringType()),
        StructField("installed_date", StringType()),
        StructField("is_active", BooleanType()),
    ]),
    "atm.transactions": StructType([
        StructField("atm_id", StringType()),
        StructField("timestamp", StringType()),
        StructField("tx_type", StringType()),
        StructField("amount_mwk", LongType()),
        StructField("card_type", StringType()),
        StructField("success", BooleanType()),
    ]),
    "atm.cash": StructType([
        StructField("atm_id", StringType()),
        StructField("timestamp", StringType()),
        StructField("cash_level_mwk", LongType()),
        StructField("hourly_withdrawal_mwk", LongType()),
        StructField("was_refilled", BooleanType()),
        StructField("below_threshold", BooleanType()),
    ]),
    "atm.faults": StructType([
        StructField("atm_id", StringType()),
        StructField("event_timestamp", StringType()),
        StructField("fault_type", StringType()),
        StructField("component", StringType()),
        StructField("event_class", StringType()),
        StructField("duration_mins", IntegerType()),
        StructField("resolved", BooleanType()),
        StructField("fault_occurred", IntegerType()),
    ]),
    "atm.replenishments": StructType([
        StructField("atm_id", StringType()),
        StructField("refill_timestamp", StringType()),
        StructField("amount_loaded_mwk", LongType()),
        StructField("cit_team", StringType()),
        StructField("downtime_mins", IntegerType()),
    ]),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, choices=list(SCHEMAS.keys()))
    ap.add_argument("--broker", default=BROKER)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    topic = args.topic
    safe  = topic.replace(".", "_")
    out_dir = args.output or f"{BRONZE}/{safe}"
    schema  = SCHEMAS[topic]

    spark = (SparkSession.builder
             .appName(f"kafka_to_bronze_{safe}")
             .config("spark.sql.shuffle.partitions", "4")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    print(f"[{topic}] Reading from {args.broker} ...")

    raw = (spark.readStream
           .format("kafka")
           .option("kafka.bootstrap.servers", args.broker)
           .option("subscribe", topic)
           .option("startingOffsets", "earliest")
           .option("failOnDataLoss", "false")
           .option("maxOffsetsPerTrigger", 200000)
           .load())

    parsed = (raw
              .selectExpr("CAST(value AS STRING) AS json_str",
                          "timestamp AS kafka_ts",
                          "partition", "offset")
              .select(from_json(col("json_str"), schema).alias("d"),
                      col("kafka_ts"), col("partition"), col("offset"))
              .select("d.*", "kafka_ts", "partition", "offset")
              .withColumn("ingested_at", current_timestamp()))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, choices=list(SCHEMAS.keys()))
    ap.add_argument("--broker", default=BROKER)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    topic = args.topic
    safe  = topic.replace(".", "_")
    out_dir = args.output or f"{BRONZE}/{safe}"
    schema  = SCHEMAS[topic]

    spark = (SparkSession.builder
             .appName(f"kafka_to_bronze_{safe}")
             .config("spark.sql.shuffle.partitions", "4")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    print(f"[{topic}] Reading from {args.broker} ...")

    raw = (spark.readStream
           .format("kafka")
           .option("kafka.bootstrap.servers", args.broker)
           .option("subscribe", topic)
           .option("startingOffsets", "earliest")
           .option("failOnDataLoss", "false")
           .option("maxOffsetsPerTrigger", 200000)
           .load())

    parsed = (raw
              .selectExpr("CAST(value AS STRING) AS json_str",
                          "timestamp AS kafka_ts",
                          "partition", "offset")
              .select(from_json(col("json_str"), schema).alias("d"),
                      col("kafka_ts"), col("partition"), col("offset"))
              .select("d.*", "kafka_ts", "partition", "offset")
              .withColumn("ingested_at", current_timestamp()))

    query = (parsed.writeStream
             .format("parquet")
             .option("path", out_dir)
             .option("checkpointLocation", f"{BRONZE}/_checkpoints/{safe}")
             .trigger(availableNow=True)
             .start())

    print(f"[{topic}] Streaming -> {out_dir}")
    query.awaitTermination()
    print(f"[{topic}] DONE.")
    spark.stop()

if __name__ == "__main__":
    main()
