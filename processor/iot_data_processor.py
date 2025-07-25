import yaml
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
from dotenv import load_dotenv

# ✅ config 경로
CONFIG_PATH = "/config/kafka_config.yaml"
# ✅ .env 로드
load_dotenv("/config/.env")

def send_email_alert(subject: str, body: str):
    sender = os.getenv("EMAIL_ADDRESS")
    receiver = os.getenv("EMAIL_RECEIVER")
    password = os.getenv("EMAIL_PASSWORD")

    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver

    message.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(os.getenv("EMAIL_HOST"), int(os.getenv("EMAIL_PORT")), context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, message.as_string())
        logger.info("📧 이상치 이메일 알림 전송 완료")
    except Exception as e:
        logger.error(f"🚨 이메일 전송 실패: {e}")

def load_config(path: str) -> dict:
    with open(path, "r") as file:
        return yaml.safe_load(file)

config = load_config(CONFIG_PATH)

# ✅ 설정 파싱
kafka_config = config["kafka"]
producer_config = config["producer"]
consumer_config = config["consumer"]

KAFKA_BROKERS = kafka_config['brokers']
KAFKA_TOPIC = kafka_config['topic']
CSV_PATH = producer_config['csv_path']

GROUP_ID = consumer_config['group_id']

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
            host="postgresql",
            database="iot_data",
            user="postgres",
            password="postgres",
            port="5432"
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
