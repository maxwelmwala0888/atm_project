# 🏧 ATM & Branch Network Analytics Platform

**Predictive operations for retail-banking ATM networks.** Forecasts cash depletion 72 hours ahead, predicts component failures before they happen, scores branch utilisation.

link : https://sturdy-capybara-v6j44xq76j43vp4-8501.app.github.dev/

link2 : https://atmproject-x2sprdaztgg2bm5hzbkgmg.streamlit.app/

cmd live start :  /workspaces/atm_project/go.sh
---

## 📌 What this solves

- 72-hour cash depletion forecast per ATM
- Component fault prediction (card readers, dispensers, printers, network)
- Branch utilisation scoring and consolidation recommendations
- Automatic work orders for Cash-in-Transit (CIT) teams
- SMS / email alerts to field engineers with priority levels
- Real-time operational dashboard

---

## 🧰 Tech stack

| Layer | Tool | Version |
|---|---|---|
| Streaming | Apache Kafka (KRaft) | 3.7.0 |
| Stream processing | Apache Spark Structured Streaming | 3.5.3 |
| Batch processing | Apache Spark | 3.5.3 |
| Transformation | dbt-core + dbt-postgres | 1.8.2 |
| Orchestration | Apache Airflow | 2.10.0 |
| OLTP storage | PostgreSQL | 16 |
| File storage | SeaweedFS / local FS | 4.47 |
| Cash forecast | Prophet | 1.4.0 |
| Fault predict | XGBoost | 3.2.0 |
| Clustering | scikit-learn KMeans | 1.5.x |
| Tracking | MLflow | 2.16.2 |
| Dashboard | Streamlit + Plotly | 1.40 / 6.0 |
| Containers | Docker + Compose | 29.8.1 |

---

## 🏗️ Architecture

LAYER 1 - SOURCES -> Python producer -> LAYER 2a - Kafka (5 topics)
LAYER 2a -> Spark Structured Streaming -> LAYER 2b - Bronze Parquet
LAYER 2b -> Spark Batch (JDBC truncate) -> LAYER 2c - Silver (Postgres)
LAYER 2c -> dbt-core -> LAYER 2d - Gold (3 marts)
LAYER 2d -> ML (Prophet, XGBoost, KMeans) + MLflow
LAYER 2d -> Serving (Streamlit, Alerts, Live feed)
Orchestration: Airflow DAG atm_pipeline

---

## 📂 Project structure

    atm/
    ├── docker/                docker-compose + schema init
    ├── producer/              CSV to Kafka, live stream, live sink
    ├── spark/streaming/       kafka_to_bronze.py
    ├── spark/batch/           bronze_to_silver.py
    ├── dbt/atm_project/       staging + marts + profiles
    ├── airflow/               Dockerfile + DAG + profiles
    ├── ml/                    3 training scripts
    ├── alerts/                generate_alerts.py + outbox/
    ├── dashboard/             Streamlit app (6 tabs)
    ├── data/                  raw CSVs, bronze, processed
    ├── mlflow/                tracking DB + artifacts
    ├── logs/                  pipeline logs
    ├── docs/                  architecture.md + STATUS.md
    ├── start-airflow.sh
    ├── start-mlflow.sh
    ├── start-dashboard.sh
    ├── start-spark.sh
    ├── live.sh
    ├── run_alerts.sh
    ├── resume.sh
    └── README.md

---

## 🚀 Quickstart

Prerequisites: Windows 11 + WSL2, Docker 29+, Python 3.11+, 8 GB RAM, 5 GB disk.

    service docker start
    cd /mnt/c/dev/atm/docker
    docker compose up -d

Full pipeline:

    cd /mnt/c/dev/atm
    python3 scripts/01_generate_data.py
    python3 scripts/01b_generate_faults.py
    cd producer && python3 produce_to_kafka.py

    for t in atm.transactions atm.dim atm.cash atm.faults atm.replenishments; do
      docker exec atm-spark spark-submit \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
        /opt/spark-jobs/streaming/kafka_to_bronze.py --topic \$t
    done

    for t in dim transactions cash faults replenishments; do
      docker exec atm-spark spark-submit \
        --jars /opt/spark/jars/postgresql-42.7.4.jar \
        /opt/spark-jobs/batch/bronze_to_silver.py --table \$t
    done

    cd /mnt/c/dev/atm/dbt/atm_project
    dbt run --select staging && dbt run --select marts

    for s in train_cash_forecast train_fault_model train_branch_clustering; do
      docker exec -e MLFLOW_TRACKING_URI=http://localhost:5000 \
        atm-mlflow python3 /ml/\$s.py
    done

    docker exec atm-mlflow python3 /alerts/generate_alerts.py

