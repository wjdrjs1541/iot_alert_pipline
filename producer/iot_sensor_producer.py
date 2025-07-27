import pandas as pd
import json
import time
import logging
from kafka import KafkaProducer
from datetime import datetime
import argparse
import os
import sys
import random


# 상위 디렉토리를 path에 추가하여 다른 모듈을 import할 수 있도록 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import KAFKA_BROKERS, KAFKA_TOPIC, CSV_DATA_PATH



# ✅ 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ✅ argparse
parser = argparse.ArgumentParser(description="IoT Sensor Producer")
parser.add_argument('--machine', type=str, required=True, help='Machine name (e.g., sensor_A, sensor_B)')
args = parser.parse_args()

# ✅ KafkaProducer 생성
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=str.encode,
    acks="all",
    linger_ms= 0 ,
    enable_idempotence= True
)

# ✅ CSV 데이터 로딩
try:
    df = pd.read_csv(CSV_DATA_PATH, low_memory=False)
    df = df[df["mqtt.topic"] == "Temperature_and_Humidity"]
    df = df[["mqtt.topic", "mqtt.msg"]].fillna("null")
except Exception as e:
    logging.error(f"CSV 파일 로드 실패: {e}")
    exit(1)

# ✅ Kafka 메시지 전송
for idx, row in df.iterrows():
    message = {
        "machine_id": args.machine,
        "topic": row["mqtt.topic"],
        "mqtt_msg": row["mqtt.msg"],
        "sent_time": datetime.now().isoformat()
    }
    producer.send(KAFKA_TOPIC, key=args.machine, value=message)
    logging.info(f"[{args.machine}] {message}")
    time.sleep(random.uniform(1, 2))

producer.flush()
producer.close()