-- ./postgres-init/init.sql

CREATE TABLE IF NOT EXISTS sensor_data (
    id SERIAL PRIMARY KEY,
    machine_id TEXT NOT NULL,
    temperature FLOAT,
    humidity FLOAT,
    sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE anomaly_range (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR,
    min_temp FLOAT,
    max_temp FLOAT,
    min_humidity FLOAT,
    max_humidity FLOAT,
    method VARCHAR,
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_machine_method UNIQUE (machine_id, method)
);

CREATE TABLE anomaly_log (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(255),
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    sent_time TIMESTAMP,
    temp_anomaly BOOLEAN,
    hum_anomaly BOOLEAN,
    method VARCHAR(50),  -- quantile / iqr
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
