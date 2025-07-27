from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
import os
import sys

# 상위 디렉토리를 path에 추가하여 다른 모듈을 import할 수 있도록 함
sys.path.insert(0, "/opt/airflow")
from config.config import SPARK_CONTAINER, SPARK_SUBMIT_PATH, SPARK_MASTER_URL, SPARK_JARS_PATH, SPARK_APP_PATH

# Default args from config
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2025, 7, 24, 0, 0),
    "retries": 3,
    "retry_delay": timedelta(minutes=3),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=8),
}

# DAG 정의
dag = DAG(
    dag_id="calculate_anomaly_range_dag",
    default_args=default_args,
    description="Run spark-submit inside spark-master container (Quantile, IQR)",
    schedule_interval= "@hourly",
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["spark", "anomaly", "batch"]
)

# spark-submit 명령 구성
bash_command = f"""
docker exec {SPARK_CONTAINER} {SPARK_SUBMIT_PATH} \
--master {SPARK_MASTER_URL} \
--jars {SPARK_JARS_PATH} \
{SPARK_APP_PATH}
""".strip()

# 작업 정의
run_spark_job = BashOperator(
    task_id="run_spark_anomaly_range_job",
    bash_command=bash_command,
    dag=dag,
)

run_spark_job
