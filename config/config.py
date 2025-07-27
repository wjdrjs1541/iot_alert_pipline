#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
설정 파일
iot sensor Pipeline 프로젝트에서 사용되는 설정 값들을 정의합니다.
"""

import os
from dotenv import load_dotenv

# .env 파일 로드 (존재하는 경우)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Kafka 설정
KAFKA_BROKERS = os.getenv('KAFKA_BROKERS')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC')
CSV_DATA_PATH= os.getenv('CSV_DATA_PATH')
GROUP_ID = os.getenv('GROUP_ID')

# 이메일 알림 설정
EMAIL_SENDER = os.getenv('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER', '')
EMAIL_SMTP_SERVER = os.getenv('EMAIL_SERVER')
EMAIL_SMTP_PORT = int(os.getenv('EMAIL_PORT'))

# DB 설정
POSTGRESQL_HOST = os.getenv('POSTGRESQL_HOST')
POSTGRESQL_DB = os.getenv('POSTGRESQL_DB')
POSTGRESQL_USER = os.getenv('POSTGRESQL_USER')
POSTGRESQL_PASSWORD = os.getenv('POSTGRESQL_PASSWORD')
POSTGRESQL_PORT = int(os.getenv('POSTGRESQL_PORT'))

# Spark 설정
SPARK_CONTAINER = os.getenv('SPARK_CONTAINER')
SPARK_SUBMIT_PATH = os.getenv('SPARK_SUBMIT_PATH')
SPARK_MASTER_URL = os.getenv('SPARK_MASTER_URL')
SPARK_JARS_PATH = os.getenv('SPARK_JARS_PATH')
SPARK_APP_PATH = os.getenv('SPARK_APP_PATH')