-- ./postgres-init/init.sql

CREATE TABLE IF NOT EXISTS sensor_data (
    id SERIAL PRIMARY KEY,
    machine_id TEXT NOT NULL,
    temperature FLOAT,
    humidity FLOAT,
    sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS anomaly_range (
    id SERIAL PRIMARY KEY,
    machine_id TEXT NOT NULL,
    min_temp FLOAT,
    max_temp FLOAT,
    min_humidity FLOAT,
    max_humidity FLOAT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);