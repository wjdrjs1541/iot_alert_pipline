FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요 파일 복사
COPY requirements.txt .
COPY iot_sensor_producer.py .
COPY kafka_load_producer.py .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt
