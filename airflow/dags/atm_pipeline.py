"""ATM Network Analytics - end-to-end pipeline."""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

SPARK_PKGS = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3"
SPARK_IVY  = "/tmp/.ivy"
PG_JAR     = "/opt/spark/jars/postgresql-42.7.4.jar"

SPARK_SUBMIT = (
    "docker exec atm-spark /opt/spark/bin/spark-submit "
    f"--conf spark.jars.ivy={SPARK_IVY} "
)

default_args = {
    "owner": "atm-ops",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="atm_pipeline",
    description="Kafka -> Spark -> Postgres -> dbt gold",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["atm", "spark", "dbt"],
) as dag:

    t1_producer = BashOperator(
        task_id="produce_to_kafka",
        bash_command=(
            "cd /opt/producer && "
            "KAFKA_BROKER=kafka:29092 "
            "python3 produce_to_kafka.py --limit 5000"
        ),
    )

    t2_bronze_tx = BashOperator(
        task_id="bronze_transactions",
        bash_command=(
            f"{SPARK_SUBMIT}"
            f"--packages {SPARK_PKGS} "
            "/opt/spark-jobs/streaming/kafka_to_bronze.py "
            "--topic atm.transactions"
        ),
    )

    t3_bronze_rest = BashOperator(
        task_id="bronze_other_topics",
        bash_command=(
            f"for t in atm.dim atm.cash atm.faults atm.replenishments; do "
            f"{SPARK_SUBMIT}--packages {SPARK_PKGS} "
            "/opt/spark-jobs/streaming/kafka_to_bronze.py --topic $t; "
            "done"
        ),
    )

    t4_silver = BashOperator(
        task_id="silver_to_postgres",
        bash_command=(
            f"for t in dim transactions cash faults replenishments; do "
            f"{SPARK_SUBMIT}--jars {PG_JAR} "
            "/opt/spark-jobs/batch/bronze_to_silver.py --table $t; "
            "done"
        ),
    )

    t5_dbt_staging = BashOperator(
        task_id="dbt_staging",
        bash_command=(
            "cd /opt/dbt/atm_project && "
            "dbt run --select staging --profiles-dir /opt/airflow/dbt_profiles"
        ),
    )

    t6_dbt_marts = BashOperator(
        task_id="dbt_marts",
        bash_command=(
            "cd /opt/dbt/atm_project && "
            "dbt run --select marts --profiles-dir /opt/airflow/dbt_profiles"
        ),
    )

    t1_producer >> t2_bronze_tx >> t3_bronze_rest >> t4_silver >> t5_dbt_staging >> t6_dbt_marts
