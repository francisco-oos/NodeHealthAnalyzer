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


class MainWindow(QMainWindow):
    """
    Main application window.

    Responsibilities:
    - Import Sercel CSV folders.
    - Display loaded nodes in a dashboard table.
    - Filter/search nodes.
    - Export filtered results to Excel/PDF.
    - Open node detail window.
    - Open multi-node comparison window.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Node Health Analyzer")
        self.resize(1200, 800)

        self.importer = CSVImporter()

        # In-memory list of loaded node summaries.
        self.nodes = []

        # Keep references to child windows.
        # This prevents PySide from garbage-collecting opened windows.
        self.detail_windows = []
        self.comparison_windows = []

        self.setup_ui()

    def setup_ui(self):
        """
        Build the main dashboard UI.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        self.title_label = QLabel("Node Health Analyzer")
        layout.addWidget(self.title_label)

        self.import_button = QPushButton("Import Folder")
        self.import_button.clicked.connect(self.import_folder)
        layout.addWidget(self.import_button)

        self.export_excel_button = QPushButton("Export Excel")
        self.export_excel_button.clicked.connect(self.export_excel)
        layout.addWidget(self.export_excel_button)

        self.export_pdf_button = QPushButton("Export PDF")
        self.export_pdf_button.clicked.connect(self.export_pdf)
        layout.addWidget(self.export_pdf_button)

        self.compare_button = QPushButton("Compare Nodes")
        self.compare_button.clicked.connect(
            self.open_node_comparison
        )
        layout.addWidget(self.compare_button)

        self.nodes_label = QLabel("Nodes Loaded: 0")
        layout.addWidget(self.nodes_label)

        self.health_summary_label = QLabel(
            "Excellent: 0 | Good: 0 | Warning: 0 | Critical: 0"
        )
        layout.addWidget(self.health_summary_label)

        self.kpi_label = QLabel(
            "Average Voltage: 0 mV | Average Charge: 0 %"
        )
        layout.addWidget(self.kpi_label)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Node...")
        self.search_box.textChanged.connect(self.update_table)
        layout.addWidget(self.search_box)

        self.classification_filter = QComboBox()
        self.classification_filter.addItems(
            [
                "All",
                "Excellent",
                "Good",
                "Warning",
                "Critical",
            ]
        )
        self.classification_filter.currentTextChanged.connect(
            self.update_table
        )
        layout.addWidget(self.classification_filter)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "Node",
                "Records",
                "Voltage (mV)",
                "Charge (%)",
                "Acq Type",
                "GPS (%)",
                "Temp (°C)",
                "Last Time",
                "Health Score",
                "Classification",
            ]
        )

        # Double click opens the node detail chart window.
        self.table.cellDoubleClicked.connect(
            self.open_node_detail
        )

        layout.addWidget(self.table)
        central_widget.setLayout(layout)

    def import_folder(self):
        """
        Import all CSV files from a selected folder.

        Current V1 behavior:
        - The database is cleared before each import.
        - This avoids duplicate records while we are developing/testing.

        Future production behavior:
        - Remove or disable clear_database().
        - Replace with a smarter import strategy:
          - avoid duplicates,
          - update existing nodes,
          - preserve historical campaigns.
        """

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )

        if not folder:
            return

        self.nodes = []
        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText("Nodes Loaded: 0")
        self.health_summary_label.setText(
            "Excellent: 0 | Good: 0 | Warning: 0 | Critical: 0"
        )
        self.kpi_label.setText(
            "Average Voltage: 0 mV | Average Charge: 0 %"
        )

        self.search_box.clear()
        self.classification_filter.setCurrentText("All")

        # DEVELOPMENT ONLY:
        # Clears SQLite database before each import.
        # Useful now because we reload the same test folders many times.
        # Do NOT keep this behavior in production if historical data
        # must be preserved.
        clear_database()

        self.nodes = self.importer.load_folder(folder)

        self.update_table()

    def get_filtered_nodes(self):
        """
        Return nodes filtered by:
        - serial number search
        - classification dropdown
        """

        filtered_nodes = self.nodes

        search_text = self.search_box.text().strip()

        if search_text:
            filtered_nodes = [
                node
                for node in filtered_nodes
                if search_text in node.get("serial_number", "")
            ]

        selected_classification = self.classification_filter.currentText()

        if selected_classification != "All":
            filtered_nodes = [
                node
                for node in filtered_nodes
                if node.get("classification") == selected_classification
            ]

        return filtered_nodes

    def update_health_summary(self):
        """
        Update count of nodes by classification.
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
            f"Excellent: {excellent} | "
            f"Good: {good} | "
            f"Warning: {warning} | "
            f"Critical: {critical}"
        )

    def update_kpis(self):
        """
        Update dashboard KPI averages.

        These averages are calculated from the latest valid value
        of each loaded node.
        """

        if not self.nodes:
            self.kpi_label.setText(
                "Average Voltage: 0 mV | Average Charge: 0 %"
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
            f"Average Voltage: {avg_voltage:.0f} mV | "
            f"Average Charge: {avg_charge:.1f} %"
        )

    def update_table(self):
        """
        Refresh the dashboard table using current filters.
        """

        self.table.clearContents()
        self.table.setRowCount(0)

        self.nodes_label.setText(
            f"Nodes Loaded: {len(self.nodes)}"
        )

        self.update_health_summary()
        self.update_kpis()

        filtered_nodes = self.get_filtered_nodes()

        self.table.setRowCount(len(filtered_nodes))

        classification_colors = {
            "Excellent": QColor(0, 180, 0),
            "Good": QColor(0, 120, 255),
            "Warning": QColor(255, 165, 0),
            "Critical": QColor(255, 60, 60),
        }

        for row, node in enumerate(filtered_nodes):

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
                node.get("classification", ""),
            ]

            classification = node.get("classification", "")
            classification_color = classification_colors.get(
                classification,
                QColor(255, 255, 255)
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                # Only Health Score and Classification are colored.
                # This keeps the table readable in dark mode.
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
        Export the currently filtered dashboard table to Excel.
        """

        filtered_nodes = self.get_filtered_nodes()

        if not filtered_nodes:
            QMessageBox.warning(
                self,
                "Export Excel",
                "No data available to export."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel Report",
            "node_health_report.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        rows = []

        for node in filtered_nodes:
            rows.append({
                "Node": node.get("serial_number", ""),
                "Records": node.get("records", ""),
                "Voltage (mV)": node.get("voltage", ""),
                "Charge (%)": node.get("charge", ""),
                "Acq Type": node.get("acq_type", ""),
                "GPS (%)": node.get("gps_quality", ""),
                "Temp (°C)": node.get("temperature", ""),
                "Last Time": node.get("last_time", ""),
                "Health Score": node.get("health_score", ""),
                "Classification": node.get("classification", ""),
            })

        df = pd.DataFrame(rows)

        try:
            df.to_excel(
                file_path,
                index=False
            )

            QMessageBox.information(
                self,
                "Export Excel",
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
        Export the currently filtered dashboard table to a PDF report.
        """

        filtered_nodes = self.get_filtered_nodes()

        if not filtered_nodes:
            QMessageBox.warning(
                self,
                "Export PDF",
                "No data available to export."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Report",
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
                    "Node",
                    "Records",
                    "Voltage",
                    "Charge",
                    "Acq Type",
                    "GPS",
                    "Temp",
                    "Health",
                    "Class",
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
                "Export PDF",
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
        Open detail window for the selected node.
        Uses filtered list so row index matches the visible table.
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

        Example:
        - Filter dashboard to Critical.
        - Click Compare Nodes.
        - Only Critical nodes will be available for comparison.
        """

        if not self.nodes:
            QMessageBox.warning(
                self,
                "Compare Nodes",
                "No nodes loaded."
            )
            return

        comparison_window = NodeComparisonWindow(
            self.get_filtered_nodes()
        )

        comparison_window.show()

        self.comparison_windows.append(comparison_window)