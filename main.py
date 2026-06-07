import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.database.database import initialize_database
from src.licensing.trial_manager import TrialManager
from src.ui.main_window import MainWindow


def main():
    """
    Application entry point.

    Startup order:
    1. Initialize SQLite database.
    2. Start QApplication.
    3. Validate 30-day trial.
    4. Open main window only if trial is valid.
    """

    initialize_database()

    app = QApplication(sys.argv)

    (
        is_valid,
        days_used,
        days_remaining,
        install_date,
        error_message
    ) = TrialManager.get_trial_status()

    if not is_valid:
        QMessageBox.critical(
            None,
            "Trial Not Valid",
            "Node Health Analyzer Trial cannot continue.\n\n"
            f"Reason: {error_message}\n\n"
            "Please contact the developer for a licensed version."
        )

        sys.exit(0)

    window = MainWindow()
    window.show()

    QMessageBox.information(
        window,
        "Trial Version",
        "Node Health Analyzer Trial Version\n\n"
        f"Install Date: {install_date}\n"
        f"Days Used: {days_used}\n"
        f"Days Remaining: {days_remaining}"
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()