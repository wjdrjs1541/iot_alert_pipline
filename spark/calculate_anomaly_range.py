from pyspark.sql import SparkSession
from pyspark.sql.functions import expr, current_timestamp
from sqlalchemy import create_engine, text
import os
import sys

sys.path.insert(0, "/opt/airflow")
from config.config import POSTGRESQL_HOST, POSTGRESQL_DB, POSTGRESQL_USER, POSTGRESQL_PASSWORD, POSTGRESQL_PORT


# ✅ Spark 세션 생성
spark = SparkSession.builder \
    .appName("IoT Anomaly Range Calculator - Spark Quantile & IQR") \
    .config("spark.jars", "/opt/spark/jars/postgresql-42.7.3.jar") \
    .getOrCreate()

# ✅ PostgreSQL → Spark 로드
sensor_df = spark.read \
    .format("jdbc") \
    .option("url", f"jdbc:postgresql://{POSTGRESQL_HOST}:{POSTGRESQL_PORT}/{POSTGRESQL_DB}") \
    .option("dbtable", "(SELECT * FROM sensor_data WHERE sent_time >= current_timestamp - interval '1 day') AS recent") \
    .option("user", POSTGRESQL_USER) \
    .option("password", POSTGRESQL_PASSWORD) \
    .option("driver", "org.postgresql.Driver") \
    .load()

sensor_df.createOrReplaceTempView("sensor_data")

# ✅ Quantile 방식
quantile_df = spark.sql("""
    SELECT
        machine_id,
        percentile_approx(temperature, 0.001) AS min_temp,
        percentile_approx(temperature, 0.999) AS max_temp,
        percentile_approx(humidity, 0.001) AS min_humidity,
        percentile_approx(humidity, 0.999) AS max_humidity,
        'quantile' AS method,
        current_timestamp() AS updated_at
    FROM sensor_data
    GROUP BY machine_id
""")

# ✅ IQR 방식
iqr_base = spark.sql("""
    SELECT
        machine_id,
        percentile_approx(temperature, 0.25) AS q1_temp,
        percentile_approx(temperature, 0.75) AS q3_temp,
        percentile_approx(humidity, 0.25) AS q1_hum,
        percentile_approx(humidity, 0.75) AS q3_hum
    FROM sensor_data
    GROUP BY machine_id
""")

iqr_df = iqr_base.selectExpr(
    "machine_id",
    "q1_temp - 10.0 * (q3_temp - q1_temp) AS min_temp",
    "q3_temp + 10.0 * (q3_temp - q1_temp) AS max_temp",
    "q1_hum - 10.0 * (q3_hum - q1_hum) AS min_humidity",
    "q3_hum + 10.0 * (q3_hum - q1_hum) AS max_humidity",
    "'iqr' AS method",
    "current_timestamp() AS updated_at"
)

# ✅ 결과 병합
final_df = quantile_df.unionByName(iqr_df)

# ✅ PostgreSQL에 임시 테이블로 저장
temp_table = "temp_anomaly_range"
final_df.write \
    .format("jdbc") \
    .option("url", f"jdbc:postgresql://{POSTGRESQL_HOST}:{POSTGRESQL_PORT}/{POSTGRESQL_DB}") \
    .option("dbtable", temp_table) \
    .option("user", POSTGRESQL_USER) \
    .option("password", POSTGRESQL_PASSWORD) \
    .option("driver", "org.postgresql.Driver") \
    .mode("overwrite") \
    .save()

# ✅ anomaly_range 테이블에 UPSERT
engine = create_engine(f"postgresql+psycopg2://{POSTGRESQL_USER}:{POSTGRESQL_PASSWORD}@{POSTGRESQL_HOST}:{POSTGRESQL_PORT}/{POSTGRESQL_DB}")

with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO anomaly_range (machine_id, min_temp, max_temp, min_humidity, max_humidity, method, updated_at)
        SELECT machine_id, min_temp, max_temp, min_humidity, max_humidity, method, updated_at
        FROM temp_anomaly_range
        ON CONFLICT (machine_id, method)
        DO UPDATE SET
            min_temp = EXCLUDED.min_temp,
            max_temp = EXCLUDED.max_temp,
            min_humidity = EXCLUDED.min_humidity,
            max_humidity = EXCLUDED.max_humidity,
            updated_at = EXCLUDED.updated_at;
    """))
    conn.commit()

    print("✅ UPSERT 완료: anomaly_range 테이블 최신화됨")


spark.stop()