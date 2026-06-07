from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
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


ADMIN_PASSWORD = "NHA2026"


class SettingsWindow(QMainWindow):
    settings_saved_signal = Signal()

    def __init__(self):
        super().__init__()

        self.inputs = {}
        self.field_labels = {}
        self.technical_unlocked = False

        self.setWindowTitle(self.t("battery_settings"))
        self.resize(650, 620)

        self.setup_ui()
        self.load_settings()
        self.apply_language()
        self.lock_technical_fields()

    def t(self, key):
        return LanguageManager.translate(key)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.operational_label = QLabel()
        layout.addWidget(self.operational_label)

        self.form = QFormLayout()

        self.operational_fields = [
            "warning_voltage_mv",
            "critical_voltage_mv",
            "warning_temperature_c",
            "critical_temperature_c",
            "replacement_alert_days",
        ]

        self.technical_fields = [
            "technical_optimal_voltage_mv",
            "technical_critical_voltage_mv",
            "optimal_temperature_c",
            "manufacturer_life_years",
            "minimum_valid_discharge_mv_day",
            "battery_model",
            "battery_pack_voltage",
            "battery_pack_ah",
            "battery_pack_wh",
            "battery_cells",
        ]

        self.fields = self.operational_fields + self.technical_fields

        for key in self.fields:
            label = QLabel()
            input_box = QLineEdit()

            self.field_labels[key] = label
            self.inputs[key] = input_box

            self.form.addRow(label, input_box)

        layout.addLayout(self.form)

        self.technical_status_label = QLabel()
        layout.addWidget(self.technical_status_label)

        self.unlock_button = QPushButton()
        self.unlock_button.clicked.connect(self.unlock_technical_settings)
        layout.addWidget(self.unlock_button)

        button_layout = QHBoxLayout()

        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)

        self.restore_button = QPushButton()
        self.restore_button.clicked.connect(self.restore_defaults)
        button_layout.addWidget(self.restore_button)

        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def apply_language(self):
        self.setWindowTitle(self.t("battery_settings"))
        self.title_label.setText(self.t("battery_settings"))

        self.operational_label.setText(self.t("operational_settings"))

        for key, label in self.field_labels.items():
            label.setText(self.t(key))

        self.unlock_button.setText(self.t("unlock_technical_settings"))
        self.save_button.setText(self.t("save_settings"))
        self.restore_button.setText(self.t("restore_defaults"))

        self.update_technical_status()

    def update_technical_status(self):
        if self.technical_unlocked:
            self.technical_status_label.setText(
                self.t("technical_settings_unlocked")
            )
        else:
            self.technical_status_label.setText(
                self.t("technical_settings_locked")
            )

    def lock_technical_fields(self):
        self.technical_unlocked = False

        for key in self.technical_fields:
            self.inputs[key].setEnabled(False)

        self.update_technical_status()

    def unlock_technical_settings(self):
        password, ok = QInputDialog.getText(
            self,
            self.t("administrator_password"),
            self.t("administrator_password"),
            QLineEdit.Password
        )

        if not ok:
            return

        if password != ADMIN_PASSWORD:
            QMessageBox.warning(
                self,
                self.t("settings_error"),
                self.t("invalid_password")
            )
            return

        self.technical_unlocked = True

        for key in self.technical_fields:
            self.inputs[key].setEnabled(True)

        self.update_technical_status()

    def load_settings(self):
        settings = get_app_settings()

        for key, input_box in self.inputs.items():
            input_box.setText(str(settings.get(key, "")))

    def save_settings(self):
        try:
            current_settings = get_app_settings()

            settings = {
                "warning_voltage_mv": float(
                    self.inputs["warning_voltage_mv"].text()
                ),
                "critical_voltage_mv": float(
                    self.inputs["critical_voltage_mv"].text()
                ),
                "warning_temperature_c": float(
                    self.inputs["warning_temperature_c"].text()
                ),
                "critical_temperature_c": float(
                    self.inputs["critical_temperature_c"].text()
                ),
                "replacement_alert_days": int(
                    float(self.inputs["replacement_alert_days"].text())
                ),
            }

            if self.technical_unlocked:
                settings.update({
                    "technical_optimal_voltage_mv": float(
                        self.inputs["technical_optimal_voltage_mv"].text()
                    ),
                    "technical_critical_voltage_mv": float(
                        self.inputs["technical_critical_voltage_mv"].text()
                    ),
                    "optimal_temperature_c": float(
                        self.inputs["optimal_temperature_c"].text()
                    ),
                    "manufacturer_life_years": float(
                        self.inputs["manufacturer_life_years"].text()
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
                })
            else:
                for key in self.technical_fields:
                    settings[key] = current_settings.get(key)

                settings["optimal_temperature_c"] = current_settings.get(
                    "optimal_temperature_c"
                )

            save_app_settings(settings)
            self.settings_saved_signal.emit()

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
        password, ok = QInputDialog.getText(
            self,
            self.t("administrator_password"),
            self.t("administrator_password"),
            QLineEdit.Password
        )

        if not ok:
            return

        if password != ADMIN_PASSWORD:
            QMessageBox.warning(
                self,
                self.t("settings_error"),
                self.t("invalid_password")
            )
            return

        restore_default_app_settings()
        self.load_settings()
        self.lock_technical_fields()
        self.settings_saved_signal.emit()

        QMessageBox.information(
            self,
            self.t("defaults_restored"),
            self.t("defaults_restored_message")
        )