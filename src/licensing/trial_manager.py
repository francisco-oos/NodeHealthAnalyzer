from datetime import datetime
from pathlib import Path
import sqlite3


DATABASE_PATH = Path("data") / "database" / "node_health.db"

TRIAL_DAYS = 30


class TrialManager:

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
        Creates the trial table if it does not exist.

        Important:
        This table must NOT be deleted by clear_database().
        """

        conn = TrialManager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS license_info (
                id INTEGER PRIMARY KEY,
                install_date TEXT NOT NULL
            )
        """)

        cursor.execute("""
            SELECT install_date
            FROM license_info
            WHERE id = 1
        """)

        row = cursor.fetchone()

        if row is None:
            today = datetime.now().strftime(
                "%Y-%m-%d"
            )

            cursor.execute("""
                INSERT INTO license_info (
                    id,
                    install_date
                )
                VALUES (
                    1,
                    ?
                )
            """, (today,))

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
        """

        TrialManager.initialize_trial()

        conn = TrialManager.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT install_date
            FROM license_info
            WHERE id = 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return False, 0, 0, ""

        install_date_text = row[0]

        install_date = datetime.strptime(
            install_date_text,
            "%Y-%m-%d"
        )

        today = datetime.now()

        days_used = (
            today.date() - install_date.date()
        ).days

        days_remaining = TRIAL_DAYS - days_used

        is_valid = days_remaining >= 0

        return (
            is_valid,
            days_used,
            days_remaining,
            install_date_text
        )