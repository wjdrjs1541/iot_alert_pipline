import os
import json
import time
import binascii
import logging
import psycopg2
from kafka import KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

# 상위 디렉토리를 path에 추가하여 다른 모듈을 import할 수 있도록 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import KAFKA_BROKERS, KAFKA_TOPIC, GROUP_ID, EMAIL_SENDER, EMAIL_RECEIVER, EMAIL_PASSWORD, EMAIL_SMTP_PORT, EMAIL_SMTP_SERVER, POSTGRESQL_HOST, POSTGRESQL_DB, POSTGRESQL_USER, POSTGRESQL_PASSWORD, POSTGRESQL_PORT


def send_email_alert(subject: str, body: str):

    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = EMAIL_SENDER
    message["To"] = EMAIL_RECEIVER

    message.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message.as_string())
        logger.info("📧 이상치 이메일 알림 전송 완료")
    except Exception as e:
        logger.error(f"🚨 이메일 전송 실패: {e}")


# ✅ 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_anomaly_bounds(cursor):
    cursor.execute("""
        SELECT method, min_temp, max_temp, min_humidity, max_humidity 
        FROM anomaly_range 
        WHERE method IN ('quantile', 'iqr')
        ORDER BY id DESC
    """)
    results = cursor.fetchall()
    bounds = {}
    for row in results:
        method, min_t, max_t, min_h, max_h = row
        if method not in bounds:
            bounds[method] = (min_t, max_t, min_h, max_h)
    return bounds


def execute_with_retry(cursor, query, values, retries=3, delay=1):
    for attempt in range(1, retries + 1):
        try:
            cursor.execute(query, values)
            conn.commit()
            return True
        except psycopg2.Error as e:
            logger.error(f"🚨 DB 저장 실패 (시도 {attempt}/{retries}): {e}")
            time.sleep(delay)
    return False


# ✅ PostgreSQL 연결 (재시도 포함)
while True:
    try:
        conn = psycopg2.connect(
            host= POSTGRESQL_HOST,
            database= POSTGRESQL_DB,
            user= POSTGRESQL_USER,
            password= POSTGRESQL_PASSWORD,
            port= POSTGRESQL_PORT
        )
        cursor = conn.cursor()
        break
    except Exception as e:
        logger.error(f"🚨 PostgreSQL 연결 실패, 재시도 중... 에러: {e}")
        time.sleep(3)


# ✅ Kafka Consumer 초기화
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BROKERS,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id=GROUP_ID,
    session_timeout_ms=10000,
    heartbeat_interval_ms=3000,
)

logger.info("📡 Kafka Consumer 시작됨...")

for msg in consumer:
    data = msg.value

    if 'mqtt_msg' not in data:
        logger.error(f"🚨 mqtt_msg 누락된 메시지: {data}")
        continue

    try:
        decoded_msg = binascii.unhexlify(data['mqtt_msg']).decode('ascii').strip()
        temperature_str, humidity_str = decoded_msg.split()
        temperature = float(temperature_str)
        humidity = float(humidity_str)
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError) as e:
        logger.error(f"🚨 mqtt_msg 디코딩 실패 또는 포맷 오류: {data.get('mqtt_msg')} / 에러: {e}")
        continue

    if not execute_with_retry(
        cursor,
        "INSERT INTO sensor_data (machine_id, temperature, humidity, sent_time) VALUES (%s, %s, %s, %s)",
        (data['machine_id'], temperature, humidity, data['sent_time']),
        retries=3,
        delay=2
    ):
        logger.error(f"🚨 DB 저장 3회 실패, 해당 데이터 스킵: {data}")
        continue

    try:
        bounds_dict = get_all_anomaly_bounds(cursor)
    except Exception as e:
        logger.error(f"🚨 이상치 기준 조회 실패: {e}")
        continue

    for method, (min_temp, max_temp, min_hum, max_hum) in bounds_dict.items():
        is_temp_anomaly = not (min_temp <= temperature <= max_temp) if min_temp is not None and max_temp is not None else False
        is_hum_anomaly = not (min_hum <= humidity <= max_hum) if min_hum is not None and max_hum is not None else False

        if is_temp_anomaly or is_hum_anomaly:
            logger.warning(f"🚨 이상치 탐지됨! [method={method}] machine_id={data['machine_id']}, temp={temperature}, hum={humidity}")
            # ✅ 이메일 전송
            subject = f"[이상치 알림] {method.upper()} - machine_id: {data['machine_id']}"
            body = f"""
            [이상치 감지]
            - 감지 방식: {method}
            - Machine ID: {data['machine_id']}
            - 온도: {temperature}
            - 습도: {humidity}
            - 전송 시각: {data['sent_time']}
            """
            send_email_alert(subject, body)
            
            execute_with_retry(
                cursor,
                "INSERT INTO anomaly_log (machine_id, temperature, humidity, sent_time, temp_anomaly, hum_anomaly, method) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (data['machine_id'], temperature, humidity, data['sent_time'], is_temp_anomaly, is_hum_anomaly, method)
            )
        else:
            logger.info(f"✅ 정상 데이터 [method={method}]: machine_id={data['machine_id']}, temperature={temperature}, humidity={humidity}")
