from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 7, 20, 0, 0),
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
}

dag = DAG(
    'calculate_anomaly_range_dag',
    default_args=default_args,
    description='spark-master 컨테이너에서 직접 spark-submit 실행 (PyOD 이상치 기준)',
    schedule_interval="*/10 * * * *",  # 10분마다 실행
    catchup=False,
    is_paused_upon_creation=False,  # 자동 시작
    tags=['spark', 'anomaly', 'batch']
)

run_spark_job = BashOperator(
    task_id='run_spark_anomaly_range_job',
    bash_command="""
    docker exec spark-master /opt/bitnami/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /opt/spark/jars/postgresql-42.7.3.jar \
    /opt/spark-apps/calculate_anomaly_range.py
    """,
    dag=dag,
)

run_spark_job
