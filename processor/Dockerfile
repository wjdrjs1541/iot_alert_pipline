FROM python:3.10-slim

WORKDIR /app


# 의존성 파일 복사
COPY requirements.txt .

# 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . /app

CMD ["python", "iot_data_processor.py"]
