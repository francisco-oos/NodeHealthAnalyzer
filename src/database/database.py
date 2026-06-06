from pathlib import Path
import sqlite3


DATABASE_PATH = (
    Path("data")
    / "database"
    / "node_health.db"
)


def initialize_database():

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(DATABASE_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id INTEGER,
            timestamp TEXT,
            voltage_mv REAL,
            charge_percent REAL,
            temperature_c REAL,
            acq_type TEXT,
            gps_quality REAL,
            latitude REAL,
            longitude REAL
        )
    """)

    conn.commit()
    conn.close()