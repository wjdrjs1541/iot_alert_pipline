import pandas as pd
import json
import time
import random
import logging
from datetime import datetime
from kafka import KafkaProducer

# ✅ 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        # logging.FileHandler("producer.log")  # 로그 파일 저장하려면 이 줄 주석 해제
    ]
)

# Kafka 설정
KAFKA_BROKER = 'kafka1:29092'
KAFKA_TOPIC = 'iot-sensor-events'
MACHINE_NAME = 'sensor_A' #sensor_A, sensor_B 사용 예정

# 전송할 컬럼
selected_columns = ['mqtt.topic', 'mqtt.msg']

# Kafka 프로듀서 생성
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=str.encode,
    acks='all',
    linger_ms=0,
    enable_idempotence=True,
    retries=5,  
    retry_backoff_ms=1000 
)

# CSV 데이터 로드
df = pd.read_csv('./data/DNN-EdgeIIoT-dataset.csv', low_memory=False)

# mqtt.topic == "Temperature_and_Humidity" 필터링
df = df[df['mqtt.topic'] == 'Temperature_and_Humidity']

# 필요한 컬럼만 선택하고 결측치 처리
df = df[selected_columns].fillna('null')

# Kafka로 전송
try:
    for idx, row in df.iterrows():
        mqtt_msg = row['mqtt.msg']

        message = {
            "machine_id": str(MACHINE_NAME),
            "mqtt_msg": mqtt_msg,  # ✅ 디코딩 없이 전송
            "sent_time": datetime.now().isoformat()
        }

        producer.send(KAFKA_TOPIC, key=MACHINE_NAME, value=message)
        logging.info(f"[{idx}] Sent: {message}")

        time.sleep(random.uniform(0.8, 1.2))

except KeyboardInterrupt:
    logging.info("프로듀서가 중지되었습니다.")
finally:
    producer.flush()
    producer.close()
    logging.info("프로듀서 종료됨.")