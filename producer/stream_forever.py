"""Continuously streams transaction CSVs into Kafka."""
import time, json, os, random, signal, sys
import pandas as pd
from kafka import KafkaProducer

BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
RAW = "/mnt/c/dev/atm/data/raw"
RATE = float(os.getenv("MSG_PER_SEC", "20"))
LIMIT = int(os.getenv("LIMIT", "100000"))

producer = KafkaProducer(
    bootstrap_servers=BROKER,
    value_serializer=lambda v: json.dumps(v, default=str).encode(),
    key_serializer=lambda k: str(k).encode() if k else None,
    compression_type="gzip",
)
print(f"Streaming at {RATE} msg/s. Ctrl+C to stop.", flush=True)

tx = pd.read_csv(f"{RAW}/fct_atm_transactions.csv", nrows=LIMIT)
tx = tx.sample(frac=1).reset_index(drop=True)
print(f"Loaded {len(tx):,} rows to replay", flush=True)

delay = 1.0 / RATE
i = 0
try:
    while True:
        row = tx.iloc[i % len(tx)]
        payload = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        producer.send("atm.transactions", key=row["atm_id"], value=payload)
        i += 1
        if i % 50 == 0:
            producer.flush()
        time.sleep(delay)
except KeyboardInterrupt:
    producer.flush()
    producer.close()
    print(f"\nSent {i:,} messages.")
