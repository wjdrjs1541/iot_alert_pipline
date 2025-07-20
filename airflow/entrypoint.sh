#!/bin/bash
export PATH="/home/airflow/.local/bin:$PATH"

airflow db init

airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@admin.com || true

airflow connections add 'spark_default' \
    --conn-type 'spark' \
    --conn-host 'spark://spark-master:7077' || true

exec "$@"