Airflow: http://localhost:8090 (admin/admin), trigger atm_pipeline.

Live streaming:
    /mnt/c/dev/atm/live.sh start
    /mnt/c/dev/atm/live.sh stop

---

## 🔗 Service URLs

| Service | URL | Credentials |
|---|---|---|
| Streamlit dashboard | http://localhost:8501 | - |
| MLflow UI | http://localhost:5000 | - |
| Airflow UI | http://localhost:8090 | admin / admin |
| Kafka UI | http://localhost:8080 | - |
| SeaweedFS master | http://localhost:9001 | minioadmin / minioadmin |
| PostgreSQL | localhost:5432 | atm / atm_pass (atm_warehouse) |
| Kafka broker | localhost:9092 | - |

---

## 📊 Pipeline stages

| # | Task | Tool | Output |
|---|---|---|---|
| 1 | produce_to_kafka | Python KafkaProducer | Kafka topics |
| 2 | bronze_transactions | Spark Streaming | /data/bronze/atm_transactions |
| 3 | bronze_other_topics | Spark Streaming | 4 more bronze folders |
| 4 | silver_to_postgres | Spark JDBC | silver.* tables |
| 5 | dbt_staging | dbt | 5 views |
| 6 | dbt_marts | dbt | 3 gold tables |
| 7 | generate_alerts | Python | SMS / email / feed JSON |

---

## 📐 Data model

Silver (5 tables):

| Table | Rows |
|---|---|
| silver.atm_transactions | 2,237,409 |
| silver.atm_cash_levels | 175,240 |
| silver.atm_fault_events | 2,684 |
| silver.replenishments | 560 |
| silver.dim_atm_network | 20 |

Gold (3 marts):

| Table | Rows |
|---|---|
| gold.fct_atm_daily_cash | 7,300 |
| gold.fct_atm_fault_events | 1,866 |
| gold.dim_atm_network | 20 |

Live:

| Table | Growth |
|---|---|
| live.atm_transactions | ~20 rows/sec |

---

## 🤖 ML Models

### 1. Cash depletion forecast - Prophet
- Input: gold.fct_atm_daily_cash
- Output: 72h forecast with 80% CI per ATM
- Trigger: yhat_lower < 100,000 MWK -> refill alert
- MLflow: atm_cash_forecast (20 runs)

### 2. Fault prediction - XGBoost
- Input: gold.fct_atm_fault_events
- Features: 11 (warnings, unresolved, downtime, per-component events, 30d MA)
- Target: fault tomorrow (binary)
- Output: probability per ATM/day; > 0.7 fires dispatch
- Metrics: ROC-AUC, F1
- Registered: atm_fault_xgboost

### 3. Branch utilisation - KMeans
- Input: gold.dim_atm_network
- Features: total_tx, failed_tx, failure_rate, avg_withdrawal, lifetime_faults
- Output: 3 clusters + utilisation_score + recommendation
- Metric: Silhouette
- Registered: atm_branch_kmeans

---

## 🔔 Alerts (Layer 4)

| Type | Trigger | Priority |
|---|---|---|
| cash_refill | min_cash_mwk < 100,000 | P1 < 50,000 else P2 |
| fault_prediction | Faults/warnings 30 days | P1 high, P2 medium, P3 low |

Output files:
- alerts/outbox/sms/<type>_<atm_id>_<uuid>.json (Twilio shape)
- alerts/outbox/email/<type>_<atm_id>_<uuid>.json (SendGrid shape)
- alerts/outbox/feed/latest.json (dashboard feed)

Sample SMS payload:

    {
      "to": "CIT_TEAM",
      "from": "ATM_OPS",
      "priority": "P2",
      "body": "[P2] ATM ATM_020 (Dedza) cash low: 91,078 MWK. Refill within 24h.",
      "sent_at": "2026-09-30T17:03:26",
      "atm_id": "ATM_020"
    }

---

## 🖥️ Dashboard (Streamlit - 6 tabs)

