from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
import yaml
import os

def load_config(filename: str) -> dict:
    """
    Load YAML configuration file from Airflow container's config directory.
    """
    config_path = f"/opt/airflow/config/{filename}"
    with open(config_path, "r") as file:
        return yaml.safe_load(file)
    
spark_config = load_config("spark_config.yaml")["spark"]
airflow_config = load_config("airflow_config.yaml")["airflow"]

# Default args from config
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2025, 7, 24, 0, 0),
    "retries": airflow_config["retries"],
    "retry_delay": timedelta(minutes=airflow_config["retry_delay_minutes"]),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=airflow_config["max_retry_delay_minutes"]),
    "execution_timeout": timedelta(minutes=airflow_config["execution_timeout_minutes"]),
}

# DAG 정의
dag = DAG(
    dag_id="calculate_anomaly_range_dag",
    default_args=default_args,
    description="Run spark-submit inside spark-master container (Quantile, IQR)",
    schedule_interval=airflow_config["schedule_interval"],
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["spark", "anomaly", "batch"]
)

# spark-submit 명령 구성
bash_command = f"""
docker exec {spark_config['container']} {spark_config['submit_path']} \
--master {spark_config['master_url']} \
--jars {spark_config['jars']} \
{spark_config['app']}
""".strip()

# 작업 정의
run_spark_job = BashOperator(
    task_id="run_spark_anomaly_range_job",
    bash_command=bash_command,
    dag=dag,
)

run_spark_job
