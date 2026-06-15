from pathlib import Path
import sqlite3
import os
import sys
from datetime import datetime

import pandas as pd


def get_app_base_path():
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "NodeHealthAnalyzer"

        return Path.home() / "AppData" / "Local" / "NodeHealthAnalyzer"

    return Path(__file__).resolve().parents[2]


DATABASE_PATH = get_app_base_path() / "data" / "database" / "node_health.db"


DEFAULT_APP_SETTINGS = {
    "technical_optimal_voltage_mv": 4200,
    "technical_critical_voltage_mv": 3600,
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


DEFAULT_FIELD_OPERATION_SETTINGS = {
    "configured_warning_percent": 30,
    "configured_critical_percent": 20,
    "bits_hour": 7,
    "bits_minute": 15,
    "sleep_minutes": 0,
    "wake_minutes": 0,
    "minimum_gps_percent": 70,
    "notes": "",
}


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def get_table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def add_column_if_missing(cursor, table_name, column_name, column_definition):
    columns = get_table_columns(cursor, table_name)

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT UNIQUE NOT NULL,
            first_seen TEXT,
            last_seen TEXT
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
            current_ma REAL,
            fcc_mah REAL,
            design_capacity_mah REAL,
            charge_mah REAL,
            duty_cycle_period_s REAL,
            gps_locked TEXT,
            gps_lock_time_ms REAL,
            settings_key TEXT,
            free_space_percent REAL,
            satellites REAL,
            latitude REAL,
            longitude REAL,
            source_file TEXT,
            import_session_id INTEGER,
            row_index INTEGER,
            FOREIGN KEY (node_id) REFERENCES nodes(id)
        )
    """)

    migrate_nodes_table(cursor)
    migrate_health_records_table(cursor)
    initialize_import_tables(cursor)
    create_indexes(cursor)

    conn.commit()
    conn.close()

    initialize_settings_table()
    initialize_field_operation_settings_table()


def migrate_nodes_table(cursor):
    add_column_if_missing(cursor, "nodes", "first_seen", "TEXT")
    add_column_if_missing(cursor, "nodes", "last_seen", "TEXT")


def migrate_health_records_table(cursor):
    required_columns = {
        "current_ma": "REAL",
        "fcc_mah": "REAL",
        "design_capacity_mah": "REAL",
        "charge_mah": "REAL",
        "duty_cycle_period_s": "REAL",
        "gps_locked": "TEXT",
        "gps_lock_time_ms": "REAL",
        "settings_key": "TEXT",
        "free_space_percent": "REAL",
        "satellites": "REAL",
        "latitude": "REAL",
        "longitude": "REAL",
        "source_file": "TEXT",
        "import_session_id": "INTEGER",
        "row_index": "INTEGER",
    }

    for column_name, column_definition in required_columns.items():
        add_column_if_missing(
            cursor,
            "health_records",
            column_name,
            column_definition,
        )


def initialize_import_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT,
            imported_at TEXT,
            node_count INTEGER DEFAULT 0,
            record_count INTEGER DEFAULT 0,
            duplicate_count INTEGER DEFAULT 0,
            notes TEXT
        )
    """)

    add_column_if_missing(cursor, "import_sessions", "duplicate_count", "INTEGER DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS node_summary_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_session_id INTEGER,
            serial_number TEXT NOT NULL,
            source_file TEXT,
            analysis_date TEXT,
            first_timestamp TEXT,
            last_timestamp TEXT,
            deployment_days REAL,
            records_count INTEGER,
            latest_voltage_mv REAL,
            latest_charge_percent REAL,
            avg_voltage_mv REAL,
            avg_charge_percent REAL,
            avg_current_ma REAL,
            avg_gps_quality REAL,
            avg_temperature_c REAL,
            max_temperature_c REAL,
            latest_fcc_mah REAL,
            avg_fcc_mah REAL,
            design_capacity_mah REAL,
            fcc_health_percent REAL,
            voltage_slope_mv_day REAL,
            charge_slope_percent_day REAL,
            battery_health REAL,
            degradation_level TEXT,
            prediction_confidence TEXT,
            recommendation TEXT,
            settings_key TEXT,
            FOREIGN KEY (import_session_id) REFERENCES import_sessions(id)
        )
    """)


def deduplicate_health_records_by_node_timestamp(cursor):
    """
    Historical rule:
    serial_number + timestamp = one unique record.

    If duplicate records already exist from old versions, keep the first one
    and remove the rest before creating the UNIQUE index.
    """

    cursor.execute("""
        DELETE FROM health_records
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM health_records
            WHERE timestamp IS NOT NULL
              AND TRIM(timestamp) <> ''
            GROUP BY node_id, timestamp
        )
        AND timestamp IS NOT NULL
        AND TRIM(timestamp) <> ''
    """)


def create_indexes(cursor):
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_serial ON nodes(serial_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_node_time ON health_records(node_id, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_session ON health_records(import_session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_source ON health_records(source_file)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_serial ON node_summary_history(serial_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session ON node_summary_history(import_session_id)")

    deduplicate_health_records_by_node_timestamp(cursor)

    cursor.execute("DROP INDEX IF EXISTS idx_records_unique_source")
    cursor.execute("DROP INDEX IF EXISTS idx_records_unique_source_row")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_records_unique_node_timestamp
        ON health_records(node_id, timestamp)
        WHERE timestamp IS NOT NULL
          AND TRIM(timestamp) <> ''
    """)


