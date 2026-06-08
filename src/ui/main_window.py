import pandas as pd
from datetime import datetime

from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.database.database import clear_database
from src.importers.importer import CSVImporter
from src.ui.node_detail_window import NodeDetailWindow
from src.ui.node_comparison_window import NodeComparisonWindow
from src.ui.settings_window import SettingsWindow
from src.translations.language_manager import LanguageManager
from src.licensing.trial_manager import TrialManager


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.language = "en"
        LanguageManager.set_language(self.language)

        self.setWindowTitle("Node Health Analyzer")
        self.resize(1400, 850)

        self.importer = CSVImporter()
        self.nodes = []

        self.detail_windows = []
        self.comparison_windows = []
        self.settings_windows = []
        self.current_folder = ""
        self.setup_ui()

    def t(self, key):
        return LanguageManager.translate(key)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.create_menu_bar()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        self.language_filter = QComboBox()
        self.language_filter.addItem("English", "en")
        self.language_filter.addItem("Español", "es")
        self.language_filter.addItem("中文", "zh")
        self.language_filter.currentIndexChanged.connect(self.change_language)
        layout.addWidget(self.language_filter)

        self.import_button = QPushButton()
        self.import_button.clicked.connect(self.import_folder)
        layout.addWidget(self.import_button)

        self.nodes_label = QLabel()
        layout.addWidget(self.nodes_label)

        self.health_summary_label = QLabel()
        layout.addWidget(self.health_summary_label)

        self.kpi_label = QLabel()
        layout.addWidget(self.kpi_label)

        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.update_table)
        layout.addWidget(self.search_box)

        self.classification_filter = QComboBox()
        self.classification_filter.currentIndexChanged.connect(self.update_table)
        layout.addWidget(self.classification_filter)

        self.table = QTableWidget()
        self.table.setColumnCount(15)
        self.table.cellDoubleClicked.connect(self.open_node_detail)
        layout.addWidget(self.table)

        central_widget.setLayout(layout)

        self.apply_language()

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        self.file_menu = menu_bar.addMenu("File")
        self.tools_menu = menu_bar.addMenu("Tools")
        self.help_menu = menu_bar.addMenu("Help")

        self.import_action = QAction("Import Folder", self)
        self.import_action.triggered.connect(self.import_folder)
        self.file_menu.addAction(self.import_action)

        self.export_excel_action = QAction("Export Excel", self)
        self.export_excel_action.triggered.connect(self.export_excel)
        self.file_menu.addAction(self.export_excel_action)

        self.export_pdf_action = QAction("Export PDF", self)
        self.export_pdf_action.triggered.connect(self.export_pdf)
        self.file_menu.addAction(self.export_pdf_action)

        self.file_menu.addSeparator()

        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

        self.compare_action = QAction("Compare Nodes", self)
        self.compare_action.triggered.connect(self.open_node_comparison)
        self.tools_menu.addAction(self.compare_action)

        self.settings_action = QAction("Battery Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.tools_menu.addAction(self.settings_action)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.about_action)

    def update_menu_language(self):
        self.file_menu.setTitle("Archivo" if self.language == "es" else "File")
        self.tools_menu.setTitle("Herramientas" if self.language == "es" else "Tools")
        self.help_menu.setTitle("Ayuda" if self.language == "es" else "Help")

        self.import_action.setText(self.t("import_folder"))
        self.export_excel_action.setText(self.t("export_excel"))
        self.export_pdf_action.setText(self.t("export_pdf"))
        self.compare_action.setText(self.t("compare_nodes"))
        self.settings_action.setText(self.t("battery_settings"))
        self.about_action.setText(self.t("about"))

        self.exit_action.setText("Salir" if self.language == "es" else "Exit")

    def change_language(self):
        self.language = self.language_filter.currentData()
        LanguageManager.set_language(self.language)

        self.apply_language()
        self.update_table()

    def apply_language(self):
        self.setWindowTitle(self.t("app_title"))
        self.title_label.setText(self.t("app_title"))

        self.import_button.setText(self.t("import_folder"))
        self.search_box.setPlaceholderText(self.t("search_node"))

        self.update_menu_language()
        self.update_classification_filter_items()
        self.update_table_headers()
        self.update_labels()

    def update_classification_filter_items(self):
        current_value = self.classification_filter.currentData()

        if current_value is None:
            current_value = "All"

        self.classification_filter.blockSignals(True)
        self.classification_filter.clear()

        self.classification_filter.addItem(self.t("all"), "All")
        self.classification_filter.addItem(self.t("excellent"), "Excellent")
        self.classification_filter.addItem(self.t("good"), "Good")
        self.classification_filter.addItem(self.t("warning"), "Warning")
        self.classification_filter.addItem(self.t("critical"), "Critical")

        for index in range(self.classification_filter.count()):
            if self.classification_filter.itemData(index) == current_value:
                self.classification_filter.setCurrentIndex(index)
                break

        self.classification_filter.blockSignals(False)

    def update_table_headers(self):
        self.table.setHorizontalHeaderLabels(
            [
                self.t("node"),
                self.t("records"),
                "Voltage (mV)",
                "Charge (%)",
                self.t("acq_type"),
                "GPS (%)",
                "Temp (°C)",
                self.t("last_time"),
                self.t("health_score"),
                self.t("classification"),
                self.t("battery_health"),
                self.t("degradation_level"),
                self.t("remaining_life"),
                self.t("prediction_confidence"),
                self.t("recommendation"),
            ]
        )

    def update_labels(self):
        self.nodes_label.setText(
            f"{self.t('nodes_loaded')}: {len(self.nodes)}"
        )

        self.update_health_summary()
        self.update_kpis()

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self.t("import_folder")
        )

        if not folder:
            return

        self.nodes = []
        self.table.clearContents()
        self.table.setRowCount(0)
        self.search_box.clear()

        self.classification_filter.blockSignals(True)
        self.classification_filter.setCurrentIndex(0)
        self.classification_filter.blockSignals(False)
        self.current_folder = folder
        clear_database()

        self.nodes = self.importer.load_folder(folder)

        self.update_table()

    def get_filtered_nodes(self):
        filtered_nodes = self.nodes

        search_text = self.search_box.text().strip()

        if search_text:
            filtered_nodes = [
                node
                for node in filtered_nodes
                if search_text in node.get("serial_number", "")
            ]

        selected_classification = self.classification_filter.currentData()

        if selected_classification and selected_classification != "All":
            filtered_nodes = [
                node
                for node in filtered_nodes
                if node.get("classification") == selected_classification
            ]

        return filtered_nodes

    def update_health_summary(self):
        excellent = sum(
            1 for node in self.nodes
            if node.get("classification") == "Excellent"
        )

        good = sum(
            1 for node in self.nodes
            if node.get("classification") == "Good"
        )

        warning = sum(
            1 for node in self.nodes
            if node.get("classification") == "Warning"
        )

        critical = sum(
            1 for node in self.nodes
            if node.get("classification") == "Critical"
        )

        self.health_summary_label.setText(
            f"{self.t('excellent')}: {excellent} | "
            f"{self.t('good')}: {good} | "
            f"{self.t('warning')}: {warning} | "
            f"{self.t('critical')}: {critical}"
        )

    def update_kpis(self):
        if not self.nodes:
            self.kpi_label.setText(
                f"{self.t('average_voltage')}: 0 mV | "
                f"{self.t('average_charge')}: 0 %"
            )
            return

        df = pd.DataFrame(self.nodes)

        df["voltage"] = pd.to_numeric(
            df["voltage"],
            errors="coerce"
        )

        df["charge"] = pd.to_numeric(
            df["charge"],
            errors="coerce"
        )

        avg_voltage = df["voltage"].mean()
        avg_charge = df["charge"].mean()

        if pd.isna(avg_voltage):
            avg_voltage = 0

        if pd.isna(avg_charge):
            avg_charge = 0

        self.kpi_label.setText(
            f"{self.t('average_voltage')}: {avg_voltage:.0f} mV | "
            f"{self.t('average_charge')}: {avg_charge:.1f} %"
        )

    def format_battery_health(self, value):
        if value is None or pd.isna(value):
            return self.t("not_available")

        return f"{value:.0f}%"

    def format_remaining_days(self, value):
        if value is None or pd.isna(value):
            return self.t("not_available")

        return f"{value:.0f} {self.t('days')}"

    def update_table(self):
        self.table.clearContents()
        self.table.setRowCount(0)

        self.update_labels()

        filtered_nodes = self.get_filtered_nodes()
        self.table.setRowCount(len(filtered_nodes))

        classification_colors = {
            "Excellent": QColor(0, 180, 0),
            "Good": QColor(0, 120, 255),
            "Warning": QColor(255, 165, 0),
            "Critical": QColor(255, 60, 60),
        }

        for row, node in enumerate(filtered_nodes):
            classification = node.get("classification", "")

            display_classification = {
                "Excellent": self.t("excellent"),
                "Good": self.t("good"),
                "Warning": self.t("warning"),
                "Critical": self.t("critical"),
            }.get(classification, classification)

            battery_health_text = self.format_battery_health(
                node.get("battery_health")
            )

            remaining_days_text = self.format_remaining_days(
                node.get("remaining_days")
            )

            values = [
                node.get("serial_number", ""),
                node.get("records", ""),
                node.get("voltage", ""),
                node.get("charge", ""),
                node.get("acq_type", ""),
                node.get("gps_quality", ""),
                node.get("temperature", ""),
                node.get("last_time", ""),
                node.get("health_score", ""),
                display_classification,
                battery_health_text,
                self.t(str(node.get("degradation_level", "")).lower()),
                remaining_days_text,
                self.t(str(node.get("prediction_confidence", "")).lower()),
                self.t(node.get("recommendation", "")),
            ]

            classification_color = classification_colors.get(
                classification,
                QColor(255, 255, 255)
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in [8, 9, 10, 11]:
                    item.setForeground(classification_color)
                    item.setFont(QFont("", -1, QFont.Bold))

                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()

    def export_excel(self):
        filtered_nodes = self.get_filtered_nodes()

        if not filtered_nodes:
            QMessageBox.warning(
                self,
                self.t("export_excel"),
                self.t("no_data_export")
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("export_excel"),
            "node_health_report.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        rows = []

        for node in filtered_nodes:
            rows.append({
                self.t("node"): node.get("serial_number", ""),
                self.t("records"): node.get("records", ""),
                "Voltage (mV)": node.get("voltage", ""),
                "Charge (%)": node.get("charge", ""),
                self.t("acq_type"): node.get("acq_type", ""),
                "GPS (%)": node.get("gps_quality", ""),
                "Temp (°C)": node.get("temperature", ""),
                self.t("last_time"): node.get("last_time", ""),
                self.t("health_score"): node.get("health_score", ""),
                self.t("classification"): node.get("classification", ""),
                self.t("battery_health"): node.get("battery_health", ""),
                self.t("degradation_level"): self.t(
                    str(node.get("degradation_level", "")).lower()
                ),
                self.t("remaining_life"): node.get("remaining_days", ""),
                self.t("prediction_confidence"): node.get(
                    "prediction_confidence",
                    ""
                ),
                self.t("recommendation"): self.t(
                    node.get("recommendation", "")
                ),
            })

        df = pd.DataFrame(rows)

        try:
            df.to_excel(file_path, index=False)

            QMessageBox.information(
                self,
                self.t("export_excel"),
                "Excel report exported successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Excel Error",
                str(e)
            )

    def export_pdf(self):
        filtered_nodes = self.get_filtered_nodes()

        if not filtered_nodes:
            QMessageBox.warning(
                self,
                self.t("export_pdf"),
                self.t("no_data_export")
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("export_pdf"),
            "node_health_report.pdf",
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return

        try:
            doc = SimpleDocTemplate(
                file_path,
                pagesize=landscape(letter)
            )

            styles = getSampleStyleSheet()
            elements = []

            title = Paragraph(
                "Node Health Analyzer Report",
                styles["Title"]
            )
            elements.append(title)
            elements.append(Spacer(1, 12))

            generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

            summary = Paragraph(
                f"Generated: {generated_at}<br/>"
                f"Total Nodes: {len(self.nodes)}<br/>"
                f"Filtered Nodes: {len(filtered_nodes)}<br/>"
                f"{self.health_summary_label.text()}<br/>"
                f"{self.kpi_label.text()}",
                styles["Normal"]
            )

            elements.append(summary)
            elements.append(Spacer(1, 12))

            table_data = [
                [
                    self.t("node"),
                    self.t("records"),
                    "Voltage",
                    "Charge",
                    self.t("acq_type"),
                    "GPS",
                    "Temp",
                    self.t("health_score"),
                    self.t("classification"),
                    self.t("battery_health"),
                    self.t("degradation_level"),
                    self.t("remaining_life"),
                    self.t("recommendation"),
                ]
            ]

            for node in filtered_nodes:
                table_data.append(
                    [
                        node.get("serial_number", ""),
                        node.get("records", ""),
                        node.get("voltage", ""),
                        node.get("charge", ""),
                        node.get("acq_type", ""),
                        node.get("gps_quality", ""),
                        node.get("temperature", ""),
                        node.get("health_score", ""),
                        node.get("classification", ""),
                        self.format_battery_health(
                            node.get("battery_health")
                        ),
                        self.t(
                            str(node.get("degradation_level", "")).lower()
                        ),
                        self.format_remaining_days(
                            node.get("remaining_days")
                        ),
                        self.t(node.get("recommendation", "")),
                    ]
                )

            table = Table(table_data, repeatRows=1)

            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )

            elements.append(table)
            doc.build(elements)

            QMessageBox.information(
                self,
                self.t("export_pdf"),
                "PDF report exported successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export PDF Error",
                str(e)
            )

    def open_node_detail(self, row, column):
        filtered_nodes = self.get_filtered_nodes()

        if row < 0 or row >= len(filtered_nodes):
            return

        node_data = filtered_nodes[row]

        detail_window = NodeDetailWindow(node_data)
        detail_window.show()

        self.detail_windows.append(detail_window)

    def open_node_comparison(self):
        if not self.nodes:
            QMessageBox.warning(
                self,
                self.t("compare_nodes"),
                "No nodes loaded."
            )
            return

        comparison_window = NodeComparisonWindow(
            self.get_filtered_nodes()
        )

        comparison_window.show()
        self.comparison_windows.append(comparison_window)

    def open_settings(self):
            """
            Open battery settings window.

            When settings are saved, the current imported folder is reanalyzed
            automatically using the new configuration values.
            """

            settings_window = SettingsWindow()

            settings_window.settings_saved_signal.connect(
                self.refresh_analysis_from_settings
            )

            settings_window.show()

            self.settings_windows.append(settings_window)

    def show_about(self):
        (
            is_valid,
            days_used,
            days_remaining,
            install_date,
            error_message
        ) = TrialManager.get_trial_status()

        QMessageBox.information(
            self,
            self.t("about"),
            "Node Health Analyzer\n\n"
            "Version: 1.0.2 Trial\n\n"
            f"Install Date: {install_date}\n"
            f"Days Used: {days_used}\n"
            f"Days Remaining: {days_remaining}\n\n"
            "Desktop application for Sercel seismic node "
            "battery health monitoring, CSV analysis, node comparison, "
            "and operational reporting.\n\n"
            "Developed by: Alvarado Leyva\n"
            "Copyright © 2026\n\n"
            "Technologies:\n"
            "Python, PySide6, Pandas, Plotly, SQLite, ReportLab"
        )
    def refresh_analysis_from_settings(self):
        """
        Recalculate current dashboard after battery settings change.

        This reloads the already selected folder using the new settings.
        """

        if not self.current_folder:
            return

        self.nodes = []
        self.table.clearContents()
        self.table.setRowCount(0)

        clear_database()

        self.nodes = self.importer.load_folder(self.current_folder)

        self.update_table()

        QMessageBox.information(
            self,
            self.t("battery_settings"),
            "Analysis recalculated with the new battery settings."
        )