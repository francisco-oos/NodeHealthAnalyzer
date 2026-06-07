from pathlib import Path
import sqlite3

import pandas as pd


DATABASE_PATH = Path("data") / "database" / "node_health.db"


DEFAULT_APP_SETTINGS = {
    # Technical reference values.
    # Used for Battery Health and Remaining Life.
    "technical_optimal_voltage_mv": 4200,
    "technical_critical_voltage_mv": 3600,

    # Operational thresholds.
    # Used for alerts, chart lines and tolerance.
    "warning_voltage_mv": 3800,
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


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    conn.execute("PRAGMA busy_timeout = 30000")

    return conn


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
    """
    Clear imported node data only.

    It does NOT delete:
    - app_settings
    - license/trial information
    """

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


def get_table_columns(cursor, table_name):
    """
    Return existing columns for a SQLite table.
    Used for safe migrations.
    """

    cursor.execute(f"PRAGMA table_info({table_name})")

    return [
        row[1]
        for row in cursor.fetchall()
    ]


def add_column_if_missing(
    cursor,
    table_name,
    column_name,
    column_definition
):
    """
    Add a column only if it does not already exist.
    """

    columns = get_table_columns(
        cursor,
        table_name
    )

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )


def migrate_settings_table(cursor):
    """
    Migrate existing app_settings table.

    This keeps old installations working after adding:
    - technical_optimal_voltage_mv
    - technical_critical_voltage_mv
    """

    add_column_if_missing(
        cursor,
        "app_settings",
        "technical_optimal_voltage_mv",
        "REAL"
    )

    add_column_if_missing(
        cursor,
        "app_settings",
        "technical_critical_voltage_mv",
        "REAL"
    )

    # Fill new technical columns using old values when available.
    cursor.execute("""
        UPDATE app_settings
        SET technical_optimal_voltage_mv =
            COALESCE(technical_optimal_voltage_mv, optimal_voltage_mv, 4200)
        WHERE id = 1
    """)

    cursor.execute("""
        UPDATE app_settings
        SET technical_critical_voltage_mv =
            COALESCE(technical_critical_voltage_mv, critical_voltage_mv, 3600)
        WHERE id = 1
    """)

    # Recommended V1.1 operational default.
    cursor.execute("""
        UPDATE app_settings
        SET warning_voltage_mv =
            COALESCE(warning_voltage_mv, 3800)
        WHERE id = 1
    """)


def initialize_settings_table():
    """
    Create and migrate app settings.

    Important:
    clear_database() must NOT delete this table.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY,
            technical_optimal_voltage_mv REAL,
            technical_critical_voltage_mv REAL,
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

    migrate_settings_table(cursor)

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
                technical_optimal_voltage_mv,
                technical_critical_voltage_mv,
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
                1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            DEFAULT_APP_SETTINGS["technical_optimal_voltage_mv"],
            DEFAULT_APP_SETTINGS["technical_critical_voltage_mv"],
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
    Return app settings as dictionary.
    """

    initialize_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            technical_optimal_voltage_mv,
            technical_critical_voltage_mv,
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
    Save user-defined settings.
    """

    initialize_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE app_settings
        SET
            technical_optimal_voltage_mv = ?,
            technical_critical_voltage_mv = ?,
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
        settings.get("technical_optimal_voltage_mv"),
        settings.get("technical_critical_voltage_mv"),
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
    Restore default Battery Intelligence settings.
    """

    save_app_settings(
        DEFAULT_APP_SETTINGS.copy()
    )