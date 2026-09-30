#!/bin/bash
docker rm -f atm-airflow 2>/dev/null
docker run -d \
  --name atm-airflow \
  --network docker_default \
  -p 8090:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /mnt/c/dev/atm/airflow/dags:/opt/airflow/dags \
  -v /mnt/c/dev/atm/airflow/profiles.yml:/opt/airflow/dbt_profiles/profiles.yml:ro \
  -v /mnt/c/dev/atm/dbt:/opt/dbt \
  -v /mnt/c/dev/atm/spark:/opt/spark-jobs \
  -v /mnt/c/dev/atm/producer:/opt/producer \
  -v /mnt/c/dev/atm/logs:/opt/logs \
  -e AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://atm:atm_pass@postgres:5432/airflow \
  -e AIRFLOW__CORE__EXECUTOR=LocalExecutor \
  -e AIRFLOW__CORE__LOAD_EXAMPLES=False \
  -e KAFKA_BROKER=kafka:29092 \
  atm-airflow:1.0 \
  bash -c "pip install -q kafka-python pandas && airflow standalone"
echo "Airflow starting on http://localhost:8090 (admin/admin)"