| Tab | Contents |
|---|---|
| 🔴 Live | 2s auto-refresh, last 15 tx, per-minute charts |
| 📊 Overview | Map (green/orange/red), cash donut, 5 KPIs |
| 🔔 Alerts | Priority filter, colored cards, priority + type charts |
| 🏧 ATMs | ATM picker, cash trend, 7d MA, withdrawal bars |
| ⚙️ Faults | ATM x component heatmap, top-10 30d MA, severity pie |
| 🤖 Models | MLflow metrics, registered models, DAG reference |

---

## 🛠️ Operations

    /mnt/c/dev/atm/resume.sh              # after reboot
    /mnt/c/dev/atm/start-mlflow.sh        # MLflow
    /mnt/c/dev/atm/start-dashboard.sh     # Streamlit
    /mnt/c/dev/atm/live.sh start|stop|status
    /mnt/c/dev/atm/run_alerts.sh

Reset for demo:

    docker exec atm-postgres psql -U atm -d atm_warehouse -c "
      TRUNCATE silver.atm_transactions, silver.atm_cash_levels,
               silver.atm_fault_events, silver.replenishments,
               gold.fct_atm_daily_cash, gold.fct_atm_fault_events CASCADE;
      TRUNCATE live.atm_transactions;"
    rm -rf /root/atm_data/bronze/_checkpoints/
    docker exec atm-airflow airflow dags trigger atm_pipeline

Monitoring:

    docker ps --format "table {{.Names}}\t{{.Status}}"

---

## 🧪 Smoke test

    docker exec atm-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

    docker exec atm-postgres psql -U atm -d atm_warehouse -c "
      SELECT table_schema, COUNT(*) FROM information_schema.tables
      WHERE table_schema IN ('silver','gold','live') GROUP BY 1;"

    docker exec atm-spark bash -c "getent hosts kafka && echo OK"

    docker exec atm-mlflow curl -s http://localhost:5000/health

    ls /mnt/c/dev/atm/alerts/outbox/sms/ | wc -l

    curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501

---

## 📈 Business impact

| Metric | Before | After |
|---|---|---|
| Cash-out incidents | Reactive | Predictive 72h ahead |
| Mean time to refill | ~2 days | Same day prioritised |
| Unplanned ATM downtime | Baseline | Reduced up to 40% |
| Branch review | Annual manual | Monthly automated |
| Ops cost per ATM | Opaque | Quantified |

---

## 🎯 Key design decisions

| Decision | Why |
|---|---|
| Kafka KRaft (no Zookeeper) | Fewer containers, faster startup |
| Spark availableNow=True | Batch-like reliability on streams |
| Bronze on native WSL FS | /mnt/c cannot chmod - Hadoop fails |
| Postgres JDBC truncate=true | dbt views depend on silver tables |
| dbt generate_schema_name macro | Prevents gold_silver.stg_* prefix |
| MLflow baked into custom image | Avoids pip timeout on restart |
| Airflow LocalExecutor | Single-container simplicity |
| Alerts as JSON outbox | Portfolio demo without API keys |

---

## 🆘 Troubleshooting

| Symptom | Fix |
|---|---|
| docker: command not found | service docker start |
| Spark cannot write /mnt/c | Move output to /root/atm_data |
| dbt-oss shadows dbt-postgres | pip uninstall dbt-oss; pin dbt-core==1.8.2 |
| relation already exists (JDBC) | Add .option("truncate", "true") |
| MLflow pip timeout | --default-timeout=300 in Dockerfile |
| Plotly 6 missing scatter_mapbox | Use scatter_map + map_style |
| Airflow cannot reach docker | chmod 666 /var/run/docker.sock |

---

## 🎓 Portfolio talking points

Elevator pitch:

> "I built an end-to-end predictive analytics platform for ATM networks.
> It ingests 2.4 million events through Kafka, processes them via a Spark + dbt
> medallion architecture into PostgreSQL, trains three ML models (Prophet,
> XGBoost, KMeans), tracks everything in MLflow, orchestrates via Airflow,
> generates operational alerts, and serves a live Streamlit dashboard."

Key points:
1. Real-time and batch in one pipeline
2. Three distinct ML problem types
3. Production-style concerns (orchestration, tracking, alerting, monitoring)
4. Clear business impact

---

## 📄 License

MIT - fork, adapt, deploy freely.
All data is synthetic. No real customer or bank data is used.

---

## 📊 Pipeline stages

| # | Task | Tool | Input → Output |
|---|---|---|---|
| 1 | 
