import pandas as pd
from datetime import datetime

from PySide6.QtGui import QColor, QFont
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
from src.translations.language_manager import LanguageManager


class MainWindow(QMainWindow):
    """
    Main application window.

    Important maintenance notes:
    - Raw CSV/database values are NOT translated.
    - Only visible UI labels are translated.
    - Internal classification values remain:
      Excellent, Good, Warning, Critical.
    - Classification filter uses itemData() for internal values.
    """

    def __init__(self):
        """
        Initialize main window and global language state.

        __init__ is the constructor of the class.
        It runs automatically when MainWindow() is created in main.py.
        """

        super().__init__()

        self.language = "en"

        # This sets the global language used by child windows
        # such as NodeDetailWindow and NodeComparisonWindow.
        LanguageManager.set_language(
            self.language
        )

        self.setWindowTitle("Node Health Analyzer")
        self.resize(1200, 800)

        self.importer = CSVImporter()
        self.nodes = []

        # Keep references to child windows.
        # Without this, PySide can close windows unexpectedly.
        self.detail_windows = []
        self.comparison_windows = []

        self.setup_ui()

    def t(self, key):
        """
        Translate a UI key using the global LanguageManager.
        """
        return LanguageManager.translate(key)

    def setup_ui(self):
        """
        Build main dashboard interface.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel()
        layout.addWidget(self.title_label)

        # Language selector.
        # Visible text: English / Español / 中文.
        # Internal value: en / es / zh.
        self.language_filter = QComboBox()
        self.language_filter.addItem("English", "en")
        self.language_filter.addItem("Español", "es")
        self.language_filter.addItem("中文", "zh")
        self.language_filter.currentIndexChanged.connect(
            self.change_language
        )
        layout.addWidget(self.language_filter)

        self.import_button = QPushButton()
        self.import_button.clicked.connect(self.import_folder)
        layout.addWidget(self.import_button)

        self.export_excel_button = QPushButton()
        self.export_excel_button.clicked.connect(self.export_excel)
        layout.addWidget(self.export_excel_button)

        self.export_pdf_button = QPushButton()
        self.export_pdf_button.clicked.connect(self.export_pdf)
        layout.addWidget(self.export_pdf_button)

        self.compare_button = QPushButton()
        self.compare_button.clicked.connect(
            self.open_node_comparison
        )
        layout.addWidget(self.compare_button)

        self.nodes_label = QLabel()
        layout.addWidget(self.nodes_label)

        self.health_summary_label = QLabel()
        layout.addWidget(self.health_summary_label)

        self.kpi_label = QLabel()
        layout.addWidget(self.kpi_label)

        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self.update_table)
        layout.addWidget(self.search_box)

        # Classification filter:
        # Visible text is translated.
        # itemData remains in English for logic.
        self.classification_filter = QComboBox()
        self.classification_filter.currentIndexChanged.connect(
            self.update_table
        )
        layout.addWidget(self.classification_filter)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.cellDoubleClicked.connect(
            self.open_node_detail
        )
        layout.addWidget(self.table)

        self.about_button = QPushButton()
        self.about_button.clicked.connect(self.show_about)
        layout.addWidget(self.about_button)

        central_widget.setLayout(layout)

        self.apply_language()

    def change_language(self):
        """
        Change current UI language and update global language manager.
        """

        self.language = self.language_filter.currentData()

        LanguageManager.set_language(
            self.language
        )

        self.apply_language()
        self.update_table()

    def apply_language(self):
        """
        Apply translations to all main window controls.
        """

        self.setWindowTitle(self.t("app_title"))
        self.title_label.setText(self.t("app_title"))

        self.import_button.setText(self.t("import_folder"))
        self.export_excel_button.setText(self.t("export_excel"))
        self.export_pdf_button.setText(self.t("export_pdf"))
        self.compare_button.setText(self.t("compare_nodes"))
        self.about_button.setText(self.t("about"))

        self.search_box.setPlaceholderText(self.t("search_node"))

        self.update_classification_filter_items()
        self.update_table_headers()
        self.update_labels()

    def update_classification_filter_items(self):
        """
        Rebuild classification filter while preserving internal values.
        """

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
        """
        Translate dashboard table headers.
        """

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
            ]
        )

    def update_labels(self):
        """
        Refresh translated labels and KPI text.
        """

        self.nodes_label.setText(
            f"{self.t('nodes_loaded')}: {len(self.nodes)}"
        )

        self.update_health_summary()
        self.update_kpis()

    def import_folder(self):
        """
        Import all CSV files from a selected folder.

        DEVELOPMENT ONLY:
        clear_database() avoids duplicate records during repeated tests.

        PRODUCTION TODO:
        Replace clear_database() with duplicate-safe import if historical
        data must be preserved between imports.
        """

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

        clear_database()

        self.nodes = self.importer.load_folder(folder)

        self.update_table()

    def get_filtered_nodes(self):
        """
        Return nodes filtered by search box and classification.
        Classification uses internal English values.
        """

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
        """
        Update translated health summary counts.
        """

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
        """
        Update average voltage and charge KPIs.
        """

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

    def update_table(self):
        """
        Refresh table using current filters.
        """

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

            # Display translated classification only.
            # Internal value remains unchanged.
            display_classification = {
                "Excellent": self.t("excellent"),
                "Good": self.t("good"),
                "Warning": self.t("warning"),
                "Critical": self.t("critical"),
            }.get(classification, classification)

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
            ]

            classification_color = classification_colors.get(
                classification,
                QColor(255, 255, 255)
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in [8, 9]:
                    item.setForeground(classification_color)
                    item.setFont(QFont("", -1, QFont.Bold))

                self.table.setItem(
                    row,
                    column,
                    item
                )

        self.table.resizeColumnsToContents()

    def export_excel(self):
        """
        Export filtered dashboard data to Excel.
        Headers follow selected UI language.
        """

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
            })

        df = pd.DataFrame(rows)

        try:
            df.to_excel(
                file_path,
                index=False
            )

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
        """
        Export filtered dashboard data to PDF.
        Headers follow selected UI language.
        """

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

            generated_at = datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )

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
                    ]
                )

            table = Table(
                table_data,
                repeatRows=1
            )

            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
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
        """
        Open node detail window.
        Uses filtered nodes so row index matches visible table.
        """

        filtered_nodes = self.get_filtered_nodes()

        if row < 0 or row >= len(filtered_nodes):
            return

        node_data = filtered_nodes[row]

        detail_window = NodeDetailWindow(node_data)
        detail_window.show()

        self.detail_windows.append(detail_window)

    def open_node_comparison(self):
        """
        Open comparison window for currently filtered nodes.
        """

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

    def show_about(self):
        """
        Show application information.
        """

        QMessageBox.information(
            self,
            self.t("about"),
            "Node Health Analyzer\n\n"
            "Version: 1.0.0 Release Candidate\n\n"
            "Desktop application for Sercel seismic node "
            "battery health monitoring, CSV analysis, node comparison, "
            "and operational reporting.\n\n"
            "Developed by: Alvarado Leyva\n"
            "Copyright © 2026\n\n"
            "Technologies:\n"
            "Python, PySide6, Pandas, Plotly, SQLite, ReportLab"
        )