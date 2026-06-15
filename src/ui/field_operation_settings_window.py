from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.database.database import (
    get_field_operation_settings,
    save_field_operation_settings,
    restore_default_field_operation_settings,
)
from src.translations.language_manager import LanguageManager


class FieldOperationSettingsWindow(QMainWindow):
    settings_saved_signal = Signal()

    def __init__(self):
        super().__init__()

        self.inputs = {}
        self.field_labels = {}

        self.setWindowTitle(self.t("field_operation_settings"))
        self.resize(620, 420)

        self.setup_ui()
        self.load_settings()
        self.apply_language()

    def t(self, key):
        return LanguageManager.translate(key)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.form = QFormLayout()

        self.fields = [
            "configured_warning_percent",
            "configured_critical_percent",
            "bits_hour",
            "bits_minute",
            "sleep_minutes",
            "wake_minutes",
            "minimum_gps_percent",
        ]

        for key in self.fields:
            label = QLabel()
            input_box = QLineEdit()
            self.field_labels[key] = label
            self.inputs[key] = input_box
            self.form.addRow(label, input_box)

        self.notes_label = QLabel()
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(90)
        self.form.addRow(self.notes_label, self.notes_input)

        layout.addLayout(self.form)

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
        self.setWindowTitle(self.t("field_operation_settings"))
        self.title_label.setText(self.t("field_operation_settings"))
        self.description_label.setText(self.t("field_operation_settings_description"))

        for key, label in self.field_labels.items():
            label.setText(self.t(key))

        self.notes_label.setText(self.t("field_operation_notes"))
        self.save_button.setText(self.t("save_settings"))
        self.restore_button.setText(self.t("restore_defaults"))

    def load_settings(self):
        settings = get_field_operation_settings()

        for key, input_box in self.inputs.items():
            input_box.setText(str(settings.get(key, "")))

        self.notes_input.setPlainText(str(settings.get("notes", "")))

    def save_settings(self):
        try:
            settings = {
                "configured_warning_percent": float(
                    self.inputs["configured_warning_percent"].text()
                ),
                "configured_critical_percent": float(
                    self.inputs["configured_critical_percent"].text()
                ),
                "bits_hour": int(float(self.inputs["bits_hour"].text())),
                "bits_minute": int(float(self.inputs["bits_minute"].text())),
                "sleep_minutes": float(self.inputs["sleep_minutes"].text()),
                "wake_minutes": float(self.inputs["wake_minutes"].text()),
                "minimum_gps_percent": float(
                    self.inputs["minimum_gps_percent"].text()
                ),
                "notes": self.notes_input.toPlainText(),
            }

            save_field_operation_settings(settings)
            self.settings_saved_signal.emit()

            QMessageBox.information(
                self,
                self.t("settings_saved"),
                self.t("field_operation_settings_saved_message")
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                self.t("settings_error"),
                f"{self.t('settings_error')}:\n{e}"
            )

    def restore_defaults(self):
        restore_default_field_operation_settings()
        self.load_settings()
        self.settings_saved_signal.emit()

        QMessageBox.information(
            self,
            self.t("defaults_restored"),
            self.t("defaults_restored_message")
        )
