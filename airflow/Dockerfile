FROM apache/airflow:2.10.0-python3.11

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends docker.io curl \
 && rm -rf /var/lib/apt/lists/*
USER airflow

RUN pip uninstall -y dbt-oss dbt-semantic-interfaces 2>/dev/null || true
RUN pip install --no-cache-dir \
      'dbt-core==1.8.2' \
      'dbt-postgres==1.8.2' \
      'kafka-python' \
      'pandas' \
      'psycopg2-binary'
