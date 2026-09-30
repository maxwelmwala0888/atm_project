"""Consume atm.transactions from Kafka and insert into Postgres live table."""
import json, time, os, signal, sys
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import execute_batch

BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
DB = dict(host="localhost", dbname="atm_warehouse", user="atm", password="atm_pass")

running = True
def stop(*a):
    global running
    running = False
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

consumer = KafkaConsumer(
    "atm.transactions",
    bootstrap_servers=BROKER,
    value_deserializer=lambda m: json.loads(m.decode()),
    auto_offset_reset="latest",
    enable_auto_commit=True,
    group_id="live-pg-sink",
)
print("Consumer ready — waiting for messages...", flush=True)

conn = psycopg2.connect(**DB)
conn.autocommit = True
cur = conn.cursor()

batch, last_commit = [], time.time()
BATCH_SIZE = 20
COMMIT_EVERY = 2.0

def flush():
    global batch, last_commit
    if not batch:
        return
    execute_batch(cur, """
        INSERT INTO live.atm_transactions
            (atm_id, event_ts, tx_type, amount_mwk, card_type, success)
        VALUES (%s, NOW(), %s, %s, %s, %s)
    """, batch)
    print(f"  +{len(batch)} rows -> live.atm_transactions", flush=True)
    batch = []
    last_commit = time.time()

try:
    while running:
        msg_pack = consumer.poll(timeout_ms=500)
        for tp, msgs in msg_pack.items():
            for m in msgs:
                d = m.value
                batch.append((
                    d.get("atm_id"),
                    d.get("tx_type"),
                    int(d.get("amount_mwk") or 0),
                    d.get("card_type"),
                    bool(d.get("success")),
                ))
                if len(batch) >= BATCH_SIZE:
                    flush()
        if batch and (time.time() - last_commit) >= COMMIT_EVERY:
            flush()
finally:
    flush()
    consumer.close()
    conn.close()
    print("Consumer stopped.", flush=True)
