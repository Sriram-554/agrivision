import os
import sqlite3
from contextlib import contextmanager


def use_mysql():
    return os.getenv("MYSQL_HOST") and os.getenv("MYSQL_DATABASE")


@contextmanager
def get_connection():
    if use_mysql():
        import pymysql

        connection = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            yield connection
        finally:
            connection.close()
    else:
        db_path = os.path.join(os.path.dirname(__file__), "data", "crop_monitor.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'farmer',
    phone TEXT,
    location TEXT
);
CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    area REAL NOT NULL,
    crop_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS sensor_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    farm_id INTEGER,
    status TEXT NOT NULL DEFAULT 'online',
    last_communication TEXT,
    FOREIGN KEY (farm_id) REFERENCES farms(id)
);
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    farm_id INTEGER,
    soil_moisture REAL NOT NULL,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    light_intensity REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (device_id) REFERENCES sensor_devices(id),
    FOREIGN KEY (farm_id) REFERENCES farms(id)
);
CREATE TABLE IF NOT EXISTS crop_seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    crop_type TEXT NOT NULL,
    season_start TEXT,
    season_end TEXT,
    actual_yield REAL,
    FOREIGN KEY (farm_id) REFERENCES farms(id)
);
CREATE TABLE IF NOT EXISTS yield_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    farm_id INTEGER,
    crop_type TEXT NOT NULL,
    area REAL NOT NULL,
    soil_moisture REAL NOT NULL,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    estimated_yield REAL NOT NULL,
    unit TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (farm_id) REFERENCES farms(id)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    farm_id INTEGER,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (farm_id) REFERENCES farms(id)
);
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    moisture_threshold REAL NOT NULL DEFAULT 30,
    temperature_threshold REAL NOT NULL DEFAULT 35,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def initialize_database():
    if use_mysql():
        # MySQL deployment: run the equivalent SQL schema with AUTO_INCREMENT
        # and DATETIME columns. The SQLite fallback is used for local demos.
        return
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
