"""
Streams ATM CSVs into Kafka topics.
Usage:
    python produce_to_kafka.py                    # all rows, all topics
    python produce_to_kafka.py --limit 5000       # first 5000 rows per topic
    python produce_to_kafka.py --speed 500        # 500 msgs/sec
    python produce_to_kafka.py --topic atm.faults # one topic only
"""
import argparse, json, os, sys, time
from datetime import datetime
import pandas as pd
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

BROKER   = os.getenv("KAFKA_BROKER", "localhost:9092")
RAW_DIR  = os.getenv("RAW_DIR", "/mnt/c/dev/atm/data/raw")

TOPICS = [
    ("atm.dim",             "dim_atm_network.csv"),
    ("atm.transactions",    "fct_atm_transactions.csv"),
    ("atm.cash",            "fct_atm_cash_levels.csv"),
    ("atm.faults",          "fct_atm_faults.csv"),
    ("atm.replenishments",  "fct_replenishments.csv"),
]

# ---------- helpers ----------
def clean(v):
    if pd.isna(v): return None
    if isinstance(v, pd.Timestamp): return v.isoformat()
    if isinstance(v, bool): return bool(v)
    try:
        if hasattr(v, "item"): return v.item()
    except Exception:
        pass
    return v

def row_to_json(row):
    return json.dumps({k: clean(v) for k, v in row.items()}, default=str)

# ---------- topic creation ----------
def ensure_topics(admin, names):
    existing = set(admin.list_topics())
    to_create = [n for n in names if n not in existing]
    if not to_create:
        print(f"All {len(names)} topics already exist.")
        return
    new = [NewTopic(name=n, num_partitions=3, replication_factor=1) for n in to_create]
    try:
        admin.create_topics(new_topics=new, validate_only=False)
        print(f"Created topics: {to_create}")
    except TopicAlreadyExistsError:
        pass
    except Exception as e:
        print(f"Topic creation warning: {e}")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="rows per topic")
    ap.add_argument("--speed", type=int, default=0,    help="msgs/sec (0 = max)")
    ap.add_argument("--topic", type=str, default=None, help="single topic name")
    ap.add_argument("--broker", type=str, default=BROKER)
    args = ap.parse_args()

    print(f"Connecting to Kafka at {args.broker} ...")
    admin = KafkaAdminClient(bootstrap_servers=args.broker, client_id="atm-admin")
    ensure_topics(admin, [t for t,_ in TOPICS])
    admin.close()

    producer = KafkaProducer(
        bootstrap_servers=args.broker,
        value_serializer=lambda v: v.encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        linger_ms=5,
        compression_type="gzip",
    )
    print("Producer connected.\n")

    total_sent = 0
    for topic, fname in TOPICS:
        if args.topic and topic != args.topic:
            continue
        path = os.path.join(RAW_DIR, fname)
        if not os.path.exists(path):
            print(f"SKIP {topic}  (missing {fname})")
            continue

        print(f"--- Streaming {fname} -> {topic} ---")
        t0 = time.time()
        sent = 0
        # read in chunks for large files
        reader = pd.read_csv(path, chunksize=10000)
        for chunk in reader:
            if args.limit and sent >= args.limit:
                break
            if args.limit:
                chunk = chunk.iloc[: args.limit - sent]
            for _, row in chunk.iterrows():
                key = str(row.get("atm_id", ""))
                producer.send(topic, key=key, value=row_to_json(row))
                sent += 1
                if args.speed and sent % args.speed == 0:
                    producer.flush()
                    time.sleep(1)
            producer.flush()
            print(f"    ... {sent:>10,} rows", end="\r")

        dt = time.time() - t0
        rate = sent / dt if dt > 0 else 0
        print(f"    DONE {sent:>10,} rows in {dt:>5.1f}s  ({rate:,.0f} msg/s)")
        total_sent += sent

    producer.flush()
    producer.close()
    print(f"\nTotal messages produced: {total_sent:,}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