def clear_database(force=False):
    """
    Historical safety guard.

    Old versions called clear_database() before every import.
    For v2 historical mode, a normal import must NOT erase the database.

    - clear_database() does nothing.
    - clear_database(force=True) deletes operational/history data.
    """

    if not force:
        print("Histórico activo: clear_database() omitido. Usa clear_database(force=True) para borrar.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM health_records")
    cursor.execute("DELETE FROM node_summary_history")
    cursor.execute("DELETE FROM import_sessions")
    cursor.execute("DELETE FROM nodes")

    conn.commit()
    conn.close()


def create_import_session(folder_path, notes=""):
    initialize_database()

    conn = get_connection()
    cursor = conn.cursor()

    imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO import_sessions (folder_path, imported_at, notes)
        VALUES (?, ?, ?)
    """, (str(folder_path), imported_at, notes))

    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return session_id


def finish_import_session(import_session_id, node_count, record_count, duplicate_count=0):
    if not import_session_id:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE import_sessions
        SET node_count = ?, record_count = ?, duplicate_count = ?
        WHERE id = ?
    """, (node_count, record_count, duplicate_count, import_session_id))

    conn.commit()
    conn.close()


def insert_node(cursor, serial_number):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT OR IGNORE INTO nodes (serial_number, first_seen, last_seen)
        VALUES (?, ?, ?)
    """, (serial_number, now, now))

    cursor.execute("""
        UPDATE nodes
        SET last_seen = ?
        WHERE serial_number = ?
    """, (now, serial_number))

    cursor.execute("""
        SELECT id FROM nodes
        WHERE serial_number = ?
    """, (serial_number,))

    return cursor.fetchone()[0]


def save_node_records(serial_number, records, source_file=None, import_session_id=None):
    if not records:
        return 0

    initialize_database()

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
            record.get("current_ma"),
            record.get("fcc_mah"),
            record.get("design_capacity_mah"),
            record.get("charge_mah"),
            record.get("duty_cycle_period_s"),
            record.get("gps_locked"),
            record.get("gps_lock_time_ms"),
            record.get("settings_key"),
            record.get("free_space_percent"),
            record.get("satellites"),
            record.get("latitude"),
            record.get("longitude"),
            source_file or record.get("source_file"),
            import_session_id or record.get("import_session_id"),
            record.get("row_index"),
        ))

    cursor.executemany("""
        INSERT OR IGNORE INTO health_records (
            node_id,
            timestamp,
            voltage_mv,
            charge_percent,
            gps_quality,
            temperature_c,
            acq_type,
            current_ma,
            fcc_mah,
            design_capacity_mah,
            charge_mah,
            duty_cycle_period_s,
            gps_locked,
            gps_lock_time_ms,
            settings_key,
            free_space_percent,
            satellites,
            latitude,
            longitude,
            source_file,
            import_session_id,
            row_index
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    inserted = cursor.rowcount if cursor.rowcount is not None else 0

    conn.commit()
    conn.close()

    return max(inserted, 0)


def get_records_by_serial(serial_number, start_time=None, end_time=None, import_session_id=None):
    initialize_database()

    conn = get_connection()

    where = ["nodes.serial_number = ?"]
    params = [serial_number]

    if start_time is not None:
        where.append("health_records.timestamp >= ?")
        params.append(str(start_time))

    if end_time is not None:
        where.append("health_records.timestamp <= ?")
        params.append(str(end_time))

    if import_session_id is not None:
        where.append("health_records.import_session_id = ?")
        params.append(import_session_id)

    query = f"""
        SELECT
            health_records.timestamp,
            health_records.voltage_mv,
            health_records.charge_percent,
            health_records.gps_quality,
            health_records.temperature_c,
            health_records.acq_type,
            health_records.current_ma,
            health_records.fcc_mah,
            health_records.design_capacity_mah,
            health_records.charge_mah,
            health_records.duty_cycle_period_s,
            health_records.gps_locked,
            health_records.gps_lock_time_ms,
            health_records.settings_key,
            health_records.free_space_percent,
            health_records.satellites,
            health_records.latitude,
            health_records.longitude,
            health_records.source_file,
            health_records.import_session_id,
            health_records.row_index
        FROM health_records
        INNER JOIN nodes
            ON health_records.node_id = nodes.id
        WHERE {' AND '.join(where)}
        ORDER BY health_records.timestamp
    """

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    return df


def save_node_summary_history(summary):
    initialize_database()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO node_summary_history (
            import_session_id,
            serial_number,
            source_file,
            analysis_date,
            first_timestamp,
            last_timestamp,
            deployment_days,
            records_count,
            latest_voltage_mv,
            latest_charge_percent,
            avg_voltage_mv,
            avg_charge_percent,
            avg_current_ma,
            avg_gps_quality,
            avg_temperature_c,
            max_temperature_c,
            latest_fcc_mah,
            avg_fcc_mah,
            design_capacity_mah,
            fcc_health_percent,
            voltage_slope_mv_day,
            charge_slope_percent_day,
            battery_health,
            degradation_level,
            prediction_confidence,
            recommendation,
            settings_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        summary.get("import_session_id"),
        summary.get("serial_number"),
        summary.get("source_file"),
        summary.get("analysis_date"),
        summary.get("first_timestamp"),
        summary.get("last_timestamp"),
        summary.get("deployment_days"),
        summary.get("records_count"),
        summary.get("latest_voltage_mv"),
        summary.get("latest_charge_percent"),
        summary.get("avg_voltage_mv"),
        summary.get("avg_charge_percent"),
        summary.get("avg_current_ma"),
        summary.get("avg_gps_quality"),
        summary.get("avg_temperature_c"),
        summary.get("max_temperature_c"),
        summary.get("latest_fcc_mah"),
        summary.get("avg_fcc_mah"),
        summary.get("design_capacity_mah"),
        summary.get("fcc_health_percent"),
        summary.get("voltage_slope_mv_day"),
        summary.get("charge_slope_percent_day"),
        summary.get("battery_health"),
        summary.get("degradation_level"),
        summary.get("prediction_confidence"),
        summary.get("recommendation"),
        summary.get("settings_key"),
    ))

    conn.commit()
    conn.close()


