import pandas as pd
import json
import time
import logging
from kafka import KafkaProducer
from datetime import datetime
import argparse

KAFKA_BROKER = 'kafka1:29092'
KAFKA_TOPIC = 'iot-sensor-events'
CSV_PATH = './data/DNN-EdgeIIoT-dataset.csv'

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

parser = argparse.ArgumentParser(description="IoT Sensor Producer")
parser.add_argument('--machine', type=str, required=True, help='Machine name (e.g., sensor_A, sensor_B)')
args = parser.parse_args()

# Kafka 프로듀서 생성
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=str.encode,
    acks='all',
    linger_ms=0,
    enable_idempotence=True
)

# CSV 데이터 로드 (고정)
df = pd.read_csv(CSV_PATH, low_memory=False)
df = df[df['mqtt.topic'] == 'Temperature_and_Humidity']
df = df[['mqtt.topic', 'mqtt.msg']].fillna('null')

# ✅ 메시지 전송
for idx, row in df.iterrows():
    message = {
        'machine_id': args.machine,
        'topic': row['mqtt.topic'],
        'mqtt_msg': row['mqtt.msg'],
        'sent_time': datetime.now().isoformat()
    }
    producer.send(KAFKA_TOPIC, key=args.machine, value=message)
    logging.info(f"[{args.machine}] {message}")
    time.sleep(0.1)

producer.flush()
producer.close()