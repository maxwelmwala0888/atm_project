#!/bin/bash
docker rm -f atm-spark 2>/dev/null
mkdir -p /root/atm_data/bronze /root/atm_data/silver /root/atm_data/gold /root/atm_data/_checkpoints
docker run -d \
  --name atm-spark \
  --network docker_default \
  -v /root/atm_data:/data \
  -v /mnt/c/dev/atm/spark:/opt/spark-jobs \
  -e SPARK_NO_DAEMONIZE=true \
  -e PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/spark/bin \
  apache/spark:3.5.3 \
  tail -f /dev/null
echo "atm-spark started"
docker ps --filter name=atm-spark