def get_node_summary_history(serial_number=None):
    initialize_database()
    conn = get_connection()

    if serial_number:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM node_summary_history
            WHERE serial_number = ?
            ORDER BY analysis_date
            """,
            conn,
            params=(serial_number,),
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM node_summary_history
            ORDER BY analysis_date DESC, serial_number
            """,
            conn,
        )

    conn.close()
    return df


def get_latest_node_summaries():
    initialize_database()
    conn = get_connection()

    query = """
        SELECT h.*
        FROM node_summary_history h
        INNER JOIN (
            SELECT serial_number, MAX(analysis_date) AS max_analysis_date
            FROM node_summary_history
            GROUP BY serial_number
        ) latest
            ON h.serial_number = latest.serial_number
           AND h.analysis_date = latest.max_analysis_date
        ORDER BY h.serial_number
    """

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df




def get_record_date_range(serial_number=None):
    """
    Returns available data range.

    If serial_number is provided, returns range for that node.
    Otherwise returns global range for all stored records.
    """
    initialize_database()
    conn = get_connection()

    if serial_number:
        query = """
            SELECT
                MIN(health_records.timestamp) AS min_timestamp,
                MAX(health_records.timestamp) AS max_timestamp,
                COUNT(*) AS record_count
            FROM health_records
            INNER JOIN nodes
                ON health_records.node_id = nodes.id
            WHERE nodes.serial_number = ?
              AND health_records.timestamp IS NOT NULL
              AND TRIM(health_records.timestamp) <> ''
        """
        df = pd.read_sql_query(query, conn, params=(serial_number,))
    else:
        query = """
            SELECT
                MIN(timestamp) AS min_timestamp,
                MAX(timestamp) AS max_timestamp,
                COUNT(*) AS record_count
            FROM health_records
            WHERE timestamp IS NOT NULL
              AND TRIM(timestamp) <> ''
        """
        df = pd.read_sql_query(query, conn)

    conn.close()

    if df.empty:
        return None, None, 0

    row = df.iloc[0]

    return (
        row.get("min_timestamp"),
        row.get("max_timestamp"),
        int(row.get("record_count") or 0),
    )


