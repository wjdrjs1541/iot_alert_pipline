

# 🔖Index
#### 0. 📂 프로젝트 개요
#### 1. 🚀 서비스 실행 방법 
#### 2. 🏗️ 아키텍처 
#### 9. To Do

## 0. 📂 프로젝트 개요
#####     IoT 센서 데이터를 Kafka로 수집하고, Spark Batch 처리로 이상 탐지 기준을 계산한 뒤, 실시간 이상 감지 및 경고 알림을 수행하는 데이터 파이프라인

## 1. 🚀 서비스 실행 방법 
#####     data 폴더 생성 및 raw data 저장(DNN-EdgeIIoT-dataset.csv)
#####      → https://www.kaggle.com/datasets/sibasispradhan/edge-iiotset-dataset
#####     Docker Desktop 실행 후 
#####      → docker compose up -d 

## 2. 🏗️ 아키텍처 
<img width="1119" height="745" alt="image" src="https://github.com/user-attachments/assets/eda28d74-9633-44e1-b10a-219d76ce2a68" />


## 9. 🕖 To Do 7/28
#####     대시보드 구축(온도/습도/이벤트 트렌드/CPU 점유율/메모리 점유율)
#####     부하 Test
