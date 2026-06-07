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


class SettingsWindow(QMainWindow):
    """
    Battery Intelligence settings window.

    These values control:
    - battery health calculation
    - voltage thresholds
    - prediction limits
    - replacement planning alerts

    Settings are stored in SQLite app_settings table.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Battery Intelligence Settings")
        self.resize(500, 500)

        self.inputs = {}

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        title = QLabel("Battery Intelligence Settings")
        layout.addWidget(title)

        form = QFormLayout()

        fields = {
            "optimal_voltage_mv": "Optimal Voltage (mV)",
            "warning_voltage_mv": "Warning Voltage (mV)",
            "critical_voltage_mv": "Critical Voltage (mV)",
            "optimal_temperature_c": "Optimal Temperature (°C)",
            "warning_temperature_c": "Warning Temperature (°C)",
            "critical_temperature_c": "Critical Temperature (°C)",
            "manufacturer_life_years": "Manufacturer Life (years)",
            "replacement_alert_days": "Replacement Alert (days)",
            "minimum_valid_discharge_mv_day": "Minimum Valid Discharge (mV/day)",
            "battery_model": "Battery Model",
            "battery_pack_voltage": "Battery Pack Voltage",
            "battery_pack_ah": "Battery Pack Ah",
            "battery_pack_wh": "Battery Pack Wh",
            "battery_cells": "Battery Cells",
        }

        for key, label in fields.items():
            input_box = QLineEdit()
            self.inputs[key] = input_box
            form.addRow(label, input_box)

        layout.addLayout(form)

        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)

        self.restore_button = QPushButton("Restore Defaults")
        self.restore_button.clicked.connect(self.restore_defaults)
        button_layout.addWidget(self.restore_button)

        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def load_settings(self):
        """
        Load settings from SQLite into input fields.
        """

        settings = get_app_settings()

        for key, input_box in self.inputs.items():
            input_box.setText(str(settings.get(key, "")))

    def save_settings(self):
        """
        Validate and save settings to SQLite.
        """

        try:
            settings = {
                "optimal_voltage_mv": float(self.inputs["optimal_voltage_mv"].text()),
                "warning_voltage_mv": float(self.inputs["warning_voltage_mv"].text()),
                "critical_voltage_mv": float(self.inputs["critical_voltage_mv"].text()),
                "optimal_temperature_c": float(self.inputs["optimal_temperature_c"].text()),
                "warning_temperature_c": float(self.inputs["warning_temperature_c"].text()),
                "critical_temperature_c": float(self.inputs["critical_temperature_c"].text()),
                "manufacturer_life_years": float(self.inputs["manufacturer_life_years"].text()),
                "replacement_alert_days": int(float(self.inputs["replacement_alert_days"].text())),
                "minimum_valid_discharge_mv_day": float(self.inputs["minimum_valid_discharge_mv_day"].text()),
                "battery_model": self.inputs["battery_model"].text(),
                "battery_pack_voltage": float(self.inputs["battery_pack_voltage"].text()),
                "battery_pack_ah": float(self.inputs["battery_pack_ah"].text()),
                "battery_pack_wh": float(self.inputs["battery_pack_wh"].text()),
                "battery_cells": int(float(self.inputs["battery_cells"].text())),
            }

            save_app_settings(settings)

            QMessageBox.information(
                self,
                "Settings Saved",
                "Battery Intelligence settings were saved successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Settings Error",
                f"Could not save settings:\n{e}"
            )

    def restore_defaults(self):
        """
        Restore default settings.
        """

        restore_default_app_settings()
        self.load_settings()

        QMessageBox.information(
            self,
            "Defaults Restored",
            "Default Battery Intelligence settings were restored."
        )