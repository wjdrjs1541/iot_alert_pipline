from kafka import KafkaProducer
import json
import time
import random
import threading

producer = KafkaProducer(
    bootstrap_servers=['kafka1:29092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def generate_load(rate_per_sec=100):
    while True:
        for _ in range(rate_per_sec):
            msg = {
                "machine_id": "sensor_A",
                "mqtt_msg": "32342e36382037362e34320d0a",  # 임의 값
                "sent_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            producer.send('iot-sensor-events', msg)
        time.sleep(1)

# 쓰레드로 여러 개 돌리기
for _ in range(5):  # 5배속
    threading.Thread(target=generate_load, args=(100,), daemon=True).start()

while True:
    time.sleep(10)
