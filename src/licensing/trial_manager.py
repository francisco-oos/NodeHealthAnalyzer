from datetime import datetime
from pathlib import Path
import sqlite3


DATABASE_PATH = Path("data") / "database" / "node_health.db"

TRIAL_DAYS = 30


class TrialManager:
    """
    Manages local 30-day trial validation.

    Important:
    - Trial data is stored in SQLite.
    - license_info must NOT be deleted by clear_database().
    - This is offline protection for demo/trial distribution.
    """

    @staticmethod
    def get_connection():
        DATABASE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        return sqlite3.connect(
            DATABASE_PATH
        )

    @staticmethod
    def initialize_trial():
        """
        Creates or updates the trial table.

        Handles old database versions where license_info existed
        without last_execution_date.
        """

        conn = TrialManager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS license_info (
                id INTEGER PRIMARY KEY,
                install_date TEXT NOT NULL
            )
        """)

        cursor.execute("PRAGMA table_info(license_info)")
        columns = [
            row[1]
            for row in cursor.fetchall()
        ]

        if "last_execution_date" not in columns:
            cursor.execute("""
                ALTER TABLE license_info
                ADD COLUMN last_execution_date TEXT
            """)

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        cursor.execute("""
            SELECT install_date, last_execution_date
            FROM license_info
            WHERE id = 1
        """)

        row = cursor.fetchone()

        if row is None:
            cursor.execute("""
                INSERT INTO license_info (
                    id,
                    install_date,
                    last_execution_date
                )
                VALUES (
                    1,
                    ?,
                    ?
                )
            """, (today, today))

        else:
            install_date = row[0]
            last_execution_date = row[1]

            if not last_execution_date:
                cursor.execute("""
                    UPDATE license_info
                    SET last_execution_date = ?
                    WHERE id = 1
                """, (install_date or today,))

        conn.commit()
        conn.close()

    @staticmethod
    def get_trial_status():
        """
        Returns:
        - is_valid
        - days_used
        - days_remaining
        - install_date
        - error_message
        """

        TrialManager.initialize_trial()

        conn = TrialManager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT install_date, last_execution_date
            FROM license_info
            WHERE id = 1
        """)

        row = cursor.fetchone()

        if row is None:
            conn.close()
            return (
                False,
                0,
                0,
                "",
                "Trial information not found."
            )

        install_date_text = row[0]
        last_execution_date_text = row[1]

        install_date = datetime.strptime(
            install_date_text,
            "%Y-%m-%d"
        )

        last_execution_date = datetime.strptime(
            last_execution_date_text,
            "%Y-%m-%d"
        )

        today = datetime.now()

        if today.date() < last_execution_date.date():
            conn.close()

            return (
                False,
                0,
                0,
                install_date_text,
                "System date manipulation detected."
            )

        days_used = (
            today.date() - install_date.date()
        ).days

        days_remaining = TRIAL_DAYS - days_used

        if days_remaining < 0:
            conn.close()

            return (
                False,
                days_used,
                0,
                install_date_text,
                "Trial period has expired."
            )

        cursor.execute("""
            UPDATE license_info
            SET last_execution_date = ?
            WHERE id = 1
        """, (
            today.strftime("%Y-%m-%d"),
        ))

        conn.commit()
        conn.close()

        return (
            True,
            days_used,
            days_remaining,
            install_date_text,
            ""
        )