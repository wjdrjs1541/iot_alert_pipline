from kafka import KafkaConsumer, KafkaProducer
import psycopg2
import json
import logging
import binascii
import time
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# ✅ Kafka Config
KAFKA_BROKER_PRODUCER = 'kafka1:29092'
KAFKA_BROKER_PROCESSOR = ["kafka1:29092", "kafka2:29093"]
KAFKA_TOPIC = 'iot-sensor-events'
ANOMALY_TOPIC = 'anomaly-topic'

# ✅ 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def create_topics_if_not_exist(broker, topics):
    admin_client = KafkaAdminClient(bootstrap_servers=broker)
    topic_list = []
    for topic_name in topics:
        topic_list.append(NewTopic(name=topic_name, num_partitions=2, replication_factor=1))
    try:
        admin_client.create_topics(new_topics=topic_list, validate_only=False)
        logger.info(f"✅ Topic 생성됨: {topics}")
    except TopicAlreadyExistsError:
        logger.info(f"✅ Topic 이미 존재: {topics}")
    except Exception as e:
        logger.error(f"🚨 Topic 생성 실패: {e}")
    finally:
        admin_client.close()

def get_anomaly_bounds(cursor):
    cursor.execute("SELECT min_temp, max_temp, min_humidity, max_humidity FROM anomaly_range ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    return result if result else (None, None, None, None)


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


# PostgreSQL 연결 (최초 연결도 재시도)
while True:
    try:
        conn = psycopg2.connect(host="postgresql", database="iot_data", user="postgres", password="postgres", port="5432")
        cursor = conn.cursor()
        break
    except Exception as e:
        logger.error(f"🚨 PostgreSQL 연결 실패, 재시도 중... 에러: {e}")
        time.sleep(3)

# Kafka 토픽이 없으면 자동 생성
create_topics_if_not_exist(KAFKA_BROKER_PRODUCER, [KAFKA_TOPIC, ANOMALY_TOPIC])

# Kafka Consumer 설정
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BROKER_PROCESSOR,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='sensor-consumer-group3',
    session_timeout_ms=10000,   # 옵션: 안정성
    heartbeat_interval_ms=3000, # 옵션: 안정성
)
print("test1")
# Kafka Producer 설정 (이상치 탐지 시)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER_PRODUCER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
print("test2")

# 메시지 소비 루프
for msg in consumer:
    data = msg.value

    # mqtt_msg 누락 방어
    if 'mqtt_msg' not in data:
        logger.error(f"🚨 mqtt_msg 누락된 메시지: {data}")
        continue
    

    try:
        # ✅ mqtt_msg 디코딩
        decoded_msg = binascii.unhexlify(data['mqtt_msg']).decode('ascii').strip()
        temperature_str, humidity_str = decoded_msg.split()
        temperature = float(temperature_str)
        humidity = float(humidity_str)
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError) as e:
        logger.error(f"🚨 mqtt_msg 디코딩 실패 또는 포맷 오류: {data.get('mqtt_msg')} / 에러: {e}")
        continue
    
    print("test2")
    # DB 저장 (재시도 3번)
    if not execute_with_retry(
        cursor,
        "INSERT INTO sensor_data (machine_id, temperature, humidity, sent_time) VALUES (%s, %s, %s, %s)",
        (data['machine_id'], temperature, humidity, data['sent_time']),
        retries=3,
        delay=2
    ):
        logger.error(f"🚨 DB 저장 3회 실패, 해당 데이터 스킵: {data}")
        continue

    # 최신 이상치 범위 불러오기
    try:
        min_temp, max_temp, min_hum, max_hum = get_anomaly_bounds(cursor)
    except Exception as e:
        logger.error(f"🚨 이상치 범위 쿼리 실패, 에러: {e}")
        continue

    if None not in [min_temp, max_temp, min_hum, max_hum]:
        is_temp_anomaly = not (min_temp <= temperature <= max_temp)
        is_hum_anomaly = not (min_hum <= humidity <= max_hum)

        if is_temp_anomaly or is_hum_anomaly:
            logger.warning(f"🚨 이상치 탐지됨! machine_id={data['machine_id']}, temperature={temperature}, humidity={humidity}, sent_time={data['sent_time']}")
            
            # ✅ 이상치 Kafka 토픽으로 전송
            anomaly_payload = {
                "machine_id": data['machine_id'],
                "temperature": temperature,
                "humidity": humidity,
                "sent_time": data['sent_time'],
                "anomaly_type": {
                    "temperature": is_temp_anomaly,
                    "humidity": is_hum_anomaly
                }
            }
            producer.send(ANOMALY_TOPIC, anomaly_payload)
            producer.flush()
        else:
            logger.info(f"✅ 정상 데이터 수신: machine_id={data['machine_id']}, temperature={temperature}, humidity={humidity}, sent_time={data['sent_time']}")
    else:
        logger.info(f"ℹ️ 이상치 기준 없음. 데이터 저장만 수행: machine_id={data['machine_id']}, temperature={temperature}, humidity={humidity}, sent_time={data['sent_time']}")
