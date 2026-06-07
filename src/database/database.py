from pathlib import Path
import sqlite3

import pandas as pd


DATABASE_PATH = Path("data") / "database" / "node_health.db"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    conn.execute("PRAGMA busy_timeout = 30000")

    return conn
DEFAULT_APP_SETTINGS = {
    "optimal_voltage_mv": 4200,
    "warning_voltage_mv": 3700,
    "critical_voltage_mv": 3600,
    "optimal_temperature_c": 25,
    "warning_temperature_c": 45,
    "critical_temperature_c": 60,
    "manufacturer_life_years": 4,
    "replacement_alert_days": 90,
    "minimum_valid_discharge_mv_day": 0.5,
    "battery_model": "INR18650MJ1 / PA-BGL55.K01.R00",
    "battery_pack_voltage": 3.6,
    "battery_pack_ah": 14,
    "battery_pack_wh": 50,
    "battery_cells": 4,
}

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER NOT NULL,
            timestamp TEXT,
            voltage_mv REAL,
            charge_percent REAL,
            gps_quality REAL,
            temperature_c REAL,
            acq_type TEXT,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)
    conn.commit()
    conn.close()

    initialize_settings_table()



def clear_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM health_records")
    cursor.execute("DELETE FROM nodes")

    conn.commit()
    conn.close()


def insert_node(cursor, serial_number):
    cursor.execute("""
        INSERT OR IGNORE INTO nodes (serial_number)
        VALUES (?)
    """, (serial_number,))

    cursor.execute("""
        SELECT id FROM nodes
        WHERE serial_number = ?
    """, (serial_number,))

    return cursor.fetchone()[0]


def save_node_records(serial_number, records):
    conn = get_connection()
    cursor = conn.cursor()

    node_id = insert_node(cursor, serial_number)

    rows = []

    for record in records:
        rows.append((
            node_id,
            record.get("timestamp"),
            record.get("voltage_mv"),
            record.get("charge_percent"),
            record.get("gps_quality"),
            record.get("temperature_c"),
            record.get("acq_type"),
        ))

    cursor.executemany("""
        INSERT INTO health_records (
            node_id,
            timestamp,
            voltage_mv,
            charge_percent,
            gps_quality,
            temperature_c,
            acq_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    conn.close()


def get_records_by_serial(serial_number):
    conn = get_connection()

    query = """
        SELECT
            health_records.timestamp,
            health_records.voltage_mv,
            health_records.charge_percent,
            health_records.gps_quality,
            health_records.temperature_c,
            health_records.acq_type
        FROM health_records
        INNER JOIN nodes
            ON health_records.node_id = nodes.id
        WHERE nodes.serial_number = ?
        ORDER BY health_records.timestamp
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=(serial_number,)
    )

    conn.close()

    return df

def initialize_settings_table():
    """
    Creates application settings table.

    This table stores operational thresholds used by
    Battery Intelligence calculations.

    Important:
    clear_database() must NOT delete this table.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY,
            optimal_voltage_mv REAL,
            warning_voltage_mv REAL,
            critical_voltage_mv REAL,
            optimal_temperature_c REAL,
            warning_temperature_c REAL,
            critical_temperature_c REAL,
            manufacturer_life_years REAL,
            replacement_alert_days INTEGER,
            minimum_valid_discharge_mv_day REAL,
            battery_model TEXT,
            battery_pack_voltage REAL,
            battery_pack_ah REAL,
            battery_pack_wh REAL,
            battery_cells INTEGER
        )
    """)

    cursor.execute("""
        SELECT COUNT(*)
        FROM app_settings
        WHERE id = 1
    """)

    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("""
            INSERT INTO app_settings (
                id,
                optimal_voltage_mv,
                warning_voltage_mv,
                critical_voltage_mv,
                optimal_temperature_c,
                warning_temperature_c,
                critical_temperature_c,
                manufacturer_life_years,
                replacement_alert_days,
                minimum_valid_discharge_mv_day,
                battery_model,
                battery_pack_voltage,
                battery_pack_ah,
                battery_pack_wh,
                battery_cells
            )
            VALUES (
                1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            DEFAULT_APP_SETTINGS["optimal_voltage_mv"],
            DEFAULT_APP_SETTINGS["warning_voltage_mv"],
            DEFAULT_APP_SETTINGS["critical_voltage_mv"],
            DEFAULT_APP_SETTINGS["optimal_temperature_c"],
            DEFAULT_APP_SETTINGS["warning_temperature_c"],
            DEFAULT_APP_SETTINGS["critical_temperature_c"],
            DEFAULT_APP_SETTINGS["manufacturer_life_years"],
            DEFAULT_APP_SETTINGS["replacement_alert_days"],
            DEFAULT_APP_SETTINGS["minimum_valid_discharge_mv_day"],
            DEFAULT_APP_SETTINGS["battery_model"],
            DEFAULT_APP_SETTINGS["battery_pack_voltage"],
            DEFAULT_APP_SETTINGS["battery_pack_ah"],
            DEFAULT_APP_SETTINGS["battery_pack_wh"],
            DEFAULT_APP_SETTINGS["battery_cells"],
        ))

    conn.commit()
    conn.close()


def get_app_settings():
    """
    Returns application settings as dictionary.
    If settings do not exist, creates default settings first.
    """

    initialize_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            optimal_voltage_mv,
            warning_voltage_mv,
            critical_voltage_mv,
            optimal_temperature_c,
            warning_temperature_c,
            critical_temperature_c,
            manufacturer_life_years,
            replacement_alert_days,
            minimum_valid_discharge_mv_day,
            battery_model,
            battery_pack_voltage,
            battery_pack_ah,
            battery_pack_wh,
            battery_cells
        FROM app_settings
        WHERE id = 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return DEFAULT_APP_SETTINGS.copy()

    keys = list(DEFAULT_APP_SETTINGS.keys())

    return dict(zip(keys, row))


def save_app_settings(settings):
    """
    Saves user-defined operational thresholds.
    """

    initialize_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE app_settings
        SET
            optimal_voltage_mv = ?,
            warning_voltage_mv = ?,
            critical_voltage_mv = ?,
            optimal_temperature_c = ?,
            warning_temperature_c = ?,
            critical_temperature_c = ?,
            manufacturer_life_years = ?,
            replacement_alert_days = ?,
            minimum_valid_discharge_mv_day = ?,
            battery_model = ?,
            battery_pack_voltage = ?,
            battery_pack_ah = ?,
            battery_pack_wh = ?,
            battery_cells = ?
        WHERE id = 1
    """, (
        settings.get("optimal_voltage_mv"),
        settings.get("warning_voltage_mv"),
        settings.get("critical_voltage_mv"),
        settings.get("optimal_temperature_c"),
        settings.get("warning_temperature_c"),
        settings.get("critical_temperature_c"),
        settings.get("manufacturer_life_years"),
        settings.get("replacement_alert_days"),
        settings.get("minimum_valid_discharge_mv_day"),
        settings.get("battery_model"),
        settings.get("battery_pack_voltage"),
        settings.get("battery_pack_ah"),
        settings.get("battery_pack_wh"),
        settings.get("battery_cells"),
    ))

    conn.commit()
    conn.close()


def restore_default_app_settings():
    """
    Restores default Battery Intelligence settings.
    """

    save_app_settings(
        DEFAULT_APP_SETTINGS.copy()
    )