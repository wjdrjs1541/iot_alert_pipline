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
import threading
from datetime import datetime, timezone, timedelta
import random

# 상위 디렉토리를 path에 추가하여 다른 모듈을 import할 수 있도록 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import KAFKA_BROKERS, KAFKA_TOPIC, GROUP_ID, EMAIL_SENDER, EMAIL_RECEIVER, EMAIL_PASSWORD, EMAIL_SMTP_PORT, EMAIL_SMTP_SERVER, POSTGRESQL_HOST, POSTGRESQL_DB, POSTGRESQL_USER, POSTGRESQL_PASSWORD, POSTGRESQL_PORT, MAX_EMAIL_RECORD_AGE

last_email_sent = {}

def _send_email(subject: str, body: str):

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

def send_email_alert(subject: str, body: str, key: str, now: datetime):
    def _send_and_mark():
        _send_email(subject, body)
        last_email_sent[key] = now

    threading.Thread(target=_send_and_mark, daemon=True).start()

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
        #랜덤 변수 적용
        temperature *= random.uniform(0.99, 1.01)
        humidity *= random.uniform(0.99, 1.01)
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
            key = f"{data['machine_id']}::{method}"
            KST = timezone(timedelta(hours=9))
            now = datetime.now(KST)

            logger.warning(f"🚨 이상치 탐지됨! [method={method}] machine_id={data['machine_id']}, temp={temperature}, hum={humidity}")

            execute_with_retry(
                cursor,
                "INSERT INTO anomaly_log (machine_id, temperature, humidity, sent_time, temp_anomaly, hum_anomaly, method) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (data['machine_id'], temperature, humidity, data['sent_time'], is_temp_anomaly, is_hum_anomaly, method)
            )

            for k in list(last_email_sent.keys()):
                if (now - last_email_sent[k]).total_seconds() > MAX_EMAIL_RECORD_AGE:
                    del last_email_sent[k]

            if key in last_email_sent:
                elapsed = (now - last_email_sent[key]).total_seconds()
                if elapsed < 3600:
                    logger.info(f"⏳ 이메일 중복 방지: {key} 최근 {elapsed:.0f}초 전 발송됨, 스킵")
                    continue
            
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
            send_email_alert(subject, body, key, now)            

        else:
            logger.info(f"✅ 정상 데이터 [method={method}]: machine_id={data['machine_id']}, temperature={temperature}, humidity={humidity}")