def get_dashboard_nodes_from_database():
    """
    Loads dashboard rows directly from SQLite.

    This lets the application open using the existing historical database
    without requiring the user to import CSV files again.
    """
    initialize_database()
    conn = get_connection()

    query = """
        WITH latest_summary AS (
            SELECT h.*
            FROM node_summary_history h
            INNER JOIN (
                SELECT serial_number, MAX(analysis_date) AS max_analysis_date
                FROM node_summary_history
                GROUP BY serial_number
            ) latest
                ON h.serial_number = latest.serial_number
               AND h.analysis_date = latest.max_analysis_date
        ),
        record_counts AS (
            SELECT
                node_id,
                COUNT(*) AS records,
                MIN(timestamp) AS first_time,
                MAX(timestamp) AS last_time
            FROM health_records
            GROUP BY node_id
        )
        SELECT
            nodes.serial_number,
            COALESCE(record_counts.records, 0) AS records,
            record_counts.first_time,
            record_counts.last_time,
            (
                SELECT voltage_mv
                FROM health_records hr
                WHERE hr.node_id = nodes.id
                  AND hr.timestamp = record_counts.last_time
                ORDER BY hr.id DESC
                LIMIT 1
            ) AS voltage,
            (
                SELECT charge_percent
                FROM health_records hr
                WHERE hr.node_id = nodes.id
                  AND hr.timestamp = record_counts.last_time
                ORDER BY hr.id DESC
                LIMIT 1
            ) AS charge,
            (
                SELECT acq_type
                FROM health_records hr
                WHERE hr.node_id = nodes.id
                  AND hr.timestamp = record_counts.last_time
                ORDER BY hr.id DESC
                LIMIT 1
            ) AS acq_type,
            (
                SELECT gps_quality
                FROM health_records hr
                WHERE hr.node_id = nodes.id
                  AND hr.timestamp = record_counts.last_time
                ORDER BY hr.id DESC
                LIMIT 1
            ) AS gps_quality,
            (
                SELECT temperature_c
                FROM health_records hr
                WHERE hr.node_id = nodes.id
                  AND hr.timestamp = record_counts.last_time
                ORDER BY hr.id DESC
                LIMIT 1
            ) AS temperature,
            latest_summary.battery_health,
            latest_summary.degradation_level,
            latest_summary.voltage_slope_mv_day,
            latest_summary.charge_slope_percent_day,
            latest_summary.prediction_confidence,
            latest_summary.recommendation,
            latest_summary.latest_fcc_mah,
            latest_summary.design_capacity_mah,
            latest_summary.fcc_health_percent,
            latest_summary.settings_key
        FROM nodes
        LEFT JOIN record_counts
            ON record_counts.node_id = nodes.id
        LEFT JOIN latest_summary
            ON latest_summary.serial_number = nodes.serial_number
        ORDER BY nodes.serial_number
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def get_import_sessions(limit=20):
    initialize_database()
    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT
            id,
            folder_path,
            imported_at,
            node_count,
            record_count,
            duplicate_count,
            notes
        FROM import_sessions
        ORDER BY imported_at DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )

    conn.close()
    return df




def migrate_settings_table(cursor):
    required_columns = {
        "technical_optimal_voltage_mv": "REAL",
        "technical_critical_voltage_mv": "REAL",
        "warning_voltage_mv": "REAL",
        "critical_voltage_mv": "REAL",
        "optimal_temperature_c": "REAL",
        "warning_temperature_c": "REAL",
        "critical_temperature_c": "REAL",
        "manufacturer_life_years": "REAL",
        "replacement_alert_days": "INTEGER",
        "minimum_valid_discharge_mv_day": "REAL",
        "battery_model": "TEXT",
        "battery_pack_voltage": "REAL",
        "battery_pack_ah": "REAL",
        "battery_pack_wh": "REAL",
        "battery_cells": "INTEGER",
    }

    for column_name, column_definition in required_columns.items():
        add_column_if_missing(
            cursor,
            "app_settings",
            column_name,
            column_definition,
        )

    columns = get_table_columns(cursor, "app_settings")

    if "optimal_voltage_mv" in columns:
        cursor.execute("""
            UPDATE app_settings
            SET technical_optimal_voltage_mv =
                COALESCE(
                    technical_optimal_voltage_mv,
                    optimal_voltage_mv,
                    4200
                )
            WHERE id = 1
        """)
    else:
        cursor.execute("""
            UPDATE app_settings
            SET technical_optimal_voltage_mv =
                COALESCE(technical_optimal_voltage_mv, 4200)
            WHERE id = 1
        """)

    cursor.execute("""
        UPDATE app_settings
        SET technical_critical_voltage_mv =
            COALESCE(technical_critical_voltage_mv, critical_voltage_mv, 3600)
        WHERE id = 1
    """)

    cursor.execute("""
        UPDATE app_settings
        SET warning_voltage_mv =
            COALESCE(warning_voltage_mv, 3800)
        WHERE id = 1
    """)

    cursor.execute("""
        UPDATE app_settings
        SET critical_voltage_mv =
            COALESCE(critical_voltage_mv, 3600)
        WHERE id = 1
    """)


def initialize_settings_table():
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
        """, tuple(DEFAULT_APP_SETTINGS.values()))

    conn.commit()
    conn.close()


