#!/bin/bash
docker rm -f atm-mlflow 2>/dev/null
mkdir -p /mnt/c/dev/atm/mlflow/artifacts /mnt/c/dev/atm/ml /mnt/c/dev/atm/alerts
docker run -d \
  --name atm-mlflow \
  --network docker_default \
  -p 5000:5000 \
  -v /mnt/c/dev/atm/mlflow:/mlflow \
  -v /mnt/c/dev/atm/ml:/ml \
  -v /mnt/c/dev/atm/alerts:/alerts \
  -w /ml \
  atm-mlflow:1.0 \
  mlflow server --backend-store-uri sqlite:////mlflow/mlflow.db \
                --default-artifact-root /mlflow/artifacts \
                --host 0.0.0.0 --port 5000
echo "MLflow at http://localhost:5000 (ready in ~15s)"
