FROM apache/airflow:2.9.0

USER root

RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    procps \
    default-jdk \
    curl && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

USER airflow

COPY requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

USER root
COPY entrypoint.sh /opt/airflow/entrypoint.sh
RUN chmod +x /opt/airflow/entrypoint.sh
USER airflow

ENTRYPOINT ["/opt/airflow/entrypoint.sh"]