def get_app_settings():
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

    return dict(zip(DEFAULT_APP_SETTINGS.keys(), row))


def save_app_settings(settings):
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
    save_app_settings(DEFAULT_APP_SETTINGS.copy())


def initialize_field_operation_settings_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS field_operation_settings (
            id INTEGER PRIMARY KEY,
            configured_warning_percent REAL,
            configured_critical_percent REAL,
            bits_hour INTEGER,
            bits_minute INTEGER,
            sleep_minutes REAL,
            wake_minutes REAL,
            minimum_gps_percent REAL,
            notes TEXT
        )
    """)

    cursor.execute("""
        SELECT COUNT(*)
        FROM field_operation_settings
        WHERE id = 1
    """)

    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("""
            INSERT INTO field_operation_settings (
                id,
                configured_warning_percent,
                configured_critical_percent,
                bits_hour,
                bits_minute,
                sleep_minutes,
                wake_minutes,
                minimum_gps_percent,
                notes
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            DEFAULT_FIELD_OPERATION_SETTINGS["configured_warning_percent"],
            DEFAULT_FIELD_OPERATION_SETTINGS["configured_critical_percent"],
            DEFAULT_FIELD_OPERATION_SETTINGS["bits_hour"],
            DEFAULT_FIELD_OPERATION_SETTINGS["bits_minute"],
            DEFAULT_FIELD_OPERATION_SETTINGS["sleep_minutes"],
            DEFAULT_FIELD_OPERATION_SETTINGS["wake_minutes"],
            DEFAULT_FIELD_OPERATION_SETTINGS["minimum_gps_percent"],
            DEFAULT_FIELD_OPERATION_SETTINGS["notes"],
        ))

    conn.commit()
    conn.close()


def get_field_operation_settings():
    initialize_field_operation_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            configured_warning_percent,
            configured_critical_percent,
            bits_hour,
            bits_minute,
            sleep_minutes,
            wake_minutes,
            minimum_gps_percent,
            notes
        FROM field_operation_settings
        WHERE id = 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return DEFAULT_FIELD_OPERATION_SETTINGS.copy()

    return dict(zip(DEFAULT_FIELD_OPERATION_SETTINGS.keys(), row))


def save_field_operation_settings(settings):
    initialize_field_operation_settings_table()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE field_operation_settings
        SET
            configured_warning_percent = ?,
            configured_critical_percent = ?,
            bits_hour = ?,
            bits_minute = ?,
            sleep_minutes = ?,
            wake_minutes = ?,
            minimum_gps_percent = ?,
            notes = ?
        WHERE id = 1
    """, (
        settings.get("configured_warning_percent"),
        settings.get("configured_critical_percent"),
        settings.get("bits_hour"),
        settings.get("bits_minute"),
        settings.get("sleep_minutes"),
        settings.get("wake_minutes"),
        settings.get("minimum_gps_percent"),
        settings.get("notes"),
    ))

    conn.commit()
    conn.close()


def restore_default_field_operation_settings():
    save_field_operation_settings(DEFAULT_FIELD_OPERATION_SETTINGS.copy())
