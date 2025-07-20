from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
import pandas as pd
from pyod.models.iforest import IForest
from datetime import datetime


# ✅ Spark Session
spark = SparkSession.builder \
    .appName("IoT Anomaly Range Calculator") \
    .config("spark.jars", "/opt/spark/jars/postgresql-42.7.3.jar") \
    .getOrCreate()


# ✅ PostgreSQL -> Spark 읽기
sensor_df = spark.read \
    .format("jdbc") \
    .option("url", "jdbc:postgresql://postgresql:5432/iot_data") \
    .option("dbtable", "sensor_data") \
    .option("user", "postgres") \
    .option("password", "postgres") \
    .option("driver", "org.postgresql.Driver") \
    .load()


# ✅ machine_id별 IForest min/max 계산 함수 (pandas_udf 사용 X)
def calc_bounds_udf(pdf: pd.DataFrame) -> pd.DataFrame:
    machine_id = pdf["machine_id"].iloc[0]

    temp_model = IForest()
    temp_X = pdf["temperature"].values.reshape(-1, 1)
    temp_model.fit(temp_X)
    min_temp = temp_X[temp_model.decision_scores_.argmin()][0]
    max_temp = temp_X[temp_model.decision_scores_.argmax()][0]

    hum_model = IForest()
    hum_X = pdf["humidity"].values.reshape(-1, 1)
    hum_model.fit(hum_X)
    min_humidity = hum_X[hum_model.decision_scores_.argmin()][0]
    max_humidity = hum_X[hum_model.decision_scores_.argmax()][0]

    return pd.DataFrame([{
        "machine_id": machine_id,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "min_humidity": min_humidity,
        "max_humidity": max_humidity
    }])


# ✅ machine_id별 실행
result_df = sensor_df.groupBy("machine_id").applyInPandas(
    calc_bounds_udf,
    schema=StructType([
        StructField("machine_id", StringType()),
        StructField("min_temp", DoubleType()),
        StructField("max_temp", DoubleType()),
        StructField("min_humidity", DoubleType()),
        StructField("max_humidity", DoubleType())
    ])
)


# ✅ updated_at 컬럼 추가
from pyspark.sql.functions import current_timestamp
final_df = result_df.withColumn("updated_at", current_timestamp())


# ✅ PostgreSQL 저장 (append)
final_df.write \
    .format("jdbc") \
    .option("url", "jdbc:postgresql://postgresql:5432/iot_data") \
    .option("dbtable", "anomaly_range") \
    .option("user", "postgres") \
    .option("password", "postgres") \
    .option("driver", "org.postgresql.Driver") \
    .mode("append") \
    .save()


spark.stop()
