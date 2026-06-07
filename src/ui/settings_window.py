from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.database import (
    get_app_settings,
    save_app_settings,
    restore_default_app_settings,
)
from src.translations.language_manager import LanguageManager


class SettingsWindow(QMainWindow):
    """
    Battery Intelligence settings window.

    These values are stored in SQLite and control:
    - battery health calculation
    - voltage thresholds
    - temperature thresholds
    - prediction limits
    - replacement planning alerts

    Maintenance note:
    Values are stored using internal English keys.
    Only labels shown to the user are translated.
    """

    def __init__(self):
        super().__init__()

        self.inputs = {}

        self.setWindowTitle(
            self.t("battery_settings")
        )

        self.resize(560, 520)

        self.setup_ui()
        self.load_settings()
        self.apply_language()

    def t(self, key):
        """
        Translate visible text using global LanguageManager.
        """

        return LanguageManager.translate(key)

    def setup_ui(self):
        """
        Build settings interface.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.form = QFormLayout()

        self.fields = [
            "optimal_voltage_mv",
            "warning_voltage_mv",
            "critical_voltage_mv",
            "optimal_temperature_c",
            "warning_temperature_c",
            "critical_temperature_c",
            "manufacturer_life_years",
            "replacement_alert_days",
            "minimum_valid_discharge_mv_day",
            "battery_model",
            "battery_pack_voltage",
            "battery_pack_ah",
            "battery_pack_wh",
            "battery_cells",
        ]

        self.field_labels = {}

        for key in self.fields:
            label = QLabel()
            input_box = QLineEdit()

            self.field_labels[key] = label
            self.inputs[key] = input_box

            self.form.addRow(label, input_box)

        layout.addLayout(self.form)

        button_layout = QHBoxLayout()

        self.save_button = QPushButton()
        self.save_button.clicked.connect(
            self.save_settings
        )
        button_layout.addWidget(self.save_button)

        self.restore_button = QPushButton()
        self.restore_button.clicked.connect(
            self.restore_defaults
        )
        button_layout.addWidget(self.restore_button)

        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def apply_language(self):
        """
        Apply translations to all visible controls.
        """

        self.setWindowTitle(
            self.t("battery_settings")
        )

        self.title_label.setText(
            self.t("battery_settings")
        )

        for key, label in self.field_labels.items():
            label.setText(
                self.t(key)
            )

        self.save_button.setText(
            self.t("save_settings")
        )

        self.restore_button.setText(
            self.t("restore_defaults")
        )

    def load_settings(self):
        """
        Load settings from SQLite into input fields.
        """

        settings = get_app_settings()

        for key, input_box in self.inputs.items():
            input_box.setText(
                str(settings.get(key, ""))
            )

    def save_settings(self):
        """
        Validate and save settings to SQLite.

        Numeric fields are converted before saving.
        If a value is invalid, the user receives an error message.
        """

        try:
            settings = {
                "optimal_voltage_mv": float(
                    self.inputs["optimal_voltage_mv"].text()
                ),
                "warning_voltage_mv": float(
                    self.inputs["warning_voltage_mv"].text()
                ),
                "critical_voltage_mv": float(
                    self.inputs["critical_voltage_mv"].text()
                ),
                "optimal_temperature_c": float(
                    self.inputs["optimal_temperature_c"].text()
                ),
                "warning_temperature_c": float(
                    self.inputs["warning_temperature_c"].text()
                ),
                "critical_temperature_c": float(
                    self.inputs["critical_temperature_c"].text()
                ),
                "manufacturer_life_years": float(
                    self.inputs["manufacturer_life_years"].text()
                ),
                "replacement_alert_days": int(
                    float(self.inputs["replacement_alert_days"].text())
                ),
                "minimum_valid_discharge_mv_day": float(
                    self.inputs["minimum_valid_discharge_mv_day"].text()
                ),
                "battery_model": self.inputs["battery_model"].text(),
                "battery_pack_voltage": float(
                    self.inputs["battery_pack_voltage"].text()
                ),
                "battery_pack_ah": float(
                    self.inputs["battery_pack_ah"].text()
                ),
                "battery_pack_wh": float(
                    self.inputs["battery_pack_wh"].text()
                ),
                "battery_cells": int(
                    float(self.inputs["battery_cells"].text())
                ),
            }

            save_app_settings(settings)

            QMessageBox.information(
                self,
                self.t("settings_saved"),
                self.t("settings_saved_message")
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                self.t("settings_error"),
                f"{self.t('settings_error')}:\n{e}"
            )

    def restore_defaults(self):
        """
        Restore default settings and reload fields.
        """

        restore_default_app_settings()
        self.load_settings()

        QMessageBox.information(
            self,
            self.t("defaults_restored"),
            self.t("defaults_restored_message")
        )