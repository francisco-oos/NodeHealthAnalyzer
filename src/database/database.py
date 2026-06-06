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